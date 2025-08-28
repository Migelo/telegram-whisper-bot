import os
import tempfile
import asyncio
import logging
import mimetypes
from dataclasses import dataclass
from typing import Optional, Protocol, Any

try:
    import whisper
except ImportError:
    whisper = None


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
    async def get_file(self, file_id: str) -> Any:
        ...
    
    async def send_message(self, chat_id: int, text: str, reply_to_message_id: Optional[int] = None) -> Any:
        ...
    
    async def edit_message_text(self, chat_id: int, message_id: int, text: str) -> Any:
        ...
    
    async def delete_message(self, chat_id: int, message_id: int) -> Any:
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
                 max_file_size: int = 20 * 1024 * 1024,
                 max_queue_size: int = 100):
        self.whisper_model = whisper_model
        self.num_workers = num_workers
        self.max_file_size = max_file_size
        self.max_queue_size = max_queue_size
        self.processing_queue = asyncio.Queue()
        self.model = None
        self.logger = logging.getLogger(__name__)
        
    def load_whisper_model(self):
        """Load the Whisper model."""
        if whisper is None:
            self.logger.error("Whisper not available - install openai-whisper package")
            return False
        
        try:
            self.model = whisper.load_model(self.whisper_model)
            self.logger.info(f"Whisper model '{self.whisper_model}' loaded.")
            return True
        except Exception as e:
            self.logger.error(f"Could not load Whisper model: {e}")
            return False

    def validate_audio_file(self, audio: AudioMessage) -> Optional[str]:
        """Validate audio file size. Returns error message if invalid, None if valid."""
        if audio.file_size > self.max_file_size:
            return "File is too large. The limit is 256 MB."
        return None

    def is_queue_full(self) -> bool:
        """Check if the processing queue is at capacity."""
        return self.processing_queue.qsize() >= self.max_queue_size

    def get_queue_position(self) -> int:
        """Get the current queue size (position for next item)."""
        return self.processing_queue.qsize()

    async def queue_audio_job(self, chat_id: int, message_id: int, audio: AudioMessage, processing_msg_id: int) -> bool:
        """Queue an audio processing job. Returns True if queued, False if rejected."""
        if self.is_queue_full():
            return False

        # Determine filename
        file_name = audio.file_name
        if not file_name:
            if audio.mime_type == "audio/ogg":
                file_name = "voice_message.ogg"
            else:
                file_name = f"audio_file_{audio.file_unique_id}.{audio.mime_type.split('/')[1]}"

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
        return True

    async def process_audio_job(self, job: Job, bot: BotProtocol) -> bool:
        """Process a single audio job. Returns True if successful, False if failed."""
        try:
            # Check file size before downloading
            if job.file_size > self.max_file_size:
                await bot.edit_message_text(
                    chat_id=job.chat_id,
                    message_id=job.processing_msg_id,
                    text="File is too large. The limit is 256 MB.",
                )
                return False

            await bot.edit_message_text(
                chat_id=job.chat_id,
                message_id=job.processing_msg_id,
                text="Downloading your audio file...",
            )

            # Download file only when ready to process
            self.logger.info(f"Downloading file for {job.file_name}")
            file = await bot.get_file(job.file_id)

            with tempfile.TemporaryDirectory() as temp_dir:
                file_ext = mimetypes.guess_extension(job.mime_type) or ".ogg"
                temp_path = os.path.join(temp_dir, f"audio{file_ext}")
                await file.download_to_drive(temp_path)
                self.logger.info(f"Finished downloading {job.file_name}")

                await bot.edit_message_text(
                    chat_id=job.chat_id,
                    message_id=job.processing_msg_id,
                    text="Analyzing audio duration...",
                )

                if whisper is None:
                    raise ImportError("Whisper not available - install openai-whisper package")
                
                audio = whisper.load_audio(temp_path)
                duration = len(audio) / 16000  # Convert samples to seconds
                
                # Validate audio has content
                if len(audio) == 0:
                    self.logger.warning(f"Empty audio file: {job.file_name}")
                    await bot.send_message(
                        chat_id=job.chat_id,
                        text="The audio file appears to be empty or corrupted.",
                        reply_to_message_id=job.message_id,
                    )
                    return True
                
                # Check for very short audio (less than 0.1 seconds)
                if duration < 0.1:
                    self.logger.warning(f"Very short audio file ({duration:.2f}s): {job.file_name}")
                    await bot.send_message(
                        chat_id=job.chat_id,
                        text="The audio file is too short to transcribe (less than 0.1 seconds).",
                        reply_to_message_id=job.message_id,
                    )
                    return True
                
                estimated_seconds = max(duration / 60 * 13, 2)

                await bot.edit_message_text(
                    chat_id=job.chat_id,
                    message_id=job.processing_msg_id,
                    text=f"Processing your audio. Estimated time: {estimated_seconds:1.0f} seconds.",
                )

                self.logger.info(f"Starting transcription for {job.file_name} (duration: {duration:.2f}s)")
                # Each BotCore instance should have its own model for thread safety
                result = await asyncio.to_thread(self.model.transcribe, temp_path)
                transcription = result["text"]
                self.logger.info(f"Finished transcription for {job.file_name}")

            await self._send_transcription_result(job, bot, transcription)
            return True

        except Exception as e:
            self.logger.error(f"Failed processing job for chat {job.chat_id}: {e}", exc_info=True)
            await self._send_error_message(job, bot, e)
            return False

    async def _send_transcription_result(self, job: Job, bot: BotProtocol, transcription: str):
        """Send transcription result to user, splitting into chunks if necessary."""
        header = "Transcription:\n\n"
        max_length = 4096  # Telegram's message character limit

        if not transcription.strip():
            await bot.send_message(
                chat_id=job.chat_id,
                text="The audio contained no detectable speech.",
                reply_to_message_id=job.message_id,
            )
        else:
            # Split into chunks and send
            for i in range(0, len(transcription), max_length - len(header)):
                chunk = transcription[i : i + max_length - len(header)]
                await bot.send_message(
                    chat_id=job.chat_id,
                    text=f"{header}{chunk}",
                    reply_to_message_id=job.message_id,
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
                chat_id=job.chat_id,
                text=error_msg,
                reply_to_message_id=job.message_id,
            )
        except Exception as notify_error:
            self.logger.error(f"Failed to notify user {job.chat_id} about error: {notify_error}")

    async def cleanup_processing_message(self, job: Job, bot: BotProtocol):
        """Clean up the processing status message."""
        try:
            await bot.delete_message(chat_id=job.chat_id, message_id=job.processing_msg_id)
        except Exception:
            pass  # Message might already be deleted or not exist