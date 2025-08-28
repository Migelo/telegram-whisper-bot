import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, Voice, Audio, Chat, User, Bot
from telegram.ext import ContextTypes
import main

pytestmark = pytest.mark.asyncio


class TestTelegramHandlers:
    """Test Telegram message handlers and integration."""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram Update object."""
        update = MagicMock(spec=Update)
        update.effective_message = MagicMock(spec=Message)
        update.effective_message.chat_id = 12345
        update.effective_message.message_id = 1
        update.effective_message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Telegram context."""
        return MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    @pytest.fixture
    def mock_voice_message(self, mock_update):
        """Create a mock voice message."""
        voice = MagicMock(spec=Voice)
        voice.file_id = "voice_123"
        voice.file_size = 1024 * 1024
        voice.mime_type = "audio/ogg"
        voice.file_unique_id = "unique_voice_123"
        
        mock_update.effective_message.voice = voice
        mock_update.effective_message.audio = None
        return mock_update

    @pytest.fixture
    def mock_audio_message(self, mock_update):
        """Create a mock audio message."""
        audio = MagicMock(spec=Audio)
        audio.file_id = "audio_456"
        audio.file_size = 2 * 1024 * 1024
        audio.mime_type = "audio/mp3"
        audio.file_name = "song.mp3"
        audio.file_unique_id = "unique_audio_456"
        
        mock_update.effective_message.voice = None
        mock_update.effective_message.audio = audio
        return mock_update

    async def test_start_command(self, mock_update, mock_context):
        """Test /start command handler."""
        # Make reply_text async
        mock_update.message.reply_text = AsyncMock()
        
        await main.start(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once_with(
            "Hi! Send me a voice message or audio file (up to 20 MB), and I'll transcribe it for you."
        )

    async def test_help_command(self, mock_update, mock_context):
        """Test /help command handler."""
        # Make reply_text async
        mock_update.message.reply_text = AsyncMock()
        
        await main.help_command(mock_update, mock_context)
        
        expected_text = (
            "Send me any voice message or audio file, and I'll convert it to text. "
            f"I can process up to {main.NUM_WORKERS} files at the same time. If the queue is full, please wait."
        )
        mock_update.message.reply_text.assert_called_once_with(expected_text)

    async def test_handle_voice_message(self, mock_voice_message, mock_context):
        """Test handling of voice messages."""
        with patch.object(main.processing_queue, 'qsize', return_value=5), \
             patch.object(main.processing_queue, 'put', new_callable=AsyncMock) as mock_put:
            
            await main.handle_audio(mock_voice_message, mock_context)
            
            # Should queue the job
            mock_put.assert_called_once()
            
            # Should send position feedback
            mock_voice_message.effective_message.reply_text.assert_called_once()
            reply_text = mock_voice_message.effective_message.reply_text.call_args[0][0]
            assert "Position: 6" in reply_text

    async def test_handle_audio_message(self, mock_audio_message, mock_context):
        """Test handling of audio file messages."""
        with patch.object(main.processing_queue, 'qsize', return_value=0), \
             patch.object(main.processing_queue, 'put', new_callable=AsyncMock) as mock_put:
            
            await main.handle_audio(mock_audio_message, mock_context)
            
            # Should queue the job
            mock_put.assert_called_once()
            job = mock_put.call_args[0][0]
            
            # Verify job properties
            assert job.chat_id == 12345
            assert job.message_id == 1
            assert job.file_id == "audio_456"
            assert job.file_name == "song.mp3"
            assert job.mime_type == "audio/mp3"
            assert job.file_size == 2 * 1024 * 1024

    async def test_handle_oversized_file_rejection(self, mock_audio_message, mock_context):
        """Test rejection of oversized files."""
        # Make the file too large
        mock_audio_message.effective_message.audio.file_size = 30 * 1024 * 1024
        
        with patch.object(main.processing_queue, 'put', new_callable=AsyncMock) as mock_put:
            await main.handle_audio(mock_audio_message, mock_context)
            
            # Should not queue the job
            mock_put.assert_not_called()
            
            # Should send rejection message
            mock_audio_message.effective_message.reply_text.assert_called_once_with(
                "File is too large. The limit is 256 MB."
            )

    async def test_handle_queue_full_rejection(self, mock_voice_message, mock_context):
        """Test rejection when queue is full."""
        with patch.object(main.processing_queue, 'qsize', return_value=main.MAX_QUEUE_SIZE), \
             patch.object(main.processing_queue, 'put', new_callable=AsyncMock) as mock_put:
            
            await main.handle_audio(mock_voice_message, mock_context)
            
            # Should not queue the job
            mock_put.assert_not_called()
            
            # Should send queue full message
            mock_voice_message.effective_message.reply_text.assert_called_once()
            reply_text = mock_voice_message.effective_message.reply_text.call_args[0][0]
            assert "queue is full" in reply_text.lower()
            assert str(main.MAX_QUEUE_SIZE) in reply_text

    async def test_handle_voice_filename_generation(self, mock_voice_message, mock_context):
        """Test filename generation for voice messages."""
        with patch.object(main.processing_queue, 'qsize', return_value=0), \
             patch.object(main.processing_queue, 'put', new_callable=AsyncMock) as mock_put:
            
            await main.handle_audio(mock_voice_message, mock_context)
            
            job = mock_put.call_args[0][0]
            assert job.file_name == "voice_message.ogg"

    async def test_handle_audio_without_filename(self, mock_audio_message, mock_context):
        """Test filename generation for audio without filename."""
        # Remove filename
        mock_audio_message.effective_message.audio.file_name = None
        
        with patch.object(main.processing_queue, 'qsize', return_value=0), \
             patch.object(main.processing_queue, 'put', new_callable=AsyncMock) as mock_put:
            
            await main.handle_audio(mock_audio_message, mock_context)
            
            job = mock_put.call_args[0][0]
            assert job.file_name == "audio_file_unique_audio_456.mp3"

    async def test_handle_neither_voice_nor_audio(self, mock_update, mock_context):
        """Test handling of messages that are neither voice nor audio."""
        # Set both voice and audio to None
        mock_update.effective_message.voice = None
        mock_update.effective_message.audio = None
        
        with patch.object(main.processing_queue, 'put', new_callable=AsyncMock) as mock_put:
            await main.handle_audio(mock_update, mock_context)
            
            # Should not queue anything or send messages
            mock_put.assert_not_called()
            mock_update.effective_message.reply_text.assert_not_called()

    @patch('main.whisper.load_model')
    async def test_worker_model_loading(self, mock_load_model):
        """Test that workers load their own Whisper models."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        mock_bot = AsyncMock(spec=Bot)
        
        # Clear any existing models
        main.models.clear()
        
        with patch.object(main.processing_queue, 'get', new_callable=AsyncMock) as mock_get:
            # Make get() raise an exception to exit the worker loop
            mock_get.side_effect = Exception("Exit worker loop")
            
            try:
                await main.worker("TestWorker", mock_bot)
            except Exception:
                pass  # Expected exit
            
            # Verify model was loaded for this worker
            mock_load_model.assert_called_once_with(main.WHISPER_MODEL)
            assert "TestWorker" in main.models
            assert main.models["TestWorker"] == mock_model

    @patch('main.whisper.load_model')
    async def test_worker_model_loading_failure(self, mock_load_model):
        """Test worker behavior when model loading fails."""
        mock_load_model.side_effect = Exception("Model loading failed")
        mock_bot = AsyncMock(spec=Bot)
        
        # Clear any existing models
        main.models.clear()
        
        # Worker should exit when model loading fails
        result = await main.worker("FailWorker", mock_bot)
        
        # Should attempt to load model
        mock_load_model.assert_called_once_with(main.WHISPER_MODEL)
        # Should not create model entry
        assert "FailWorker" not in main.models

    async def test_post_init_creates_workers(self):
        """Test that post_init creates the correct number of worker tasks."""
        mock_app = MagicMock()
        mock_bot = AsyncMock(spec=Bot)
        mock_app.bot = mock_bot
        
        with patch('main.asyncio.create_task') as mock_create_task:
            await main.post_init(mock_app)
            
            # Should create NUM_WORKERS tasks
            assert mock_create_task.call_count == main.NUM_WORKERS
            
            # Each call should be a coroutine (can't easily inspect worker names)
            for call_args in mock_create_task.call_args_list:
                assert len(call_args[0]) == 1  # One positional argument
                # The argument should be a coroutine
                assert hasattr(call_args[0][0], '__await__')

    async def test_job_creation_properties(self, mock_audio_message, mock_context):
        """Test that Job objects are created with correct properties."""
        with patch.object(main.processing_queue, 'qsize', return_value=3), \
             patch.object(main.processing_queue, 'put', new_callable=AsyncMock) as mock_put, \
             patch.object(mock_audio_message.effective_message, 'reply_text', new_callable=AsyncMock) as mock_reply:
            
            # Mock the reply_text to return a message with an ID
            mock_message = MagicMock()
            mock_message.message_id = 999
            mock_reply.return_value = mock_message
            
            await main.handle_audio(mock_audio_message, mock_context)
            
            job = mock_put.call_args[0][0]
            
            # Verify all job properties
            assert isinstance(job, main.Job)
            assert job.chat_id == 12345
            assert job.message_id == 1
            assert job.file_id == "audio_456"
            assert job.file_name == "song.mp3"
            assert job.mime_type == "audio/mp3"
            assert job.file_size == 2 * 1024 * 1024
            assert job.processing_msg_id == 999