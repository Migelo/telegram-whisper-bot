import os
import asyncio
import logging

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
from bot_core import BotCore, AudioMessage, Job, Config

try:
    import whisper
except ImportError:
    whisper = None

WHISPER_MODEL = os.getenv("WHISPER_MODEL", Config.DEFAULT_WHISPER_MODEL)
NUM_WORKERS = int(os.getenv("NUM_WORKERS", str(Config.DEFAULT_NUM_WORKERS)))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
MAX_FILE_SIZE_MB = Config.DEFAULT_MAX_FILE_SIZE
MAX_QUEUE_SIZE = Config.DEFAULT_MAX_QUEUE_SIZE
MAX_JOBS_PER_USER_IN_QUEUE = int(os.getenv("MAX_JOBS_PER_USER_IN_QUEUE", str(Config.DEFAULT_MAX_JOBS_PER_USER)))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create bot core instance
bot_core = BotCore(
    whisper_model=WHISPER_MODEL,
    num_workers=NUM_WORKERS,
    max_file_size=MAX_FILE_SIZE_MB,
    max_queue_size=MAX_QUEUE_SIZE,
    max_jobs_per_user_in_queue=MAX_JOBS_PER_USER_IN_QUEUE
)


# processing_queue is now managed by bot_core


async def start(event):
    """Send a message when the command /start is issued."""
    await event.respond(
        "Hi! Send me a voice message or audio file (up to 2 GB), and I'll transcribe it for you."
    )


async def help_command(event):
    """Send a message when the command /help is issued."""
    await event.respond(
        "Send me any voice message or audio file, and I'll convert it to text. "
        f"I can process up to {NUM_WORKERS} files at the same time. If the queue is full, please wait."
    )


async def handle_audio(event):
    """Handles incoming audio, adds it to the queue."""
    message = event.message

    # Check if message has media (voice or audio)
    if not message.media:
        return
        
    # Handle voice messages and audio files
    if hasattr(message.media, 'document') and message.media.document:
        document = message.media.document
        # Check if it's audio/voice by mime_type
        if not document.mime_type.startswith('audio/'):
            return
        
        file_size = document.size
        file_name = getattr(document, 'file_name', None) or f"audio_{document.id}.{document.mime_type.split('/')[1]}"
        mime_type = document.mime_type
        file_id = document.id
    else:
        return

    # Create audio message object
    audio_message = AudioMessage(
        file_id=str(file_id),
        file_size=file_size,
        mime_type=mime_type,
        file_name=file_name,
        file_unique_id=str(file_id)
    )

    # Validate file size
    error_msg = bot_core.validate_audio_file(audio_message)
    if error_msg:
        await event.respond(error_msg)
        return

    # Give immediate feedback that the file is being queued
    processing_msg = await event.respond("Queueing your audio file...")

    # Try to queue the job with rate limiting
    success, error_message = await bot_core.queue_audio_job(
        chat_id=event.chat_id,
        message_id=message.id,
        audio=audio_message,
        processing_msg_id=processing_msg.id
    )

    if not success:
        await event.client.edit_message(
            entity=event.chat_id,
            message=processing_msg.id,
            text=error_message
        )
        return

    # Update message with queue position
    queue_position = bot_core.get_queue_position()
    await event.client.edit_message(
        entity=event.chat_id,
        message=processing_msg.id,
        text=f"Your file has been queued for processing. Position: {queue_position}"
    )



async def worker(name: str, client: TelegramClient):
    """The worker function that processes jobs from the queue."""
    # Get model for this worker
    model = bot_core.get_worker_model(name)
    if not model:
        logger.error(f"Failed to load model for {name}")
        return
    
    while True:
        job = None
        try:
            job = await bot_core.processing_queue.get()
            logger.info(f"Worker '{name}' picked up job for chat {job.chat_id}")

            # Process the job using bot_core
            success = await bot_core.process_audio_job(job, client, model)
            logger.info(f"Worker '{name}' {'completed' if success else 'failed'} job for chat {job.chat_id}")

        except Exception as e:
            logger.error(f"Worker '{name}' encountered error: {e}", exc_info=True)
            if job:
                await bot_core.complete_job(job)

        finally:
            if job:
                try:
                    await bot_core.cleanup_processing_message(job, client)
                except Exception:
                    pass
                bot_core.processing_queue.task_done()


async def start_workers(client: TelegramClient):
    """Create worker tasks after the client is initialized."""
    for i in range(NUM_WORKERS):
        asyncio.create_task(worker(f"Worker-{i + 1}", client))
    logger.info(f"Started {NUM_WORKERS} worker tasks.")


async def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")
    if not API_ID or not API_HASH:
        raise ValueError("API_ID and API_HASH environment variables must be set.")

    # Create the client and connect
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=TELEGRAM_BOT_TOKEN)
    
    # Start worker tasks
    await start_workers(client)
    
    # Register event handlers
    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await start(event)
    
    @client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        await help_command(event)
    
    @client.on(events.NewMessage)
    async def audio_handler(event):
        # Only handle messages with media (audio/voice)
        if event.message.media:
            await handle_audio(event)
    
    logger.info("Bot is starting... Press Ctrl+C to stop.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
