import pytest
from unittest.mock import AsyncMock, MagicMock
from bot_core import AudioMessage, BotCore


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
    bot.edit_message_text.return_value = mock_message
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