import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telethon.tl.types import Message, Document, DocumentAttributeAudio, DocumentAttributeFilename
from telethon import events
import main

pytestmark = pytest.mark.asyncio


class TestTelegramHandlers:
    """Test Telegram message handlers and integration."""

    @pytest.fixture
    def mock_event(self):
        """Create a mock Telethon event object."""
        event = MagicMock(spec=events.NewMessage.Event)
        event.message = MagicMock(spec=Message)
        event.message.id = 1
        event.chat_id = 12345
        event.respond = AsyncMock()
        
        # Add client mock for edit_message calls
        event.client = AsyncMock()
        event.client.edit_message = AsyncMock()
        
        return event

    @pytest.fixture
    def mock_voice_event(self, mock_event):
        """Create a mock voice message event."""
        document = MagicMock(spec=Document)
        document.id = 123
        document.size = 1024 * 1024
        document.mime_type = "audio/ogg"
        document.file_name = None
        
        mock_event.message.media = MagicMock()
        mock_event.message.media.document = document
        return mock_event

    @pytest.fixture
    def mock_audio_event(self, mock_event):
        """Create a mock audio message event."""
        document = MagicMock(spec=Document)
        document.id = 456
        document.size = 2 * 1024 * 1024
        document.mime_type = "audio/mp3"
        document.file_name = "song.mp3"
        
        mock_event.message.media = MagicMock()
        mock_event.message.media.document = document
        return mock_event

    async def test_start_command(self, mock_event):
        """Test /start command handler."""
        await main.start(mock_event)
        
        mock_event.respond.assert_called_once_with(
            "Hi! Send me a voice message or audio file (up to 2 GB), and I'll transcribe it for you."
        )

    async def test_help_command(self, mock_event):
        """Test /help command handler."""
        await main.help_command(mock_event)
        
        expected_text = (
            "Send me any voice message or audio file, and I'll convert it to text. "
            f"I can process up to {main.NUM_WORKERS} files at the same time. If the queue is full, please wait."
        )
        mock_event.respond.assert_called_once_with(expected_text)

    async def test_handle_voice_message(self, mock_voice_event):
        """Test handling of voice messages."""
        with patch.object(main.bot_core, 'validate_audio_file', return_value=None), \
             patch.object(main.bot_core, 'queue_audio_job', return_value=(True, None)) as mock_queue, \
             patch.object(main.bot_core, 'get_queue_position', return_value=1):
            
            await main.handle_audio(mock_voice_event)
            
            # Should queue the job
            mock_queue.assert_called_once()
            
            # Should send initial queueing message and then update with position
            assert mock_voice_event.respond.call_count == 1
            assert mock_voice_event.client.edit_message.call_count == 1

    async def test_handle_audio_message(self, mock_audio_event):
        """Test handling of audio file messages."""
        with patch.object(main.bot_core, 'validate_audio_file', return_value=None), \
             patch.object(main.bot_core, 'queue_audio_job', return_value=(True, None)) as mock_queue, \
             patch.object(main.bot_core, 'get_queue_position', return_value=1):
            
            await main.handle_audio(mock_audio_event)
            
            # Should queue the job
            mock_queue.assert_called_once()
            
            # Should send initial queueing message and then update with position
            assert mock_audio_event.respond.call_count == 1
            assert mock_audio_event.client.edit_message.call_count == 1

    async def test_handle_oversized_file_rejection(self, mock_audio_event):
        """Test rejection of oversized files."""
        # Make the file too large
        mock_audio_event.message.media.document.size = 3 * 1024 * 1024 * 1024  # 3GB
        
        with patch.object(main.bot_core, 'queue_audio_job', new_callable=AsyncMock) as mock_queue:
            await main.handle_audio(mock_audio_event)
            
            # Should not queue the job
            mock_queue.assert_not_called()
            
            # Should send rejection message
            mock_audio_event.respond.assert_called_once_with(
                "File is too large. The limit is 2 GB."
            )

    async def test_handle_queue_full_rejection(self, mock_voice_event):
        """Test rejection when queue is full."""
        queue_full_error = f"Sorry, the processing queue is full ({main.MAX_QUEUE_SIZE} files). Please try again later."
        
        with patch.object(main.bot_core, 'validate_audio_file', return_value=None), \
             patch.object(main.bot_core, 'queue_audio_job', return_value=(False, queue_full_error)) as mock_queue:
            
            # Mock the processing message
            mock_voice_event.respond.return_value.id = 999
            
            await main.handle_audio(mock_voice_event)
            
            # Should attempt to queue the job
            mock_queue.assert_called_once()
            
            # Should send queueing message then edit with error
            mock_voice_event.respond.assert_called_once()
            mock_voice_event.client.edit_message.assert_called_once()

    async def test_handle_voice_filename_generation(self, mock_voice_event):
        """Test filename generation for voice messages."""
        with patch.object(main.bot_core, 'validate_audio_file', return_value=None), \
             patch.object(main.bot_core, 'queue_audio_job', return_value=(True, None)) as mock_queue, \
             patch.object(main.bot_core, 'get_queue_position', return_value=1):
            
            await main.handle_audio(mock_voice_event)
            
            # Should queue the job
            mock_queue.assert_called_once()
            
            # Check that the audio message was created with correct filename
            call_args = mock_queue.call_args
            audio_message = call_args[1]['audio']
            assert audio_message.file_name == "audio_123.ogg"

    async def test_handle_audio_without_filename(self, mock_audio_event):
        """Test filename generation for audio without filename."""
        # Remove filename
        mock_audio_event.message.media.document.file_name = None
        
        with patch.object(main.bot_core, 'validate_audio_file', return_value=None), \
             patch.object(main.bot_core, 'queue_audio_job', return_value=(True, None)) as mock_queue, \
             patch.object(main.bot_core, 'get_queue_position', return_value=1):
            
            await main.handle_audio(mock_audio_event)
            
            # Should queue the job
            mock_queue.assert_called_once()
            
            # Check that the audio message was created with correct filename
            call_args = mock_queue.call_args
            audio_message = call_args[1]['audio']
            assert audio_message.file_name == "audio_456.mp3"

    async def test_handle_neither_voice_nor_audio(self, mock_event):
        """Test handling of messages that are neither voice nor audio."""
        # Set media to None
        mock_event.message.media = None
        
        with patch.object(main.bot_core, 'queue_audio_job', new_callable=AsyncMock) as mock_queue:
            await main.handle_audio(mock_event)
            
            # Should not queue anything or send messages
            mock_queue.assert_not_called()
            mock_event.respond.assert_not_called()

    async def test_worker_model_loading(self):
        """Test that workers load their own Whisper models."""
        from telethon import TelegramClient
        
        with patch('main.whisper') as mock_whisper:
            mock_model = MagicMock()
            mock_whisper.load_model.return_value = mock_model
            mock_client = AsyncMock(spec=TelegramClient)
            
            # Mock bot_core.get_worker_model to return our mock model
            with patch.object(main.bot_core, 'get_worker_model', return_value=mock_model) as mock_get_model, \
                 patch.object(main.bot_core.processing_queue, 'get', new_callable=AsyncMock) as mock_get:
                # Make get() raise an exception to exit the worker loop immediately
                mock_get.side_effect = asyncio.CancelledError("Exit worker loop")
                
                with pytest.raises(asyncio.CancelledError):
                    await main.worker("TestWorker", mock_client)
                
                # Verify model was requested for this worker
                mock_get_model.assert_called_once_with("TestWorker")

    async def test_worker_model_loading_failure(self):
        """Test worker behavior when model loading fails."""
        from telethon import TelegramClient
        
        with patch('main.whisper') as mock_whisper:
            mock_whisper.load_model.side_effect = Exception("Model loading failed")
            mock_client = AsyncMock(spec=TelegramClient)
            
            # Mock bot_core.get_worker_model to return None (failure)
            with patch.object(main.bot_core, 'get_worker_model', return_value=None) as mock_get_model:
                # Worker should exit when model loading fails
                result = await main.worker("FailWorker", mock_client)
                
                # Should attempt to get model for this worker
                mock_get_model.assert_called_once_with("FailWorker")

    async def test_start_workers_creates_workers(self):
        """Test that start_workers creates the correct number of worker tasks."""
        from telethon import TelegramClient
        
        mock_client = AsyncMock(spec=TelegramClient)
        
        with patch('main.asyncio.create_task') as mock_create_task:
            await main.start_workers(mock_client)
            
            # Should create NUM_WORKERS tasks
            assert mock_create_task.call_count == main.NUM_WORKERS
            
            # Each call should be a coroutine (can't easily inspect worker names)
            for call_args in mock_create_task.call_args_list:
                assert len(call_args[0]) == 1  # One positional argument
                # The argument should be a coroutine
                assert hasattr(call_args[0][0], '__await__')

    async def test_job_creation_properties(self, mock_audio_event):
        """Test that Job objects are created with correct properties."""
        with patch.object(main.bot_core, 'validate_audio_file', return_value=None), \
             patch.object(main.bot_core, 'queue_audio_job', return_value=(True, None)) as mock_queue, \
             patch.object(main.bot_core, 'get_queue_position', return_value=1):
            
            # Mock the respond to return a message with an ID
            mock_message = MagicMock()
            mock_message.id = 999
            mock_audio_event.respond.return_value = mock_message
            
            await main.handle_audio(mock_audio_event)
            
            # Should queue the job
            mock_queue.assert_called_once()
            
            # Check that the audio message was created with correct properties
            call_args = mock_queue.call_args
            audio_message = call_args[1]['audio']
            
            assert call_args[1]['chat_id'] == 12345
            assert call_args[1]['message_id'] == 1
            assert audio_message.file_id == "456"
            assert audio_message.file_name == "song.mp3"
            assert audio_message.mime_type == "audio/mp3"
            assert audio_message.file_size == 2 * 1024 * 1024
            assert call_args[1]['processing_msg_id'] == 999