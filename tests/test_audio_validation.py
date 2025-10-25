import pytest
from unittest.mock import MagicMock, patch
from bot_core import Job

pytestmark = pytest.mark.asyncio


class TestAudioValidation:
    """Test audio validation and error handling."""

    def create_test_job(self):
        """Create a sample job for testing."""
        return Job(
            chat_id=12345, message_id=1, file_id="test_file_123", file_name="test_audio.ogg",
            mime_type="audio/ogg", file_size=1024 * 1024, processing_msg_id=2
        )

    def setup_audio_mocks(self, bot_core, mock_tempdir, mock_whisper, audio_data):
        """Standard setup for audio validation tests."""
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = audio_data

    @patch('bot_core.whisper')
    @patch('tempfile.TemporaryDirectory')
    async def test_empty_audio_file(self, mock_tempdir, mock_whisper, bot_core, mock_bot):
        """Test handling of empty audio files."""
        sample_job = self.create_test_job()
        self.setup_audio_mocks(bot_core, mock_tempdir, mock_whisper, [])
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is True
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="The audio file appears to be empty or corrupted.",
            reply_to=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('tempfile.TemporaryDirectory')
    async def test_very_short_audio_file(self, mock_tempdir, mock_whisper, bot_core, mock_bot):
        """Test handling of very short audio files."""
        sample_job = self.create_test_job()
        self.setup_audio_mocks(bot_core, mock_tempdir, mock_whisper, [0] * 800)  # 0.05 seconds
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is True
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="The audio file is too short to transcribe (less than 1 seconds).",
            reply_to=sample_job.message_id
        )

    async def test_tensor_reshape_error_message(self, bot_core, mock_bot):
        """Test specific error message for tensor reshape errors."""
        sample_job = self.create_test_job()
        error = RuntimeError("cannot reshape tensor of 0 elements into shape [1, 0, 8, -1]")
        
        await bot_core._send_error_message(sample_job, mock_bot, error)
        
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="Sorry, this audio file cannot be processed. It may be too short, corrupted, or in an unsupported format.",
            reply_to=sample_job.message_id
        )

    async def test_tensor_zero_elements_error_message(self, bot_core, mock_bot):
        """Test specific error message for zero elements tensor errors."""
        sample_job = self.create_test_job()
        error = RuntimeError("tensor of 0 elements cannot be reshaped")
        
        await bot_core._send_error_message(sample_job, mock_bot, error)
        
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="Sorry, this audio file cannot be processed. It may be too short, corrupted, or in an unsupported format.",
            reply_to=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_tensor_error_during_transcription(self, mock_tempdir, mock_to_thread, mock_whisper, bot_core, mock_bot):
        """Test handling of tensor errors during actual transcription."""
        sample_job = self.create_test_job()
        self.setup_audio_mocks(bot_core, mock_tempdir, mock_whisper, [0] * 16000)
        mock_to_thread.side_effect = RuntimeError("cannot reshape tensor of 0 elements into shape [1, 0, 8, -1]")
        
        result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is False
        mock_bot.send_message.assert_called_once_with(
            entity=sample_job.chat_id,
            message="Sorry, this audio file cannot be processed. It may be too short, corrupted, or in an unsupported format.",
            reply_to=sample_job.message_id
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_successful_processing_with_duration_logging(self, mock_tempdir, mock_to_thread, mock_whisper, bot_core, mock_bot):
        """Test that duration is properly logged during successful processing."""
        sample_job = self.create_test_job()
        self.setup_audio_mocks(bot_core, mock_tempdir, mock_whisper, [0] * (16000 * 5))
        mock_to_thread.return_value = {"text": "Test transcription"}
        
        with patch.object(bot_core.logger, 'info') as mock_logger:
            result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is True
        
        # Check that duration was logged
        log_calls = [call.args[0] for call in mock_logger.call_args_list]
        duration_logs = [log for log in log_calls if "duration:" in log]
        assert len(duration_logs) > 0
        assert "duration: 5.00s" in duration_logs[0]

    @patch('bot_core.whisper')
    @patch('tempfile.TemporaryDirectory')
    async def test_minimum_valid_duration(self, mock_tempdir, mock_whisper, bot_core, mock_bot):
        """Test audio with exactly 1 second (minimum valid duration)."""
        sample_job = self.create_test_job()
        self.setup_audio_mocks(bot_core, mock_tempdir, mock_whisper, [0] * 16000)  # 1 second
        
        with patch('bot_core.asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = {"text": "Short audio"}
            result = await bot_core.process_audio_job(sample_job, mock_bot, MagicMock())
        
        assert result is True
        mock_to_thread.assert_called_once()