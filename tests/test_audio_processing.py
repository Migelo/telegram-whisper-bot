import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from bot_core import BotCore, Job, AudioMessage

pytestmark = pytest.mark.asyncio


class TestAudioProcessing:
    """Test audio processing workflow."""

    @pytest.fixture
    def sample_job(self):
        """Create a sample job for testing."""
        return Job(
            chat_id=12345,
            message_id=1,
            file_id="test_file_123",
            file_name="test_audio.ogg",
            mime_type="audio/ogg",
            file_size=1024 * 1024,
            processing_msg_id=2
        )

    @pytest.fixture
    def large_job(self):
        """Create a job with oversized file."""
        return Job(
            chat_id=12345,
            message_id=1,
            file_id="large_file_456",
            file_name="large_audio.mp3",
            mime_type="audio/mp3",
            file_size=3 * 1024 * 1024 * 1024,  # 3GB - Over 2GB limit
            processing_msg_id=2
        )

    async def test_process_oversized_file_rejected(self, bot_core, mock_bot, large_job):
        """Test that oversized files are rejected during processing."""
        bot_core.model = MagicMock()  # Mock model
        
        result = await bot_core.process_audio_job(large_job, mock_bot, MagicMock())
        
        assert result is False
        mock_bot.edit_message.assert_called_once_with(
            entity=large_job.chat_id,
            message=large_job.processing_msg_id,
            text="File is too large. The limit is 2 GB."
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_successful_audio_processing(self, mock_tempdir, mock_to_thread, mock_whisper, 
                                             bot_core, mock_bot, sample_job):
        """Test successful audio processing workflow."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 16000  # 1 second of audio
        mock_to_thread.return_value = {"text": "Hello world test transcription"}
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is True
        
        # Verify bot interactions
        assert mock_bot.edit_message.call_count >= 3  # Download, analyze, process messages
        mock_bot.send_message.assert_called_once()
        
        # Verify transcription was sent
        send_call = mock_bot.send_message.call_args
        assert send_call[1]['entity'] == sample_job.chat_id
        assert "Transcription:" in send_call[1]['message']
        assert "Hello world test transcription" in send_call[1]['message']

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_empty_transcription(self, mock_tempdir, mock_to_thread, mock_whisper,
                                     bot_core, mock_bot, sample_job):
        """Test handling of audio with no detectable speech."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 16000
        mock_to_thread.return_value = {"text": "   "}  # Empty/whitespace transcription
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is True
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="The audio contained no detectable speech.",
            reply_to=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')  
    @patch('tempfile.TemporaryDirectory')
    async def test_long_transcription_chunked(self, mock_tempdir, mock_to_thread, mock_whisper,
                                            bot_core, mock_bot, sample_job):
        """Test that long transcriptions are properly chunked."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 16000
        
        # Create a very long transcription that will need chunking
        long_text = "This is a test. " * 300  # Should exceed 4096 chars
        mock_to_thread.return_value = {"text": long_text}
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is True
        
        # Should have multiple send_message calls for chunks
        assert mock_bot.send_message.call_count > 1
        
        # Verify all chunks contain header and content
        for call in mock_bot.send_message.call_args_list:
            assert "Transcription:" in call[1]['message']

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    async def test_processing_download_error(self, mock_to_thread, mock_whisper, bot_core, mock_bot, sample_job):
        """Test handling of download errors."""
        bot_core.model = MagicMock()
        mock_whisper.load_audio.side_effect = Exception("Download failed")
        mock_bot.get_messages.side_effect = Exception("Download failed")
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is False
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="Sorry, failed to download your file. Please try again.",
            reply_to=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_processing_transcription_error(self, mock_tempdir, mock_to_thread, mock_whisper,
                                                bot_core, mock_bot, sample_job):
        """Test handling of transcription errors."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 16000
        mock_to_thread.side_effect = Exception("Whisper transcription failed")
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is False
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="Sorry, failed to transcribe your audio. The file may be corrupted or in an unsupported format.",
            reply_to=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_processing_generic_error(self, mock_tempdir, mock_to_thread, mock_whisper,
                                          bot_core, mock_bot, sample_job):
        """Test handling of generic processing errors."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.side_effect = Exception("Generic error")
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is False
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="Sorry, an error occurred while processing your file.",
            reply_to=sample_job.message_id
        )

    async def test_cleanup_processing_message(self, bot_core, mock_bot, sample_job):
        """Test cleanup of processing status message."""
        await bot_core.cleanup_processing_message(sample_job, mock_bot)
        
        mock_bot.delete_messages.assert_called_once_with(
            entity=sample_job.chat_id,
            message_ids=sample_job.processing_msg_id
        )

    async def test_cleanup_processing_message_fails_silently(self, bot_core, mock_bot, sample_job):
        """Test that cleanup failures are handled silently."""
        mock_bot.delete_messages.side_effect = Exception("Delete failed")
        
        # Should not raise exception
        await bot_core.cleanup_processing_message(sample_job, mock_bot)
        
        mock_bot.delete_messages.assert_called_once()

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_duration_estimation(self, mock_tempdir, mock_to_thread, mock_whisper,
                                     bot_core, mock_bot, sample_job):
        """Test audio duration estimation."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * (16000 * 120)  # 2 minutes of audio
        mock_to_thread.return_value = {"text": "Test transcription"}
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is True
        
        # Check that duration estimation message was sent
        estimation_calls = [call for call in mock_bot.edit_message.call_args_list 
                          if "Estimated time:" in str(call)]
        assert len(estimation_calls) > 0
        
        # Should show estimated time (2 minutes * 13 seconds/minute = 26 seconds)
        estimation_call = estimation_calls[0][1]['text']
        assert "26 seconds" in estimation_call