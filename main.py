import os
import tempfile
from telethon import TelegramClient, events
import whisper
import asyncio
import mimetypes

# Initialize Whisper model
model = whisper.load_model(os.getenv("WHISPER_MODEL"))

# Create a queue for processing audio files
processing_queue = asyncio.Queue()

# Maximum file size (256 MB in bytes)
MAX_FILE_SIZE = 256 * 1024 * 1024

# Telegram API credentials
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")

# Create the Telegram client
client = TelegramClient('session_name', api_id, api_hash)

async def start(event):
    """Send a message when the command /start is issued."""
    await event.respond('Hi! Send me a voice message or audio file (up to 256 MB), and I\'ll transcribe it for you.')

async def help_command(event):
    """Send a message when the command /help is issued."""
    await event.respond('Send me any voice message or audio file (up to 256 MB), and I\'ll convert it to text using Whisper. If there are other files being processed, yours will be queued.')

async def process_queue():
    """Background task to process the queue."""
    while True:
        try:
            # Get the next item from the queue
            event, processing_msg = await processing_queue.get()
            
            try:
                # Process the audio file
                await process_audio(event, processing_msg)
            except Exception as e:
                await event.respond(f"Sorry, an error occurred: {str(e)}")
            finally:
                # Mark the task as done
                processing_queue.task_done()
        except Exception as e:
            print(f"Error in queue processor: {str(e)}")
            await asyncio.sleep(1)  # Prevent tight loop in case of errors

async def handle_audio(event):
    """Handle incoming voice messages and audio files."""
    # Check file size
    file_size = 0
    if event.message.voice:
        file_size = event.message.voice.file.size
    elif event.message.audio:
        file_size = event.message.audio.size
    
    if file_size > MAX_FILE_SIZE:
        await event.respond(f"File size exceeds the maximum limit of 256 MB. Please send a smaller file.")
        return
    
    # Get message duration
    duration = 0
    if event.message.voice:
        duration = event.message.voice.attributes[0].duration
    elif event.message.audio:
        duration = event.message.audio.attributes[0].duration

    # Send initial processing message
    queue_size = processing_queue.qsize()
    if queue_size > 0:
        processing_msg = await event.respond(
            f"Your file has been queued. There are {queue_size} files ahead of yours. Please wait..."
        )
    else:
        processing_msg = await event.respond(f"Processing your audio. Estimated time: {duration / 60 * 13:1.0f} seconds.")
    
    # Add to queue
    await processing_queue.put((event, processing_msg))

async def process_audio(event, processing_msg):
    """Process a single audio file."""
    try:
        # Get the audio file
        if event.message.voice:
            file = await client.download_media(event.message.voice)
            file_extension = '.ogg'
        else:
            file = await client.download_media(event.message.audio)
            mime_type = event.message.audio.mime_type
            file_extension = mimetypes.guess_extension(mime_type) or '.ogg'
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_audio:
            # Print the file path
            print(f"Downloading audio to: {temp_audio.name}")
            # Download the voice message
            temp_audio.write(file)
            
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
            await event.respond(f"{header}{chunk}")
            
    except Exception as e:
        raise e
    
    finally:
        # Clean up the temporary file
        if 'temp_audio' in locals():
            os.unlink(temp_audio.name)
        # Delete the processing message
        await processing_msg.delete()

async def main():
    """Start the bot."""
    # Connect to Telegram
    await client.start()

    # Add handlers
    client.add_event_handler(start, events.NewMessage(pattern='/start'))
    client.add_event_handler(help_command, events.NewMessage(pattern='/help'))
    client.add_event_handler(handle_audio, events.NewMessage(func=lambda e: e.message.voice or e.message.audio))

    # Create and start the queue processor as a background task
    asyncio.create_task(process_queue())

    # Run the client
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
