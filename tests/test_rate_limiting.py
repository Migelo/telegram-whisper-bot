import pytest
import asyncio
from unittest.mock import MagicMock
from bot_core import Job


@pytest.mark.asyncio
class TestRateLimiting:
    """Test rate limiting functionality."""

    async def test_user_can_queue_up_to_limit(self, rate_limited_bot_core, mock_bot, sample_audio):
        """Test that user can queue up to their limit."""
        chat_id = 12345
        
        # First job should succeed
        success1, error1 = await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id,
            message_id=1,
            audio=sample_audio,
            processing_msg_id=10
        )
        assert success1 is True
        assert error1 is None
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 1

        # Second job should also succeed
        success2, error2 = await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id,
            message_id=2,
            audio=sample_audio,
            processing_msg_id=11
        )
        assert success2 is True
        assert error2 is None
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 2

    async def test_user_blocked_at_limit(self, rate_limited_bot_core, mock_bot, sample_audio):
        """Test that user is blocked when they reach their limit."""
        chat_id = 12345
        
        # Queue two jobs (at limit)
        await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=1, audio=sample_audio, processing_msg_id=10
        )
        await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=2, audio=sample_audio, processing_msg_id=11
        )

        # Third job should be rejected
        success3, error3 = await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id,
            message_id=3,
            audio=sample_audio,
            processing_msg_id=12
        )
        assert success3 is False
        assert "reached the maximum limit of 2 audio files" in error3
        assert "Currently in queue: 2" in error3
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 2  # Still 2, not 3

    async def test_different_users_independent_limits(self, rate_limited_bot_core, mock_bot, sample_audio):
        """Test that different users have independent rate limits."""
        user1_chat_id = 12345
        user2_chat_id = 67890
        
        # User 1 queues 2 jobs (at limit)
        success1, _ = await rate_limited_bot_core.queue_audio_job(
            chat_id=user1_chat_id, message_id=1, audio=sample_audio, processing_msg_id=10
        )
        success2, _ = await rate_limited_bot_core.queue_audio_job(
            chat_id=user1_chat_id, message_id=2, audio=sample_audio, processing_msg_id=11
        )
        assert success1 and success2
        assert rate_limited_bot_core.get_user_queue_count(user1_chat_id) == 2

        # User 2 should still be able to queue jobs
        success3, error3 = await rate_limited_bot_core.queue_audio_job(
            chat_id=user2_chat_id,
            message_id=3,
            audio=sample_audio,
            processing_msg_id=12
        )
        assert success3 is True
        assert error3 is None
        assert rate_limited_bot_core.get_user_queue_count(user2_chat_id) == 1

        # User 1 should still be blocked
        success4, error4 = await rate_limited_bot_core.queue_audio_job(
            chat_id=user1_chat_id,
            message_id=4,
            audio=sample_audio,
            processing_msg_id=13
        )
        assert success4 is False
        assert "reached the maximum limit" in error4

    async def test_job_completion_decrements_count(self, rate_limited_bot_core, mock_bot, sample_audio):
        """Test that completing jobs decrements the user's queue count."""
        chat_id = 12345
        
        # Queue 2 jobs (at limit)
        await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=1, audio=sample_audio, processing_msg_id=10
        )
        await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=2, audio=sample_audio, processing_msg_id=11
        )
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 2

        # Create a job and complete it
        job = Job(
            chat_id=chat_id,
            message_id=1,
            file_id="test_file_123",
            file_name="test_audio.ogg",
            mime_type="audio/ogg",
            file_size=1024 * 1024,
            processing_msg_id=10
        )
        
        await rate_limited_bot_core.complete_job(job)
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 1

        # Now user should be able to queue another job
        success, error = await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id,
            message_id=3,
            audio=sample_audio,
            processing_msg_id=12
        )
        assert success is True
        assert error is None
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 2

    async def test_memory_cleanup_on_zero_count(self, rate_limited_bot_core, sample_audio):
        """Test that user counts are cleaned up when they reach zero."""
        chat_id = 12345
        
        # Queue one job
        await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=1, audio=sample_audio, processing_msg_id=10
        )
        assert chat_id in rate_limited_bot_core.user_queue_count
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 1

        # Complete the job
        job = Job(
            chat_id=chat_id,
            message_id=1,
            file_id="test_file_123",
            file_name="test_audio.ogg",
            mime_type="audio/ogg",
            file_size=1024 * 1024,
            processing_msg_id=10
        )
        await rate_limited_bot_core.complete_job(job)
        
        # User should be cleaned up from the dictionary
        assert chat_id not in rate_limited_bot_core.user_queue_count
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 0

    async def test_rate_limit_with_queue_full(self, rate_limited_bot_core, sample_audio):
        """Test rate limiting interaction with global queue limit."""
        # Fill up the global queue first
        for i in range(10):
            success, error = await rate_limited_bot_core.queue_audio_job(
                chat_id=i,
                message_id=i,
                audio=sample_audio,
                processing_msg_id=i + 100
            )
            assert success is True  # Should succeed since queue limit is 10

        # Now the 11th job should fail due to global queue limit
        success, error = await rate_limited_bot_core.queue_audio_job(
            chat_id=999,
            message_id=99,
            audio=sample_audio,
            processing_msg_id=199
        )
        assert success is False
        assert "processing queue is full (10 files)" in error

    async def test_thread_safety_of_rate_limiting(self, rate_limited_bot_core, sample_audio):
        """Test that rate limiting is thread-safe with concurrent requests."""
        chat_id = 12345
        
        # Try to queue 5 jobs concurrently (should only allow 2)
        tasks = [
            rate_limited_bot_core.queue_audio_job(
                chat_id=chat_id,
                message_id=i,
                audio=sample_audio,
                processing_msg_id=i + 100
            ) for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        successes = sum(1 for success, _ in results if success is True)
        failures = sum(1 for success, _ in results if success is False)
        
        assert successes == 2  # Only 2 should succeed
        assert failures == 3   # 3 should fail
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 2

    def test_can_user_submit_job_edge_cases(self, rate_limited_bot_core):
        """Test edge cases for can_user_submit_job."""
        # New user should be able to submit
        assert rate_limited_bot_core.can_user_submit_job(12345) is True
        
        # User at limit should not be able to submit
        rate_limited_bot_core.increment_user_queue_count(12345)
        rate_limited_bot_core.increment_user_queue_count(12345)
        assert rate_limited_bot_core.can_user_submit_job(12345) is False

    def test_decrement_prevents_negative_counts(self, rate_limited_bot_core):
        """Test that decrementing doesn't go below zero."""
        chat_id = 12345
        
        # Decrement without any jobs queued
        result = rate_limited_bot_core.decrement_user_queue_count(chat_id)
        assert result == 0
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 0


@pytest.mark.asyncio
class TestRateLimitingIntegration:
    """Integration tests for rate limiting with actual job processing."""

    async def test_rate_limit_enforced_during_processing(self, rate_limited_bot_core, mock_bot, sample_audio):
        """Test that rate limits are enforced and properly decremented during processing."""
        chat_id = 12345
        
        # Mock the model to avoid loading Whisper
        rate_limited_bot_core.model = MagicMock()
        rate_limited_bot_core.model.transcribe.return_value = {"text": "Test transcription"}
        
        # Queue 2 jobs (at limit)
        success1, _ = await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=1, audio=sample_audio, processing_msg_id=10
        )
        success2, _ = await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=2, audio=sample_audio, processing_msg_id=11
        )
        assert success1 and success2
        assert rate_limited_bot_core.get_user_queue_count(chat_id) == 2

        # Third job should be rejected
        success3, error3 = await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=3, audio=sample_audio, processing_msg_id=12
        )
        assert success3 is False
        assert "reached the maximum limit" in error3

        # Process one job to completion
        job = await rate_limited_bot_core.processing_queue.get()
        await rate_limited_bot_core.complete_job(job)
        
        # Now user should be able to queue another job
        success4, error4 = await rate_limited_bot_core.queue_audio_job(
            chat_id=chat_id, message_id=4, audio=sample_audio, processing_msg_id=13
        )
        assert success4 is True
        assert error4 is None