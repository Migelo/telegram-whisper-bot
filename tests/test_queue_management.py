import pytest
import asyncio
from bot_core import BotCore, AudioMessage

pytestmark = pytest.mark.asyncio


class TestQueueManagement:
    """Test queue management and validation functionality."""

    def test_validate_audio_file_valid(self, bot_core, sample_audio):
        """Test that valid audio files pass validation."""
        result = bot_core.validate_audio_file(sample_audio)
        assert result is None

    def test_validate_audio_file_too_large(self, bot_core, large_audio):
        """Test that oversized files are rejected."""
        result = bot_core.validate_audio_file(large_audio)
        assert result == "File is too large. The limit is 2 GB."

    def test_queue_initially_empty(self, bot_core):
        """Test that queue starts empty."""
        assert bot_core.get_queue_position() == 0
        assert not bot_core.is_queue_full()

    async def test_queue_single_job(self, bot_core, sample_audio):
        """Test queuing a single job."""
        success, _ = await bot_core.queue_audio_job(
            chat_id=12345,
            message_id=1,
            audio=sample_audio,
            processing_msg_id=2
        )
        
        assert success is True
        assert bot_core.get_queue_position() == 1
        assert not bot_core.is_queue_full()


    async def test_queue_at_capacity(self, sample_audio):
        """Test queue behavior at maximum capacity."""
        # Create bot with small queue size for testing
        bot_core = BotCore(max_queue_size=3)
        
        # Fill queue to capacity
        for i in range(3):
            success, _ = await bot_core.queue_audio_job(
                chat_id=12345 + i,
                message_id=i,
                audio=sample_audio,
                processing_msg_id=i + 100
            )
            assert success is True
        
        assert bot_core.is_queue_full()
        assert bot_core.get_queue_position() == 3

    async def test_queue_rejects_when_full(self, sample_audio):
        """Test that queue rejects new jobs when full."""
        # Create bot with small queue size for testing
        bot_core = BotCore(max_queue_size=2)
        
        # Fill queue to capacity
        for i in range(2):
            success, _ = await bot_core.queue_audio_job(
                chat_id=12345 + i,
                message_id=i,
                audio=sample_audio,
                processing_msg_id=i + 100
            )
            assert success is True
        
        # Try to add one more - should be rejected
        success, _ = await bot_core.queue_audio_job(
            chat_id=99999,
            message_id=999,
            audio=sample_audio,
            processing_msg_id=1999
        )
        
        assert success is False
        assert bot_core.get_queue_position() == 2
        assert bot_core.is_queue_full()

    async def test_filename_generation(self, bot_core, voice_message):
        """Test filename generation for voice messages."""
        success, _ = await bot_core.queue_audio_job(
            chat_id=123, message_id=1, audio=voice_message, processing_msg_id=2
        )
        assert success is True
        
        job = await bot_core.processing_queue.get()
        assert job.file_name == "voice_message.ogg"

