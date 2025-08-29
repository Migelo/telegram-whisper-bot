import pytest
from unittest.mock import patch, MagicMock
from bot_core import BotCore

# pytestmark = pytest.mark.asyncio  # Not needed for synchronous tests


class TestWhisperModel:
    """Test Whisper model loading and configuration."""

    def test_get_worker_model_success(self):
        """Test successful Whisper model loading."""
        with patch('bot_core.whisper') as mock_whisper:
            mock_model = MagicMock()
            mock_whisper.load_model.return_value = mock_model
            
            bot_core = BotCore(whisper_model="base")
            result = bot_core.get_worker_model("test_worker")
            
            assert result == mock_model
            assert bot_core.models["test_worker"] == mock_model
            mock_whisper.load_model.assert_called_once_with("base")

    def test_get_worker_model_failure(self):
        """Test Whisper model loading failure."""
        with patch('bot_core.whisper') as mock_whisper:
            mock_whisper.load_model.side_effect = Exception("Model loading failed")
            
            bot_core = BotCore(whisper_model="base")
            result = bot_core.get_worker_model("test_worker")
            
            assert result is None
            assert "test_worker" not in bot_core.models

    def test_load_different_model_sizes(self):
        """Test loading different Whisper model sizes."""
        with patch('bot_core.whisper') as mock_whisper:
            mock_model = MagicMock()
            mock_whisper.load_model.return_value = mock_model
            
            for model_size in ["tiny", "base", "small", "medium", "large"]:
                bot_core = BotCore(whisper_model=model_size)
                result = bot_core.get_worker_model("test_worker")
                
                assert result == mock_model
                mock_whisper.load_model.assert_called_with(model_size)