import pytest
import asyncio
import mimetypes
from unittest.mock import AsyncMock, MagicMock, patch
from bot_core import BotCore, Job, AudioMessage

pytestmark = pytest.mark.asyncio


class TestAudioFormats:
    """Test handling of various audio formats and MIME types."""

    @pytest.fixture
    def sample_formats(self):
        """Common audio formats to test."""
        return [
            ("audio/ogg", "voice.ogg", ".ogg"),
            ("audio/mpeg", "song.mp3", ".mp3"),
            ("audio/mp4", "audio.m4a", ".m4a"),
            ("audio/wav", "sound.wav", ".wav"),
            ("audio/x-wav", "sound.wav", ".wav"),
            ("audio/flac", "music.flac", ".flac"),
            ("audio/aac", "audio.aac", ".aac"),
            ("audio/webm", "voice.webm", ".webm"),
            ("audio/x-m4a", "audio.m4a", ".m4a"),
        ]

    @pytest.fixture
    def uncommon_formats(self):
        """Less common or edge case formats."""
        return [
            ("audio/amr", "voice.amr", ".amr"),
            ("audio/3gpp", "voice.3gp", ".3gp"),
            ("audio/x-ms-wma", "song.wma", ".wma"),
            ("audio/opus", "voice.opus", ".opus"),
        ]

    def create_audio_message(self, mime_type, filename, file_size=1024*1024):
        """Helper to create AudioMessage with specific format."""
        return AudioMessage(
            file_id=f"file_{mime_type.replace('/', '_')}",
            file_size=file_size,
            mime_type=mime_type,
            file_name=filename,
            file_unique_id=f"unique_{mime_type.replace('/', '_')}"
        )

    def create_job_for_format(self, mime_type, filename):
        """Helper to create Job with specific format."""
        return Job(
            chat_id=12345,
            message_id=1,
            file_id=f"file_{mime_type.replace('/', '_')}",
            file_name=filename,
            mime_type=mime_type,
            file_size=1024*1024,
            processing_msg_id=2
        )

    async def test_validate_common_audio_formats(self, bot_core, sample_formats):
        """Test that common audio formats are accepted."""
        for mime_type, filename, _ in sample_formats:
            audio = self.create_audio_message(mime_type, filename)
            error = bot_core.validate_audio_file(audio)
            assert error is None, f"Format {mime_type} should be valid"

    async def test_queue_audio_with_various_formats(self, bot_core, sample_formats):
        """Test queueing audio with different formats."""
        for i, (mime_type, filename, _) in enumerate(sample_formats):
            audio = self.create_audio_message(mime_type, filename)
            # Use different chat_id for each format to avoid rate limiting
            success, error = await bot_core.queue_audio_job(12345 + i, 1, audio, 2)
            assert success is True, f"Should queue {mime_type} successfully, got error: {error}"

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    @patch('mimetypes.guess_extension')
    async def test_file_extension_mapping(self, mock_guess_ext, mock_tempdir, mock_to_thread, 
                                        mock_whisper, bot_core, mock_bot, sample_formats):
        """Test that MIME types map to correct file extensions."""
        for mime_type, filename, expected_ext in sample_formats:
            # Setup mocks
            bot_core.model = MagicMock()
            mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
            mock_whisper.load_audio.return_value = [0] * 16000
            mock_to_thread.return_value = {"text": "Test transcription"}
            mock_guess_ext.return_value = expected_ext
            
            job = self.create_job_for_format(mime_type, filename)
            result = await bot_core.process_audio_job(job, mock_bot, MagicMock())
            
            assert result is True
            # Verify mimetypes.guess_extension was called with the MIME type
            mock_guess_ext.assert_called_with(mime_type)

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    @patch('mimetypes.guess_extension')
    async def test_unknown_mime_type_fallback(self, mock_guess_ext, mock_tempdir, mock_to_thread,
                                            mock_whisper, bot_core, mock_bot):
        """Test handling of unknown MIME types."""
        # Setup mocks
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 16000
        mock_to_thread.return_value = {"text": "Test transcription"}
        mock_guess_ext.return_value = None  # Unknown MIME type
        
        job = self.create_job_for_format("audio/unknown", "mystery.xyz")
        result = await bot_core.process_audio_job(job, mock_bot, MagicMock())
        
        assert result is True
        # Should fall back to .ogg extension
        mock_guess_ext.assert_called_with("audio/unknown")

    async def test_filename_generation_for_different_formats(self, bot_core, sample_formats):
        """Test filename generation for various formats."""
        for i, (mime_type, _, expected_ext) in enumerate(sample_formats):
            # Test with no filename provided
            audio = AudioMessage(
                file_id=f"test_{i}",
                file_size=1024*1024,
                mime_type=mime_type,
                file_name=None,
                file_unique_id=f"unique_{i}"
            )
            
            # Use different chat_id for each format to avoid rate limiting
            success, _ = await bot_core.queue_audio_job(12345 + i, 1, audio, 2)
            assert success is True
            
            # Get the job from the queue to check filename
            job = await bot_core.processing_queue.get()
            
            if mime_type == "audio/ogg":
                assert job.file_name == "voice_message.ogg"
            else:
                expected_filename = f"audio_file_unique_{i}.{mime_type.split('/')[1]}"
                assert job.file_name == expected_filename

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_format_specific_processing(self, mock_tempdir, mock_to_thread, mock_whisper,
                                            bot_core, mock_bot, uncommon_formats):
        """Test processing of less common audio formats."""
        for mime_type, filename, _ in uncommon_formats:
            # Setup mocks
            bot_core.model = MagicMock()
            mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
            mock_whisper.load_audio.return_value = [0] * 16000  # 1 second
            mock_to_thread.return_value = {"text": f"Transcription for {mime_type}"}
            
            job = self.create_job_for_format(mime_type, filename)
            result = await bot_core.process_audio_job(job, mock_bot, MagicMock())
            
            assert result is True
            
            # Verify transcription was sent
            mock_bot.send_message.assert_called()
            send_call = mock_bot.send_message.call_args
            assert f"Transcription for {mime_type}" in send_call[1]['message']
            
            # Reset mock for next iteration
            mock_bot.reset_mock()

    async def test_format_validation_edge_cases(self, bot_core):
        """Test edge cases in format validation."""
        test_cases = [
            # Valid cases
            ("audio/ogg", "voice.ogg", True),
            ("audio/mpeg", "song.mp3", True),
            ("AUDIO/WAV", "sound.wav", True),  # Case insensitive
            
            # Invalid cases (still accepted - validation is size-based, not format-based)
            ("text/plain", "document.txt", True),  # Wrong type, but size is OK
            ("application/octet-stream", "binary.bin", True),  # Generic binary
        ]
        
        for mime_type, filename, should_be_valid in test_cases:
            audio = self.create_audio_message(mime_type, filename)
            error = bot_core.validate_audio_file(audio)
            
            if should_be_valid:
                assert error is None, f"{mime_type} should be accepted"
            else:
                assert error is not None, f"{mime_type} should be rejected"

    @patch('bot_core.whisper')
    async def test_whisper_load_audio_called_correctly(self, mock_whisper, bot_core, mock_bot):
        """Test that whisper.load_audio is called with correct file path."""
        formats_to_test = [
            ("audio/wav", "test.wav"),
            ("audio/mp3", "test.mp3"),
            ("audio/flac", "test.flac"),
        ]
        
        for mime_type, filename in formats_to_test:
            with patch('tempfile.TemporaryDirectory') as mock_tempdir, \
                 patch('bot_core.asyncio.to_thread') as mock_to_thread:
                
                # Setup mocks
                bot_core.model = MagicMock()
                mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
                mock_whisper.load_audio.return_value = [0] * 16000
                mock_to_thread.return_value = {"text": "Test"}
                
                job = self.create_job_for_format(mime_type, filename)
                await bot_core.process_audio_job(job, mock_bot, MagicMock())
                
                # Verify whisper.load_audio was called with the temp path
                mock_whisper.load_audio.assert_called()
                called_path = mock_whisper.load_audio.call_args[0][0]
                assert called_path.startswith("/tmp/test/audio")
                
                # Reset mocks for next iteration
                mock_whisper.reset_mock()

    async def test_large_files_different_formats(self, bot_core, sample_formats):
        """Test that large file validation works across formats."""
        for mime_type, filename, _ in sample_formats:
            # Create oversized file
            audio = self.create_audio_message(mime_type, filename, 25 * 1024 * 1024)
            error = bot_core.validate_audio_file(audio)
            assert error is not None, f"Large {mime_type} file should be rejected"
            assert "too large" in error.lower()

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_format_specific_error_handling(self, mock_tempdir, mock_to_thread, mock_whisper,
                                                 bot_core, mock_bot):
        """Test error handling for different formats."""
        error_formats = [
            ("audio/corrupted", "bad.ogg"),
            ("audio/invalid", "invalid.mp3"),
        ]
        
        for mime_type, filename in error_formats:
            # Setup mocks to simulate processing error
            bot_core.model = MagicMock()
            mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
            mock_whisper.load_audio.side_effect = Exception(f"Cannot process {mime_type}")
            
            job = self.create_job_for_format(mime_type, filename)
            result = await bot_core.process_audio_job(job, mock_bot, MagicMock())
            
            assert result is False
            mock_bot.send_message.assert_called_with(
                entity=job.chat_id,
                message="Sorry, an error occurred while processing your file.",
                reply_to=job.message_id
            )
            
            # Reset mocks
            mock_bot.reset_mock()
            mock_whisper.reset_mock()

    async def test_voice_message_mime_type_handling(self, bot_core):
        """Test specific handling of Telegram voice message format."""
        # Telegram voice messages are typically audio/ogg
        voice_audio = AudioMessage(
            file_id="voice_123",
            file_size=512 * 1024,
            mime_type="audio/ogg",
            file_name=None,  # Voice messages don't have filenames
            file_unique_id="unique_voice"
        )
        
        success, _ = await bot_core.queue_audio_job(12345, 1, voice_audio, 2)
        assert success is True
        
        # Check generated filename
        job = await bot_core.processing_queue.get()
        assert job.file_name == "voice_message.ogg"
        assert job.mime_type == "audio/ogg"