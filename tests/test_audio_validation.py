import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from bot_core import BotCore, Job, AudioMessage

pytestmark = pytest.mark.asyncio


class TestAudioValidation:
    """Test audio validation and error handling."""

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

    @patch('bot_core.whisper')
    @patch('tempfile.TemporaryDirectory')
    async def test_empty_audio_file(self, mock_tempdir, mock_whisper, bot_core, mock_bot, sample_job):
        """Test handling of empty audio files."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = []  # Empty audio array
        
        result = await bot_core.process_audio_job(sample_job, mock_bot)
        
        assert result is True
        mock_bot.send_message.assert_called_once_with(
            chat_id=sample_job.chat_id,
            text="The audio file appears to be empty or corrupted.",
            reply_to_message_id=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('tempfile.TemporaryDirectory')
    async def test_very_short_audio_file(self, mock_tempdir, mock_whisper, bot_core, mock_bot, sample_job):
        """Test handling of very short audio files."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 800  # 0.05 seconds of audio (800 samples / 16000 Hz)
        
        result = await bot_core.process_audio_job(sample_job, mock_bot)
        
        assert result is True
        mock_bot.send_message.assert_called_once_with(
            chat_id=sample_job.chat_id,
            text="The audio file is too short to transcribe (less than 0.1 seconds).",
            reply_to_message_id=sample_job.message_id
        )

    async def test_tensor_reshape_error_message(self, bot_core, mock_bot, sample_job):
        """Test specific error message for tensor reshape errors."""
        # Create a tensor reshape error
        error = RuntimeError("cannot reshape tensor of 0 elements into shape [1, 0, 8, -1]")
        
        await bot_core._send_error_message(sample_job, mock_bot, error)
        
        mock_bot.send_message.assert_called_once_with(
            chat_id=sample_job.chat_id,
            text="Sorry, this audio file cannot be processed. It may be too short, corrupted, or in an unsupported format.",
            reply_to_message_id=sample_job.message_id
        )

    async def test_tensor_zero_elements_error_message(self, bot_core, mock_bot, sample_job):
        """Test specific error message for zero elements tensor errors."""
        # Create a zero elements error
        error = RuntimeError("tensor of 0 elements cannot be reshaped")
        
        await bot_core._send_error_message(sample_job, mock_bot, error)
        
        mock_bot.send_message.assert_called_once_with(
            chat_id=sample_job.chat_id,
            text="Sorry, this audio file cannot be processed. It may be too short, corrupted, or in an unsupported format.",
            reply_to_message_id=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_tensor_error_during_transcription(self, mock_tempdir, mock_to_thread, mock_whisper,
                                                   bot_core, mock_bot, sample_job):
        """Test handling of tensor errors during actual transcription."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 16000  # 1 second of audio (should pass validation)
        mock_to_thread.side_effect = RuntimeError("cannot reshape tensor of 0 elements into shape [1, 0, 8, -1]")
        
        result = await bot_core.process_audio_job(sample_job, mock_bot)
        
        assert result is False
        mock_bot.send_message.assert_called_once_with(
            chat_id=sample_job.chat_id,
            text="Sorry, this audio file cannot be processed. It may be too short, corrupted, or in an unsupported format.",
            reply_to_message_id=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_successful_processing_with_duration_logging(self, mock_tempdir, mock_to_thread, mock_whisper,
                                                             bot_core, mock_bot, sample_job):
        """Test that duration is properly logged during successful processing."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * (16000 * 5)  # 5 seconds of audio
        mock_to_thread.return_value = {"text": "Test transcription"}
        
        with patch.object(bot_core.logger, 'info') as mock_logger:
            result = await bot_core.process_audio_job(sample_job, mock_bot)
        
        assert result is True
        
        # Check that duration was logged
        log_calls = [call.args[0] for call in mock_logger.call_args_list]
        duration_logs = [log for log in log_calls if "duration:" in log]
        assert len(duration_logs) > 0
        assert "duration: 5.00s" in duration_logs[0]

    @patch('bot_core.whisper')
    @patch('tempfile.TemporaryDirectory')
    async def test_minimum_valid_duration(self, mock_tempdir, mock_whisper, bot_core, mock_bot, sample_job):
        """Test audio with exactly 0.1 seconds (minimum valid duration)."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 1600  # Exactly 0.1 seconds (1600 samples / 16000 Hz)
        
        # This should proceed to transcription (not be rejected)
        with patch('bot_core.asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = {"text": "Short audio"}
            result = await bot_core.process_audio_job(sample_job, mock_bot)
        
        assert result is True
        # Should call transcription, not send error message for being too short
        mock_to_thread.assert_called_once()