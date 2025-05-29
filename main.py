import os
import tempfile
import asyncio
import logging
import mimetypes
from dataclasses import dataclass

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import whisper

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
NUM_WORKERS = int(os.getenv("NUM_WORKERS", "2"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_FILE_SIZE_MB = 20 * 1024 * 1024

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

try:
    model = whisper.load_model(WHISPER_MODEL)
    logger.info(f"Whisper model '{WHISPER_MODEL}' loaded.")
except Exception as e:
    logger.error(f"Could not load Whisper model: {e}")
    exit()


@dataclass
class Job:
    chat_id: int
    message_id: int
    file_id: str
    file_name: str
    mime_type: str
    processing_msg_id: int


processing_queue = asyncio.Queue()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hi! Send me a voice message or audio file (up to 20 MB), and I'll transcribe it for you."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Send me any voice message or audio file, and I'll convert it to text. "
        f"I can process up to {NUM_WORKERS} files at the same time. If the queue is full, please wait."
    )


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming audio, adds it to the queue."""
    message = update.effective_message

    if message.voice:
        audio = message.voice
        file_name = "voice_message.ogg"
    elif message.audio:
        audio = message.audio
        file_name = (
            audio.file_name
            or f"audio_file_{audio.file_unique_id}.{audio.mime_type.split('/')[1]}"
        )
    else:
        return

    if audio.file_size > MAX_FILE_SIZE_MB:
        await message.reply_text("File is too large. The limit is 256 MB.")
        return

    # Give immediate feedback that the file is queued
    queue_size = processing_queue.qsize()
    processing_msg = await message.reply_text(
        f"Your file has been added to the queue. Position: {queue_size + 1}"
    )

    # Create a lightweight job object with the correctly determined filename
    job = Job(
        chat_id=message.chat_id,
        message_id=message.message_id,
        file_id=audio.file_id,
        file_name=file_name,
        mime_type=audio.mime_type,
        processing_msg_id=processing_msg.message_id,
    )

    await processing_queue.put(job)
    logger.info(
        f"Job added to queue for chat {job.chat_id}. Queue size: {processing_queue.qsize()}"
    )


async def worker(name: str, bot: Bot):
    """The worker function that processes jobs from the queue."""
    while True:
        try:
            job = await processing_queue.get()
            logger.info(f"Worker '{name}' picked up job for chat {job.chat_id}")

            await bot.edit_message_text(
                chat_id=job.chat_id,
                message_id=job.processing_msg_id,
                text="Downloading and processing your audio...",
            )

            file = await bot.get_file(job.file_id)

            with tempfile.TemporaryDirectory() as temp_dir:
                file_ext = mimetypes.guess_extension(job.mime_type)

                if not file_ext:
                    file_ext = ".ogg"

                temp_path = os.path.join(temp_dir, f"audio{file_ext}")
                await file.download_to_drive(temp_path)

                audio = whisper.load_audio(temp_path)
                duration = len(audio) / 16000  # Convert samples to seconds
                estimated_seconds = max(duration / 60 * 13, 2)

                await bot.edit_message_text(
                    chat_id=job.chat_id,
                    message_id=job.processing_msg_id,
                    text=f"Processing your audio. Estimated time: {estimated_seconds:1.0f} seconds.",
                )

                # --- 2. Run the blocking transcription in a separate thread ---
                logger.info(
                    f"Worker '{name}' starting transcription for {job.file_name}"
                )
                result = await asyncio.to_thread(model.transcribe, temp_path)
                transcription = result["text"]
                logger.info(
                    f"Worker '{name}' finished transcription for {job.file_name}"
                )

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

        except Exception as e:
            logger.error(
                f"Worker '{name}' failed on job for chat {job.chat_id}: {e}",
                exc_info=True,
            )
            try:
                # Try to notify the user about the error
                await bot.send_message(
                    chat_id=job.chat_id,
                    text="Sorry, an error occurred while processing your file.",
                    reply_to_message_id=job.message_id,
                )
            except Exception as notify_error:
                logger.error(
                    f"Failed to notify user {job.chat_id} about error: {notify_error}"
                )

        finally:
            if "job" in locals():
                try:
                    await bot.delete_message(
                        chat_id=job.chat_id, message_id=job.processing_msg_id
                    )
                except Exception:
                    pass
                processing_queue.task_done()


async def post_init(application: Application):
    """Create worker tasks after the application is initialized."""
    bot = application.bot
    for i in range(NUM_WORKERS):
        asyncio.create_task(worker(f"Worker-{i + 1}", bot))
    logger.info(f"Started {NUM_WORKERS} worker tasks.")


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")

    application = (
        Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    logger.info("Bot is starting... Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
