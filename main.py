import os
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import whisper
import asyncio
import mimetypes

# Initialize Whisper model
model = whisper.load_model(os.getenv("WHISPER_MODEL"))

# Create a queue for processing audio files
processing_queue = asyncio.Queue()

# Maximum file size (256 MB in bytes)
MAX_FILE_SIZE = 256 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text('Hi! Send me a voice message or audio file (up to 256 MB), and I\'ll transcribe it for you.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text('Send me any voice message or audio file (up to 256 MB), and I\'ll convert it to text using Whisper. If there are other files being processed, yours will be queued.')

async def process_queue():
    """Background task to process the queue."""
    while True:
        try:
            # Get the next item from the queue
            update, context, processing_msg = await processing_queue.get()
            
            try:
                # Process the audio file
                await process_audio(update, context, processing_msg)
            except Exception as e:
                await update.message.reply_text(f"Sorry, an error occurred: {str(e)}")
            finally:
                # Mark the task as done
                processing_queue.task_done()
        except Exception as e:
            print(f"Error in queue processor: {str(e)}")
            await asyncio.sleep(1)  # Prevent tight loop in case of errors

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages and audio files."""
    # Check file size
    file_size = 0
    if update.message.voice:
        file_size = update.message.voice.file_size
    elif update.message.audio:
        file_size = update.message.audio.file_size
    
    if file_size > MAX_FILE_SIZE:
        await update.message.reply_text(f"File size exceeds the maximum limit of 256 MB. Please send a smaller file.")
        return
    
    # Get message duration
    duration = 0
    if update.message.voice:
        duration = update.message.voice.duration
    elif update.message.audio:
        duration = update.message.audio.duration

    # Send initial processing message
    queue_size = processing_queue.qsize()
    if queue_size > 0:
        processing_msg = await update.message.reply_text(
            f"Your file has been queued. There are {queue_size} files ahead of yours. Please wait..."
        )
    else:
        processing_msg = await update.message.reply_text(f"Processing your audio. Estimated time: {duration / 60 * 13:1.0f} seconds.")
    
    # Add to queue
    await processing_queue.put((update, context, processing_msg))

async def process_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, processing_msg):
    """Process a single audio file."""
    try:
        # Get the audio file
        if update.message.voice:
            file = await update.message.voice.get_file()
            file_extension = '.ogg'
        else:
            file = await update.message.audio.get_file()
            mime_type = update.message.audio.mime_type
            file_extension = mimetypes.guess_extension(mime_type) or '.ogg'
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_audio:
            # Print the file path
            print(f"Downloading audio to: {temp_audio.name}")
            # Download the voice message
            await file.download_to_drive(temp_audio.name)
            
            # Transcribe the audio
            result = model.transcribe(temp_audio.name)
            transcription = result["text"]
            
        # Split transcription into chunks of 4000 characters
        max_length = 4000
        chunks = [transcription[i:i+max_length] 
                 for i in range(0, len(transcription), max_length)]
        
        # Send each chunk as a separate message
        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                header = f"Part {i}/{len(chunks)}:\n\n"
            else:
                header = "Transcription:\n\n"
            await update.message.reply_text(f"{header}{chunk}")
            
    except Exception as e:
        raise e
    
    finally:
        # Clean up the temporary file
        if 'temp_audio' in locals():
            os.unlink(temp_audio.name)
        # Delete the processing message
        await processing_msg.delete()

def main():
    """Start the bot."""
    # Create the Application
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("No API token provided. Please set the TELEGRAM_BOT_TOKEN environment variable.")
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    # Create and start the queue processor as a background task
    async def start_queue_processor(app):
        asyncio.create_task(process_queue())

    # Add the startup action
    application.post_init = start_queue_processor

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
