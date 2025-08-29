import pytest
import os
import asyncio
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
        assert bot_core.max_file_size == 2 * 1024 * 1024 * 1024  # 2GB
        assert bot_core.max_queue_size == 100

    def test_bot_core_custom_configuration(self):
        """Test BotCore with custom configuration values."""
        bot_core = BotCore(
            whisper_model="large",
            num_workers=4,
            max_file_size=1024 * 1024 * 1024,  # 1GB
            max_queue_size=200
        )
        
        assert bot_core.whisper_model == "large"
        assert bot_core.num_workers == 4
        assert bot_core.max_file_size == 1024 * 1024 * 1024
        assert bot_core.max_queue_size == 200

    @patch.dict(os.environ, {
        'WHISPER_MODEL': 'small',
        'NUM_WORKERS': '3',
        'TELEGRAM_BOT_TOKEN': 'test_token_123',
        'API_ID': '12345',
        'API_HASH': 'test_api_hash'
    })
    def test_main_environment_variable_parsing(self):
        """Test that main.py correctly reads environment variables."""
        # Reload the module to pick up new env vars
        import importlib
        importlib.reload(main)
        
        assert main.WHISPER_MODEL == "small"
        assert main.NUM_WORKERS == 3
        assert main.TELEGRAM_BOT_TOKEN == "test_token_123"
        assert main.API_ID == 12345
        assert main.API_HASH == "test_api_hash"

    @patch.dict(os.environ, {}, clear=True)
    def test_main_default_environment_values(self):
        """Test default values when environment variables are not set."""
        import importlib
        importlib.reload(main)
        
        assert main.WHISPER_MODEL == "base"
        assert main.NUM_WORKERS == 2
        assert main.TELEGRAM_BOT_TOKEN is None
        assert main.API_ID == 0
        assert main.API_HASH == ""

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
            (1 * 1024 * 1024, True),                    # 1MB - should be valid
            (100 * 1024 * 1024, True),                  # 100MB - should be valid
            (1024 * 1024 * 1024, True),                 # 1GB - should be valid  
            (3 * 1024 * 1024 * 1024, False),            # 3GB - over default 2GB limit
        ]
        
        bot_core = BotCore(max_file_size=2 * 1024 * 1024 * 1024)  # 2GB
        
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
                assert "2 GB" in error

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
        success1, _ = await small_queue_bot.queue_audio_job(1, 1, audio, 1)
        success2, _ = await small_queue_bot.queue_audio_job(2, 2, audio, 2)
        success3, error = await small_queue_bot.queue_audio_job(3, 3, audio, 3)  # Should fail
        
        assert success1 is True
        assert success2 is True
        assert success3 is False
        assert "queue is full" in error

    def test_whisper_model_configurations(self):
        """Test different Whisper model configurations."""
        valid_models = ["tiny", "base", "small", "medium", "large"]
        
        for model in valid_models:
            bot_core = BotCore(whisper_model=model)
            assert bot_core.whisper_model == model

    def test_whisper_model_loading_with_different_models(self):
        """Test loading different Whisper model sizes."""
        models_to_test = ["tiny", "base", "small", "medium", "large"]
        
        for model_name in models_to_test:
            with patch('bot_core.whisper') as mock_whisper:
                # Create fresh mock for each test
                mock_model = MagicMock()
                mock_whisper.load_model.return_value = mock_model
                
                bot_core = BotCore(whisper_model=model_name)
                result = bot_core.get_worker_model("test_worker")
                
                assert result == mock_model
                mock_whisper.load_model.assert_called_with(model_name)
                assert bot_core.models["test_worker"] == mock_model

    def test_whisper_model_loading_failure_handling(self):
        """Test handling of Whisper model loading failures."""
        with patch('bot_core.whisper') as mock_whisper:
            mock_whisper.load_model.side_effect = Exception("Model not found")
            
            bot_core = BotCore(whisper_model="nonexistent")
            result = bot_core.get_worker_model("test_worker")
            
            assert result is None
            assert "test_worker" not in bot_core.models

    def test_constants_configuration(self):
        """Test that constants are properly configured."""
        # Test main.py constants
        assert main.MAX_FILE_SIZE_MB == 2 * 1024 * 1024 * 1024  # 2GB
        assert main.MAX_QUEUE_SIZE == 100
        
        # These should be configurable via environment
        assert isinstance(main.WHISPER_MODEL, str)
        assert isinstance(main.NUM_WORKERS, int)

    @patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': '', 'API_ID': '12345', 'API_HASH': 'test_hash'})
    def test_empty_telegram_token(self):
        """Test handling of empty Telegram bot token."""
        import importlib
        importlib.reload(main)
        
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN environment variable not set"):
            asyncio.run(main.main())

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_telegram_token(self):
        """Test handling of missing Telegram bot token."""
        import importlib
        importlib.reload(main)
        
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN environment variable not set"):
            asyncio.run(main.main())

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
        'NUM_WORKERS': '6',
        'API_ID': '12345',
        'API_HASH': 'test_hash'
    })
    def test_environment_integration_with_bot_core(self):
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

    def test_per_worker_model_configuration(self):
        """Test that each worker can have its own model configuration."""
        with patch('bot_core.whisper') as mock_whisper:
            mock_model = MagicMock()
            mock_whisper.load_model.return_value = mock_model
            
            # Create a bot_core instance for this test
            bot_core = BotCore()
            
            # Test multiple workers with same model
            worker_names = ["Worker-1", "Worker-2", "Worker-3"]
            
            for worker_name in worker_names:
                # Each worker should be able to get its own model instance
                model = bot_core.get_worker_model(worker_name)
                assert model == mock_model
        
        # Each worker should have loaded the same model
        assert len(bot_core.models) == len(worker_names)
        for worker_name in worker_names:
            assert worker_name in bot_core.models

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