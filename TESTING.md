# Testing Guide

The project includes **47 comprehensive tests** covering:

- **Rate Limiting** - Per-user queue limits, thread safety
- **Audio Processing** - Transcription, validation, error handling  
- **Queue Management** - Capacity limits, job handling
- **Integration** - End-to-end workflows, multi-user scenarios
- **Concurrency** - Failure scenarios, graceful degradation
- **Configuration** - Environment variables, model loading

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt requirements-dev.txt

# Run tests
pytest                    # All tests
pytest -v                # Verbose
pytest --cov=.           # With coverage
```

## Test Categories

```bash
# Core functionality
pytest tests/test_queue_management.py tests/test_rate_limiting.py

# Integration workflows  
pytest tests/test_integration.py tests/test_audio_processing.py

# Configuration and validation
pytest tests/test_configuration.py tests/test_audio_validation.py
```

## CI/CD

GitHub Actions runs tests on:
- Python 3.12
- Ubuntu with FFmpeg
- Coverage reporting via Codecov
- Lint/type checking (ruff, mypy)

## Configuration

- `pytest.ini` - Async support, markers, warning filters
- `requirements-dev.txt` - Testing dependencies

## Development

```bash
# Coverage
pytest --cov=. --cov-report=html

# Debug failures  
pytest --tb=long --pdb

# Performance
pytest --durations=10
```


## Mocking

- `AsyncMock` for Telegram bot operations
- `MagicMock` for Whisper model interactions  
- `@patch` decorators for isolation
- Shared fixtures in `conftest.py`

## Troubleshooting

```bash
# FFmpeg missing
sudo apt-get install ffmpeg  # Ubuntu
brew install ffmpeg        # macOS

# Import errors  
source .venv/bin/activate
pip install -r requirements.txt
```

## Contributing

1. Add tests for new features
2. Use `@pytest.mark.asyncio` for async tests
3. Test both success and error cases
4. Ensure all tests pass before PR

```python
@pytest.mark.asyncio
async def test_new_feature():
    mock_bot = AsyncMock()
    result = await function_under_test(mock_bot)
    assert result is True
```