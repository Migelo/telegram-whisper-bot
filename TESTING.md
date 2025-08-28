# Testing Guide

This document provides comprehensive information about the testing setup for the Telegram Whisper Bot.

## Test Coverage

The project includes **106 comprehensive tests** covering:

- ✅ **Telegram Handler Integration** (13 tests) - Command handling, message routing, queue management
- ✅ **Audio Format Support** (12 tests) - Multiple audio formats, MIME type handling, file validation  
- ✅ **Concurrency & Failure Scenarios** (21 tests) - Network timeouts, resource constraints, graceful degradation
- ✅ **End-to-End Integration** (10 tests) - Complete user workflows, multi-user scenarios
- ✅ **Configuration Management** (18 tests) - Environment variables, configuration boundaries
- ✅ **Core Audio Processing** (17 tests) - Transcription, validation, error handling
- ✅ **Queue Management** (11 tests) - Queue limits, capacity handling, stress testing
- ✅ **Whisper Model Integration** (4 tests) - Model loading, different sizes, failure handling

## Quick Start

### 1. Setup Test Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Run All Tests

```bash
# Basic test run
pytest

# Verbose output with coverage
pytest -v --cov=. --cov-report=html

# Run specific test categories
pytest -m "not slow"           # Skip slow tests
pytest -m integration          # Only integration tests
pytest -m concurrency          # Only concurrency tests
```

## Test Categories

### Unit Tests
Fast, isolated tests for individual functions:
```bash
pytest tests/test_queue_management.py tests/test_whisper_model.py -v
```

### Integration Tests  
End-to-end workflow testing:
```bash
pytest tests/test_integration.py tests/test_telegram_handlers.py -v
```

### Concurrency Tests
Multi-threading and failure scenario tests:
```bash
pytest tests/test_concurrency.py -v
```

### Audio Format Tests
Comprehensive audio format support testing:
```bash
pytest tests/test_audio_formats.py -v
```

## Testing Without Whisper

For environments where Whisper cannot be installed:

```bash
pip install python-telegram-bot pytest pytest-asyncio pytest-mock
pytest tests/test_without_whisper.py tests/test_queue_management.py -v
```

## GitHub Actions CI/CD

The project includes comprehensive GitHub Actions workflows:

### Main Test Workflow (`.github/workflows/test.yml`)

**Multi-Python Version Testing:**
- Tests on Python 3.9, 3.10, 3.11, 3.12
- Ubuntu latest with FFmpeg support
- Cached dependencies for faster builds

**Test Jobs:**
1. **Full Test Suite** - Complete test coverage with Whisper
2. **Minimal Tests** - Core functionality without Whisper dependencies  
3. **Integration Tests** - End-to-end workflow validation
4. **Security Scanning** - Dependency vulnerability checks

**Features:**
- ✅ Parallel execution across Python versions
- ✅ Dependency caching for performance
- ✅ Code coverage reporting (Codecov integration)
- ✅ Lint and type checking (ruff, mypy)
- ✅ Security scanning (bandit, safety)
- ✅ Artifact uploads for coverage reports

## Test Configuration

### pytest.ini
Centralized pytest configuration with:
- Async test support (`asyncio_mode = auto`)
- Custom markers for test categorization
- Warning filters for cleaner output
- Detailed reporting options

### Requirements Files
- `requirements.txt` - Core application dependencies
- `requirements-dev.txt` - Development and testing tools

## Running Tests Locally

### Development Workflow
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests with coverage
pytest --cov=. --cov-report=html

# Run only fast tests during development  
pytest -m "not slow"

# Run specific test file
pytest tests/test_telegram_handlers.py -v

# Run with debugging on failures
pytest --tb=long --showlocals --pdb
```

### Performance Testing
```bash
# Show test durations
pytest --durations=10

# Run with performance profiling
pytest --benchmark-only
```

## Continuous Integration

### Triggers
- **Push** to `main` or `develop` branches
- **Pull Requests** to `main` or `develop`

### Matrix Testing
Tests run across Python 3.9, 3.10, 3.11, and 3.12 to ensure compatibility.

### Coverage Reporting
- Coverage reports uploaded to Codecov
- HTML coverage reports available as artifacts
- Minimum coverage thresholds enforced

### Security
- Dependency vulnerability scanning with `safety`
- Code security analysis with `bandit`
- Security reports uploaded as artifacts

## Test Data and Mocks

Tests use comprehensive mocking to avoid external dependencies:
- **AsyncMock** for async Telegram bot operations
- **MagicMock** for Whisper model interactions
- **Patch decorators** for isolated component testing
- **Fixtures** for consistent test data

## Troubleshooting

### Common Issues

**FFmpeg Not Found:**
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

**Async Test Warnings:**
Already configured in `pytest.ini` to filter common async warnings.

**Import Errors:**
Ensure virtual environment is activated and dependencies installed:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Debug Mode
```bash
# Run tests with detailed debugging
pytest --tb=long --showlocals -s

# Drop into debugger on failures  
pytest --pdb
```

## Contributing

When adding new features:

1. **Add corresponding tests** in the appropriate test file
2. **Use proper test markers** for categorization
3. **Include both positive and negative test cases**
4. **Test error conditions and edge cases**
5. **Ensure all tests pass** before submitting PR

### Test Naming Convention
- `test_<functionality>_<scenario>` 
- Example: `test_handle_audio_oversized_file_rejection`

### Async Test Pattern
```python
@pytest.mark.asyncio
async def test_async_function():
    # Use AsyncMock for async operations
    mock_bot = AsyncMock()
    result = await some_async_function(mock_bot)
    assert result is True
```

This comprehensive testing setup ensures the Telegram Whisper Bot is reliable, maintainable, and production-ready.