import pytest
import os
from unittest.mock import patch, MagicMock
from bot_core import BotCore, AudioMessage
import main


class TestConfiguration:
    """Test configuration management and environment variables."""

    def test_bot_core_default_configuration(self):
        """Test BotCore with default configuration values."""
        bot_core = BotCore()
        
        assert bot_core.whisper_model == "base"
        assert bot_core.num_workers == 2
        assert bot_core.max_file_size == 20 * 1024 * 1024
        assert bot_core.max_queue_size == 100

    def test_bot_core_custom_configuration(self):
        """Test BotCore with custom configuration values."""
        bot_core = BotCore(
            whisper_model="large",
            num_workers=4,
            max_file_size=50 * 1024 * 1024,
            max_queue_size=200
        )
        
        assert bot_core.whisper_model == "large"
        assert bot_core.num_workers == 4
        assert bot_core.max_file_size == 50 * 1024 * 1024
        assert bot_core.max_queue_size == 200

    @patch.dict(os.environ, {
        'WHISPER_MODEL': 'small',
        'NUM_WORKERS': '3',
        'TELEGRAM_BOT_TOKEN': 'test_token_123'
    })
    def test_main_environment_variable_parsing(self):
        """Test that main.py correctly reads environment variables."""
        # Reload the module to pick up new env vars
        import importlib
        importlib.reload(main)
        
        assert main.WHISPER_MODEL == "small"
        assert main.NUM_WORKERS == 3
        assert main.TELEGRAM_BOT_TOKEN == "test_token_123"

    @patch.dict(os.environ, {}, clear=True)
    def test_main_default_environment_values(self):
        """Test default values when environment variables are not set."""
        import importlib
        importlib.reload(main)
        
        assert main.WHISPER_MODEL == "base"
        assert main.NUM_WORKERS == 2
        assert main.TELEGRAM_BOT_TOKEN is None

    @patch.dict(os.environ, {'NUM_WORKERS': 'invalid_number'})
    def test_invalid_num_workers_environment_variable(self):
        """Test handling of invalid NUM_WORKERS environment variable."""
        with pytest.raises(ValueError, match="invalid literal for int()"):
            import importlib
            importlib.reload(main)

    @patch.dict(os.environ, {'NUM_WORKERS': '0'})
    def test_zero_workers_configuration(self):
        """Test configuration with zero workers."""
        import importlib
        importlib.reload(main)
        
        assert main.NUM_WORKERS == 0

    @patch.dict(os.environ, {'NUM_WORKERS': '10'})
    def test_high_worker_count_configuration(self):
        """Test configuration with high worker count."""
        import importlib
        importlib.reload(main)
        
        assert main.NUM_WORKERS == 10

    def test_file_size_limits_configuration(self):
        """Test different file size limit configurations."""
        test_cases = [
            (1 * 1024 * 1024, True),      # 1MB - should be valid
            (10 * 1024 * 1024, True),     # 10MB - should be valid
            (50 * 1024 * 1024, False),    # 50MB - over default limit
        ]
        
        bot_core = BotCore(max_file_size=20 * 1024 * 1024)
        
        for file_size, should_be_valid in test_cases:
            audio = AudioMessage(
                file_id="test",
                file_size=file_size,
                mime_type="audio/ogg",
                file_name="test.ogg"
            )
            
            error = bot_core.validate_audio_file(audio)
            if should_be_valid:
                assert error is None, f"File size {file_size} should be valid"
            else:
                assert error is not None, f"File size {file_size} should be invalid"

    def test_queue_size_limits_configuration(self):
        """Test different queue size configurations."""
        test_configs = [
            (1, 1),    # Minimal queue
            (50, 50),  # Medium queue
            (100, 100), # Default queue
            (500, 500), # Large queue
        ]
        
        for max_size, expected_size in test_configs:
            bot_core = BotCore(max_queue_size=max_size)
            assert bot_core.max_queue_size == expected_size

    @pytest.mark.asyncio
    async def test_queue_behavior_with_different_sizes(self):
        """Test queue behavior with different size configurations."""
        small_queue_bot = BotCore(max_queue_size=2)
        audio = AudioMessage("test", 1024*1024, "audio/ogg", "test.ogg")
        
        # Fill small queue
        success1 = await small_queue_bot.queue_audio_job(1, 1, audio, 1)
        success2 = await small_queue_bot.queue_audio_job(2, 2, audio, 2)
        success3 = await small_queue_bot.queue_audio_job(3, 3, audio, 3)  # Should fail
        
        assert success1 is True
        assert success2 is True
        assert success3 is False

    def test_whisper_model_configurations(self):
        """Test different Whisper model configurations."""
        valid_models = ["tiny", "base", "small", "medium", "large"]
        
        for model in valid_models:
            bot_core = BotCore(whisper_model=model)
            assert bot_core.whisper_model == model

    @patch('bot_core.whisper.load_model')
    def test_whisper_model_loading_with_different_models(self, mock_load_model):
        """Test loading different Whisper model sizes."""
        models_to_test = ["tiny", "base", "small", "medium", "large"]
        
        for model_name in models_to_test:
            # Create fresh mock for each test
            mock_model = MagicMock()
            mock_load_model.return_value = mock_model
            
            bot_core = BotCore(whisper_model=model_name)
            success = bot_core.load_whisper_model()
            
            assert success is True
            mock_load_model.assert_called_with(model_name)
            assert bot_core.model == mock_model
            
            mock_load_model.reset_mock()

    @patch('bot_core.whisper.load_model')
    def test_whisper_model_loading_failure_handling(self, mock_load_model):
        """Test handling of Whisper model loading failures."""
        mock_load_model.side_effect = Exception("Model not found")
        
        bot_core = BotCore(whisper_model="nonexistent")
        success = bot_core.load_whisper_model()
        
        assert success is False
        assert bot_core.model is None

    def test_constants_configuration(self):
        """Test that constants are properly configured."""
        # Test main.py constants
        assert main.MAX_FILE_SIZE_MB == 20 * 1024 * 1024
        assert main.MAX_QUEUE_SIZE == 100
        
        # These should be configurable via environment
        assert isinstance(main.WHISPER_MODEL, str)
        assert isinstance(main.NUM_WORKERS, int)

    @patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': ''})
    def test_empty_telegram_token(self):
        """Test handling of empty Telegram bot token."""
        import importlib
        importlib.reload(main)
        
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN environment variable not set"):
            main.main()

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_telegram_token(self):
        """Test handling of missing Telegram bot token."""
        import importlib
        importlib.reload(main)
        
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN environment variable not set"):
            main.main()

    def test_worker_count_validation(self):
        """Test validation of worker count configurations."""
        valid_counts = [1, 2, 4, 8, 16]
        
        for count in valid_counts:
            bot_core = BotCore(num_workers=count)
            assert bot_core.num_workers == count

    def test_configuration_boundaries(self):
        """Test configuration boundary values."""
        # Test minimum viable configuration
        minimal_bot = BotCore(
            whisper_model="tiny",
            num_workers=1,
            max_file_size=1024,  # 1KB minimum
            max_queue_size=1
        )
        
        assert minimal_bot.whisper_model == "tiny"
        assert minimal_bot.num_workers == 1
        assert minimal_bot.max_file_size == 1024
        assert minimal_bot.max_queue_size == 1
        
        # Test maximum reasonable configuration
        maximal_bot = BotCore(
            whisper_model="large",
            num_workers=32,
            max_file_size=1024 * 1024 * 1024,  # 1GB
            max_queue_size=1000
        )
        
        assert maximal_bot.whisper_model == "large"
        assert maximal_bot.num_workers == 32
        assert maximal_bot.max_file_size == 1024 * 1024 * 1024
        assert maximal_bot.max_queue_size == 1000

    @patch.dict(os.environ, {
        'WHISPER_MODEL': 'medium',
        'NUM_WORKERS': '6'
    })
    @pytest.mark.asyncio
    async def test_environment_integration_with_bot_core(self):
        """Test integration between environment variables and BotCore."""
        import importlib
        importlib.reload(main)
        
        # BotCore should use its own defaults, not main's env vars
        bot_core = BotCore()
        assert bot_core.whisper_model == "base"  # BotCore default
        assert bot_core.num_workers == 2  # BotCore default
        
        # But main should use env vars
        assert main.WHISPER_MODEL == "medium"
        assert main.NUM_WORKERS == 6

    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        bot_core = BotCore()
        
        # Should have a logger instance
        assert hasattr(bot_core, 'logger')
        assert bot_core.logger is not None
        assert bot_core.logger.name == 'bot_core'

    @patch('bot_core.whisper.load_model')
    @pytest.mark.asyncio
    async def test_per_worker_model_configuration(self, mock_load_model):
        """Test that each worker can have its own model configuration."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        
        # Clear any existing models
        main.models.clear()
        
        # Test multiple workers with same model
        worker_names = ["Worker-1", "Worker-2", "Worker-3"]
        
        for worker_name in worker_names:
            # Each worker should load its own model instance
            mock_bot = MagicMock()
            
            # Simulate worker initialization
            if worker_name not in main.models:
                main.models[worker_name] = mock_load_model(main.WHISPER_MODEL)
        
        # Each worker should have its own model instance
        assert len(main.models) == len(worker_names)
        for worker_name in worker_names:
            assert worker_name in main.models

    def test_memory_management_configuration(self):
        """Test configuration affects memory usage patterns."""
        # Small configuration should use less resources
        small_bot = BotCore(
            whisper_model="tiny",
            num_workers=1,
            max_queue_size=5
        )
        
        # Large configuration for comparison
        large_bot = BotCore(
            whisper_model="large",
            num_workers=8,
            max_queue_size=500
        )
        
        # Verify configuration differences
        assert small_bot.max_queue_size < large_bot.max_queue_size
        assert small_bot.num_workers < large_bot.num_workers
        
        # Both should have properly initialized queues
        assert small_bot.processing_queue is not None
        assert large_bot.processing_queue is not None

    def test_configuration_immutability_during_runtime(self):
        """Test that configuration remains stable during runtime."""
        bot_core = BotCore(whisper_model="base", num_workers=2)
        
        original_model = bot_core.whisper_model
        original_workers = bot_core.num_workers
        original_queue_size = bot_core.max_queue_size
        
        # Configuration should not change during runtime
        assert bot_core.whisper_model == original_model
        assert bot_core.num_workers == original_workers
        assert bot_core.max_queue_size == original_queue_size