import os
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import whisper
import asyncio
import mimetypes

# Initialize Whisper model
model = whisper.load_model("base")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text('Hi! Send me a voice message or audio file, and I\'ll transcribe it for you.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text('Send me any voice message or audio file, and I\'ll convert it to text using Whisper.')

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages and audio files."""
    # Send a processing message
    processing_msg = await update.message.reply_text("Processing your audio... Please wait.")
    
    try:
        # Get the audio file
        if update.message.voice:
            file = await update.message.voice.get_file()
            file_extension = '.ogg'
        else:
            file = await update.message.audio.get_file()
            # Get mime_type from the audio message, not the file
            mime_type = update.message.audio.mime_type
            file_extension = mimetypes.guess_extension(mime_type) or '.ogg'
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_audio:
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
        await update.message.reply_text(f"Sorry, an error occurred: {str(e)}")
    
    
    finally:
        # Clean up the temporary file
        if 'temp_audio' in locals():
            os.unlink(temp_audio.name)
        # Delete the processing message
        await processing_msg.delete()

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token("***REMOVED***").build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()