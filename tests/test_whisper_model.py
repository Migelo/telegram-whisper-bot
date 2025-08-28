import pytest
from unittest.mock import patch, MagicMock
from bot_core import BotCore

pytestmark = pytest.mark.asyncio


class TestWhisperModel:
    """Test Whisper model loading and configuration."""

    @patch('bot_core.whisper.load_model')
    def test_load_whisper_model_success(self, mock_load_model):
        """Test successful Whisper model loading."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        
        bot_core = BotCore(whisper_model="base")
        result = bot_core.load_whisper_model()
        
        assert result is True
        assert bot_core.model == mock_model
        mock_load_model.assert_called_once_with("base")

    @patch('bot_core.whisper.load_model')
    def test_load_whisper_model_failure(self, mock_load_model):
        """Test Whisper model loading failure."""
        mock_load_model.side_effect = Exception("Model loading failed")
        
        bot_core = BotCore(whisper_model="base")
        result = bot_core.load_whisper_model()
        
        assert result is False
        assert bot_core.model is None

    @patch('bot_core.whisper.load_model')
    def test_load_different_model_sizes(self, mock_load_model):
        """Test loading different Whisper model sizes."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        
        for model_size in ["tiny", "base", "small", "medium", "large"]:
            bot_core = BotCore(whisper_model=model_size)
            result = bot_core.load_whisper_model()
            
            assert result is True
            mock_load_model.assert_called_with(model_size)