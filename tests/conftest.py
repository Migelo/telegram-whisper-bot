import pytest
from unittest.mock import AsyncMock, MagicMock
from bot_core import AudioMessage, BotCore, Job


@pytest.fixture
def mock_bot():
    """Mock Bot object for testing."""
    bot = AsyncMock()
    
    # Mock file object with download_to_drive method
    mock_file = AsyncMock()
    mock_file.download_to_drive = AsyncMock()
    bot.get_file.return_value = mock_file
    
    # Mock message responses
    mock_message = MagicMock()
    mock_message.message_id = 123
    bot.send_message.return_value = mock_message
    bot.edit_message.return_value = mock_message
    bot.delete_message.return_value = None
    
    return bot


@pytest.fixture
def mock_whisper_model():
    """Mock Whisper model for testing."""
    model = MagicMock()
    model.transcribe.return_value = {"text": "This is a test transcription."}
    return model


@pytest.fixture
def bot_core():
    """BotCore instance with test configuration."""
    return BotCore(
        whisper_model="base",
        num_workers=2,
        max_file_size=20 * 1024 * 1024,
        max_queue_size=100
    )


@pytest.fixture
def sample_audio():
    """Sample audio message for testing."""
    return AudioMessage(
        file_id="test_file_123",
        file_size=1024 * 1024,  # 1MB
        mime_type="audio/ogg",
        file_name="test_audio.ogg",
        file_unique_id="unique_123"
    )


@pytest.fixture
def sample_jobs():
    """Sample jobs for concurrency testing."""
    return [
        Job(
            chat_id=12345 + i,
            message_id=i,
            file_id=f"test_file_{i}",
            file_name=f"test_audio_{i}.ogg",
            mime_type="audio/ogg",
            file_size=1024 * 1024,
            processing_msg_id=i + 100
        )
        for i in range(5)
    ]


@pytest.fixture
def large_audio():
    """Large audio file for testing size limits."""
    return AudioMessage(
        file_id="large_file_456",
        file_size=25 * 1024 * 1024,  # 25MB (over limit)
        mime_type="audio/mp3",
        file_name="large_audio.mp3",
        file_unique_id="unique_456"
    )


@pytest.fixture
def voice_message():
    """Voice message without filename."""
    return AudioMessage(
        file_id="voice_789",
        file_size=512 * 1024,  # 512KB
        mime_type="audio/ogg",
        file_name=None,
        file_unique_id="unique_789"
    )


@pytest.fixture
def rate_limited_bot_core():
    """BotCore instance with rate limiting for testing."""
    return BotCore(
        whisper_model="base",
        num_workers=2,
        max_file_size=20 * 1024 * 1024,
        max_queue_size=10,
        max_jobs_per_user_in_queue=2
    )


@pytest.fixture
def multiple_users():
    """Multiple user IDs for testing rate limiting across users."""
    return [12345, 67890, 11111, 22222, 33333]


@pytest.fixture
def test_job():
    """Standard test job for validation and error testing."""
    return Job(
        chat_id=12345, message_id=1, file_id="test_file_123", file_name="test_audio.ogg",
        mime_type="audio/ogg", file_size=1024 * 1024, processing_msg_id=2
    )


@pytest.fixture
def mock_whisper_setup():
    """Standard whisper mock setup for most tests."""
    def _setup(bot_core, mock_tempdir, mock_whisper, audio_data=None, transcription="Test transcription"):
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        if audio_data is not None:
            mock_whisper.load_audio.return_value = audio_data
        else:
            mock_whisper.load_audio.return_value = [0] * 16000  # 1 second default
        return {"text": transcription}
    return _setup