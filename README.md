# Telegram Whisper Bot

![Tests](https://github.com/Migelo/telegram-whisper-bot/workflows/Tests/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests Count](https://img.shields.io/badge/tests-116-brightgreen)
![File Size](https://img.shields.io/badge/file_size_limit-2GB-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A Telegram bot that transcribes audio messages using OpenAI's Whisper. Supports files up to 2GB using Telethon's MTProto API.

## Features

- 🎤 **Audio Transcription** - Supports voice messages and audio files up to 2GB
- 📊 **Queue Management** - 100-file queue limit with rejection handling
- 🔄 **Concurrent Processing** - Multiple workers with per-worker models
- 🛡️ **Rate Limiting** - Per-user limits to prevent abuse (2 jobs per user in queue)
- 🛡️ **Error Handling** - Comprehensive validation and graceful degradation
- 🧪 **Comprehensive Testing** - 116 tests with full coverage
- 🚀 **Production Ready** - Complete CI/CD pipeline
- ⚡ **MTProto Protocol** - Uses Telethon for larger file support vs Bot API

## Quick Start

### 1. Get Telegram API Credentials

1. **Get API credentials** from https://my.telegram.org/apps:
   - `API_ID` - Your application ID
   - `API_HASH` - Your application hash

2. **Create a bot** with @BotFather on Telegram:
   - Get your `TELEGRAM_BOT_TOKEN`

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Environment Variables
```bash
export API_ID="your_api_id_here"          # Required: from my.telegram.org
export API_HASH="your_api_hash_here"      # Required: from my.telegram.org  
export TELEGRAM_BOT_TOKEN="your_bot_token_here" # Required: from @BotFather
export WHISPER_MODEL="base"  # Optional: tiny, base, small, medium, large
export NUM_WORKERS="2"       # Optional: number of concurrent workers
export MAX_JOBS_PER_USER_IN_QUEUE="2"  # Optional: max jobs per user in queue
```

### 4. Run the Bot
```bash
python main.py
```

## Testing

Run the comprehensive test suite:

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Validate CI setup
./scripts/validate-ci.sh
```

See [TESTING.md](TESTING.md) for detailed testing documentation.

## Architecture

- **Queue-based Processing** - Configurable limits and concurrent workers
- **Thread-Safe Models** - Per-worker Whisper model instances 
- **Audio Validation** - Format checking and error recovery
- **Message Chunking** - Handles long transcriptions (>4096 chars)
- **Graceful Degradation** - Continues operation under failure conditions

## Supported Audio Formats

- **Voice Messages** - `.ogg` (Telegram voice notes)
- **Audio Files** - `.mp3`, `.wav`, `.m4a`, `.flac`, `.aac`, `.webm`
- **File Size Limit** - Up to 2GB per file (MTProto API advantage over Bot API)

## CI/CD Pipeline

- ✅ **GitHub Actions** - Automated testing on every push/PR
- ✅ **Python 3.12** - Latest stable Python version
- ✅ **106 Tests** - Comprehensive coverage including edge cases
- ✅ **Security Scanning** - Vulnerability detection with bandit/safety
- ✅ **Code Quality** - Linting and type checking

## Documentation

- [**Testing Guide**](TESTING.md) - Complete testing documentation
- [**CI/CD Setup**](CI-CD-SETUP.md) - Implementation details and usage
- [**Configuration**](pytest.ini) - Test configuration and markers

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.