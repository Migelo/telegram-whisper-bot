import os
import tempfile
import asyncio
import logging
import mimetypes
from dataclasses import dataclass
from typing import Optional, Protocol, Any, Dict
from collections import defaultdict
import threading

try:
    import whisper
except ImportError:
    whisper = None


@dataclass
class Config:
    """Configuration constants for the bot."""
    # Telegram limits
    TELEGRAM_MESSAGE_LIMIT = 4096
    
    # Audio processing constants  
    AUDIO_SAMPLE_RATE = 16000
    TRANSCRIPTION_TIME_FACTOR = 13  # seconds per minute of audio
    MIN_AUDIO_DURATION = 0.1  # seconds
    
    # Default limits
    DEFAULT_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    DEFAULT_MAX_QUEUE_SIZE = 100
    DEFAULT_NUM_WORKERS = 2
    DEFAULT_MAX_JOBS_PER_USER = 2
    DEFAULT_WHISPER_MODEL = "base"


@dataclass
class Job:
    chat_id: int
    message_id: int
    file_id: str
    file_name: str
    mime_type: str
    file_size: int
    processing_msg_id: int


class BotProtocol(Protocol):
    async def get_messages(self, entity, ids) -> Any:
        ...
    
    async def send_message(self, entity, message: str, reply_to: Optional[int] = None) -> Any:
        ...
    
    async def edit_message(self, entity, message, text: str) -> Any:
        ...
    
    async def delete_messages(self, entity, message_ids) -> Any:
        ...


class AudioMessage:
    def __init__(self, file_id: str, file_size: int, mime_type: str, file_name: Optional[str] = None, file_unique_id: str = "test"):
        self.file_id = file_id
        self.file_size = file_size
        self.mime_type = mime_type
        self.file_name = file_name
        self.file_unique_id = file_unique_id


class BotCore:
    def __init__(self, 
                 whisper_model: str = "base",
                 num_workers: int = 2,
                 max_file_size: int = 2 * 1024 * 1024 * 1024,  # 2GB
                 max_queue_size: int = 100,
                 max_jobs_per_user_in_queue: int = 2):
        self.whisper_model = whisper_model
        self.num_workers = num_workers
        self.max_file_size = max_file_size
        self.max_queue_size = max_queue_size
        self.max_jobs_per_user_in_queue = max_jobs_per_user_in_queue
        self.processing_queue = asyncio.Queue()
        self.models: Dict[str, Any] = {}  # worker_name -> model instance
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting tracking - jobs in queue per user
        self.user_queue_count: Dict[int, int] = defaultdict(int)
        self._rate_limit_lock = threading.Lock()
        
    def get_worker_model(self, worker_name: str):
        """Get or load Whisper model for a specific worker."""
        if worker_name not in self.models:
            if whisper is None:
                self.logger.error(f"Whisper not available for {worker_name} - install openai-whisper package")
                return None
                
            try:
                self.logger.info(f"Loading Whisper model '{self.whisper_model}' for {worker_name}")
                self.models[worker_name] = whisper.load_model(self.whisper_model)
                self.logger.info(f"Model loaded successfully for {worker_name}")
            except Exception as e:
                self.logger.error(f"Could not load Whisper model for {worker_name}: {e}")
                return None
        
        return self.models[worker_name]

    def validate_audio_file(self, audio: AudioMessage) -> Optional[str]:
        """Validate audio file size. Returns error message if invalid, None if valid."""
        if audio.file_size > self.max_file_size:
            return "File is too large. The limit is 2 GB."
        return None

    def is_queue_full(self) -> bool:
        """Check if the processing queue is at capacity."""
        return self.processing_queue.qsize() >= self.max_queue_size

    def get_queue_position(self) -> int:
        """Get the current queue size (position for next item)."""
        return self.processing_queue.qsize()
    
    def can_user_submit_job(self, chat_id: int) -> bool:
        """Check if user is within their queue job limit."""
        with self._rate_limit_lock:
            current_count = self.user_queue_count[chat_id]
            return current_count < self.max_jobs_per_user_in_queue
    
    def increment_user_queue_count(self, chat_id: int) -> int:
        """Increment user's queued job count and return new count."""
        with self._rate_limit_lock:
            self.user_queue_count[chat_id] += 1
            new_count = self.user_queue_count[chat_id]
            self.logger.debug(f"User {chat_id} now has {new_count} jobs in queue")
            return new_count
    
    def decrement_user_queue_count(self, chat_id: int) -> int:
        """Decrement user's queued job count and return new count."""
        with self._rate_limit_lock:
            if self.user_queue_count[chat_id] > 0:
                self.user_queue_count[chat_id] -= 1
            new_count = self.user_queue_count[chat_id]
            
            # Clean up zero counts to prevent memory leaks
            if new_count == 0:
                del self.user_queue_count[chat_id]
            
            self.logger.debug(f"User {chat_id} now has {new_count} jobs in queue")
            return new_count
    
    def get_user_queue_count(self, chat_id: int) -> int:
        """Get current number of queued jobs for a user."""
        with self._rate_limit_lock:
            return self.user_queue_count[chat_id]

    async def queue_audio_job(self, chat_id: int, message_id: int, audio: AudioMessage, processing_msg_id: int) -> tuple[bool, Optional[str]]:
        """Queue an audio processing job. Returns (success, error_message)."""
        if self.is_queue_full():
            return False, f"Sorry, the processing queue is full ({self.max_queue_size} files). Please try again later."

        # Check rate limit
        if not self.can_user_submit_job(chat_id):
            current_count = self.get_user_queue_count(chat_id)
            return False, f"You have reached the maximum limit of {self.max_jobs_per_user_in_queue} audio files in the queue. Please wait for your current jobs to complete. (Currently in queue: {current_count})"

        # Determine filename
        file_name = audio.file_name
        if not file_name:
            if audio.mime_type == "audio/ogg":
                file_name = "voice_message.ogg"
            else:
                file_name = f"audio_file_{audio.file_unique_id}.{audio.mime_type.split('/')[1]}"

        # Increment user queue count before queueing
        self.increment_user_queue_count(chat_id)

        job = Job(
            chat_id=chat_id,
            message_id=message_id,
            file_id=audio.file_id,
            file_name=file_name,
            mime_type=audio.mime_type,
            file_size=audio.file_size,
            processing_msg_id=processing_msg_id,
        )

        await self.processing_queue.put(job)
        self.logger.info(f"Job added to queue for chat {job.chat_id}. Queue size: {self.processing_queue.qsize()}")
        return True, None

    async def complete_job(self, job: Job):
        """Mark a job as complete and decrement user queue count."""
        self.decrement_user_queue_count(job.chat_id)
        self.logger.info(f"Job completed for user {job.chat_id}")

    async def process_audio_job(self, job: Job, bot: BotProtocol, model) -> bool:
        """Process a single audio job. Returns True if successful, False if failed."""
        try:
            # Check file size before downloading
            if job.file_size > self.max_file_size:
                await bot.edit_message(
                    entity=job.chat_id,
                    message=job.processing_msg_id,
                    text="File is too large. The limit is 2 GB.",
                )
                return False

            await bot.edit_message(
                entity=job.chat_id,
                message=job.processing_msg_id,
                text="Downloading your audio file...",
            )

            # Download file only when ready to process
            self.logger.info(f"Downloading file for {job.file_name}")
            original_message = await bot.get_messages(job.chat_id, ids=job.message_id)

            with tempfile.TemporaryDirectory() as temp_dir:
                file_ext = mimetypes.guess_extension(job.mime_type) or ".ogg"
                temp_path = os.path.join(temp_dir, f"audio{file_ext}")
                await original_message.download_media(temp_path)
                self.logger.info(f"Finished downloading {job.file_name}")

                await bot.edit_message(
                    entity=job.chat_id,
                    message=job.processing_msg_id,
                    text="Analyzing audio duration...",
                )

                if whisper is None:
                    raise ImportError("Whisper not available - install openai-whisper package")
                
                audio = whisper.load_audio(temp_path)
                duration = len(audio) / Config.AUDIO_SAMPLE_RATE  # Convert samples to seconds
                
                # Validate audio has content
                if len(audio) == 0:
                    self.logger.warning(f"Empty audio file: {job.file_name}")
                    await bot.send_message(
                        entity=job.chat_id,
                        message="The audio file appears to be empty or corrupted.",
                        reply_to=job.message_id,
                    )
                    return True
                
                # Check for very short audio
                if duration < Config.MIN_AUDIO_DURATION:
                    self.logger.warning(f"Very short audio file ({duration:.2f}s): {job.file_name}")
                    await bot.send_message(
                        entity=job.chat_id,
                        message=f"The audio file is too short to transcribe (less than {Config.MIN_AUDIO_DURATION} seconds).",
                        reply_to=job.message_id,
                    )
                    return True
                
                estimated_seconds = max(duration / 60 * Config.TRANSCRIPTION_TIME_FACTOR, 2)

                await bot.edit_message(
                    entity=job.chat_id,
                    message=job.processing_msg_id,
                    text=f"Processing your audio. Estimated time: {estimated_seconds:1.0f} seconds.",
                )

                self.logger.info(f"Starting transcription for {job.file_name} (duration: {duration:.2f}s)")
                # Each worker has its own model for thread safety
                result = await asyncio.to_thread(model.transcribe, temp_path)
                transcription = result["text"]
                self.logger.info(f"Finished transcription for {job.file_name}")

            await self._send_transcription_result(job, bot, transcription)
            await self.complete_job(job)
            return True

        except Exception as e:
            self.logger.error(f"Failed processing job for chat {job.chat_id}: {e}", exc_info=True)
            await self._send_error_message(job, bot, e)
            await self.complete_job(job)
            return False

    async def _send_transcription_result(self, job: Job, bot: BotProtocol, transcription: str):
        """Send transcription result to user, splitting into chunks if necessary."""
        header = "Transcription:\n\n"
        max_length = Config.TELEGRAM_MESSAGE_LIMIT

        if not transcription.strip():
            await bot.send_message(
                entity=job.chat_id,
                message="The audio contained no detectable speech.",
                reply_to=job.message_id,
            )
        else:
            # Split into chunks and send
            for i in range(0, len(transcription), max_length - len(header)):
                chunk = transcription[i : i + max_length - len(header)]
                await bot.send_message(
                    entity=job.chat_id,
                    message=f"{header}{chunk}",
                    reply_to=job.message_id,
                )

    async def _send_error_message(self, job: Job, bot: BotProtocol, error: Exception):
        """Send appropriate error message to user based on error type."""
        try:
            # Determine error type for better user messaging
            error_str = str(error).lower()
            if "download" in error_str or "file" in error_str:
                error_msg = "Sorry, failed to download your file. Please try again."
            elif "cannot reshape tensor" in error_str or "tensor of 0 elements" in error_str:
                error_msg = "Sorry, this audio file cannot be processed. It may be too short, corrupted, or in an unsupported format."
            elif "transcribe" in error_str or "whisper" in error_str:
                error_msg = "Sorry, failed to transcribe your audio. The file may be corrupted or in an unsupported format."
            else:
                error_msg = "Sorry, an error occurred while processing your file."
            
            await bot.send_message(
                entity=job.chat_id,
                message=error_msg,
                reply_to=job.message_id,
            )
        except Exception as notify_error:
            self.logger.error(f"Failed to notify user {job.chat_id} about error: {notify_error}")

    async def cleanup_processing_message(self, job: Job, bot: BotProtocol):
        """Clean up the processing status message."""
        try:
            await bot.delete_messages(entity=job.chat_id, message_ids=job.processing_msg_id)
        except Exception:
            pass  # Message might already be deleted or not exist