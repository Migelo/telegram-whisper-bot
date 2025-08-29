import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from bot_core import BotCore, Job, AudioMessage

pytestmark = pytest.mark.asyncio


class TestEndToEndIntegration:
    """Test complete end-to-end workflows from message to response."""

    def setup_standard_mocks(self, bot_core, mock_tempdir, mock_whisper, mock_to_thread, transcription_text="Test transcription"):
        """Standard mock setup for integration tests."""
        bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
        mock_whisper.load_audio.return_value = [0] * 16000  # 1 second
        mock_to_thread.return_value = {"text": transcription_text}

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_complete_voice_message_workflow(self, mock_tempdir, mock_to_thread, mock_whisper, bot_core, mock_bot):
        """Test complete workflow: queue → download → process → transcribe → respond."""
        realistic_audio_job = Job(
            chat_id=123456789, message_id=42, file_id="test_voice", file_name="voice_message.ogg",
            mime_type="audio/ogg", file_size=245760, processing_msg_id=43
        )
        
        self.setup_standard_mocks(
            bot_core, mock_tempdir, mock_whisper, mock_to_thread,
            "Hello, this is a test voice message sent to the Whisper bot for transcription."
        )
        mock_whisper.load_audio.return_value = [0] * (16000 * 15)  # 15 seconds
        
        # Execute complete workflow
        result = await bot_core.process_audio_job(realistic_audio_job, mock_bot, MagicMock())
        
        # Verify successful completion
        assert result is True
        
        # Verify workflow completed successfully
        assert result is True
        mock_whisper.load_audio.assert_called_once()
        mock_to_thread.assert_called_once()
        mock_bot.send_message.assert_called_once()
        
        response = mock_bot.send_message.call_args[1]['message']
        assert "Transcription:" in response

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_multiple_concurrent_user_workflows(self, mock_tempdir, mock_to_thread, mock_whisper, bot_core, mock_bot):
        """Test multiple users submitting files concurrently."""
        user_jobs = [
            Job(chat_id=100000 + i, message_id=i, file_id=f"user_{i}_file", 
                file_name=f"user_{i}_voice.ogg", mime_type="audio/ogg", 
                file_size=128 * 1024, processing_msg_id=i + 1000)
            for i in range(5)
        ]
        
        self.setup_standard_mocks(bot_core, mock_tempdir, mock_whisper, mock_to_thread)
        
        # Unique response per user
        mock_to_thread.side_effect = lambda *args: {"text": f"User {mock_to_thread.call_count} transcription result"}
        
        # Process all users concurrently
        tasks = [bot_core.process_audio_job(job, mock_bot, MagicMock()) for job in user_jobs]
        
        results = await asyncio.gather(*tasks)
        
        # All users should be processed successfully
        assert all(results), "All user workflows should complete successfully"
        
        # Verify each user got their own transcription
        assert mock_bot.send_message.call_count == 5
        
        # Check that different users got different responses
        responses = [call[1]['message'] for call in mock_bot.send_message.call_args_list]
        unique_responses = set(responses)
        assert len(unique_responses) == 5, "Each user should get unique transcription"

    async def test_queue_to_completion_integration(self, bot_core, mock_bot, sample_audio):
        """Test complete workflow from queue addition to job completion."""
        # Queue the job
        success, _ = await bot_core.queue_audio_job(
            chat_id=987654321, message_id=100, audio=sample_audio, processing_msg_id=101
        )
        assert success is True
        assert bot_core.get_queue_position() == 1
        
        # Process the queued job
        with patch('bot_core.whisper') as mock_whisper, \
             patch('bot_core.asyncio.to_thread') as mock_to_thread, \
             patch('tempfile.TemporaryDirectory') as mock_tempdir:
            
            self.setup_standard_mocks(bot_core, mock_tempdir, mock_whisper, mock_to_thread, "Integration test successful")
            
            job = await bot_core.processing_queue.get()
            result = await bot_core.process_audio_job(job, mock_bot, MagicMock())
            
            assert result is True
            assert job.chat_id == 987654321

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_error_recovery_integration(self, mock_tempdir, mock_to_thread, mock_whisper, bot_core, mock_bot, sample_audio):
        """Test complete error handling and recovery workflow."""
        realistic_audio_job = Job(
            chat_id=123456789, message_id=42, file_id="test_voice", file_name="voice_message.ogg",
            mime_type="audio/ogg", file_size=245760, processing_msg_id=43
        )
        
        self.setup_standard_mocks(bot_core, mock_tempdir, mock_whisper, mock_to_thread)
        mock_to_thread.side_effect = RuntimeError("Temporary processing error")
        
        result = await bot_core.process_audio_job(realistic_audio_job, mock_bot, MagicMock())
        
        assert result is False  # Job failed
        
        # Verify error was communicated to user
        mock_bot.send_message.assert_called_once()
        error_response = mock_bot.send_message.call_args[1]['message']
        assert "Sorry" in error_response
        assert "error occurred" in error_response

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_long_transcription_chunking_integration(self, mock_tempdir, mock_to_thread, mock_whisper, bot_core, mock_bot, sample_audio):
        """Test complete workflow with long transcription requiring chunking."""
        realistic_audio_job = Job(
            chat_id=123456789, message_id=42, file_id="test_voice", file_name="voice_message.ogg",
            mime_type="audio/ogg", file_size=245760, processing_msg_id=43
        )
        
        long_text = "This is a very long transcription. " * 150  # ~5250 characters
        self.setup_standard_mocks(bot_core, mock_tempdir, mock_whisper, mock_to_thread, long_text)
        mock_whisper.load_audio.return_value = [0] * (16000 * 300)  # 5 minutes
        
        # Process job
        result = await bot_core.process_audio_job(realistic_audio_job, mock_bot, MagicMock())
        
        assert result is True
        
        # Should send multiple message chunks
        assert mock_bot.send_message.call_count > 1
        
        # Verify all chunks contain header and no chunk exceeds limit
        responses = [call[1]['message'] for call in mock_bot.send_message.call_args_list]
        for response in responses:
            assert "Transcription:" in response
            assert len(response) <= 4096
        
        # Verify complete text was sent across chunks
        combined_text = "".join(resp.replace("Transcription:\n\n", "") for resp in responses)
        assert long_text in combined_text

    async def test_queue_capacity_workflow_integration(self, bot_core, mock_bot, sample_audio):
        """Test complete workflow when queue reaches capacity."""
        # Fill queue to capacity
        for i in range(bot_core.max_queue_size):
            success, _ = await bot_core.queue_audio_job(i, i, sample_audio, i+100)
            assert success is True
        
        assert bot_core.is_queue_full()
        
        # Attempt to add one more - should be rejected
        rejection, _ = await bot_core.queue_audio_job(999, 999, sample_audio, 999)
        assert rejection is False
        
        # Process one job to free space
        with patch('bot_core.whisper') as mock_whisper, \
             patch('bot_core.asyncio.to_thread') as mock_to_thread, \
             patch('tempfile.TemporaryDirectory') as mock_tempdir:
            
            self.setup_standard_mocks(bot_core, mock_tempdir, mock_whisper, mock_to_thread, "Capacity test")
            
            job = await bot_core.processing_queue.get()
            await bot_core.process_audio_job(job, mock_bot, MagicMock())
            
            # Now should be able to queue another job
            success, _ = await bot_core.queue_audio_job(1000, 1000, sample_audio, 1000)
            assert success is True

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_realistic_timing_workflow(self, mock_tempdir, mock_to_thread, mock_whisper, bot_core, mock_bot, sample_audio):
        """Test workflow with realistic timing constraints."""
        realistic_audio_job = Job(
            chat_id=123456789, message_id=42, file_id="test_voice", file_name="voice_message.ogg",
            mime_type="audio/ogg", file_size=245760, processing_msg_id=43
        )
        
        self.setup_standard_mocks(bot_core, mock_tempdir, mock_whisper, mock_to_thread)
        mock_whisper.load_audio.return_value = [0] * (16000 * 120)  # 2-minute audio
        
        # Simulate realistic processing time
        async def realistic_transcribe(*args):
            await asyncio.sleep(0.1)
            return {"text": "Realistic timing test transcription with proper duration estimation."}
        mock_to_thread.side_effect = realistic_transcribe
        
        start_time = asyncio.get_event_loop().time()
        result = await bot_core.process_audio_job(realistic_audio_job, mock_bot, MagicMock())
        end_time = asyncio.get_event_loop().time()
        
        assert result is True
        
        assert result is True
        assert (end_time - start_time) < 1.0, "Should complete quickly in test environment"

    @patch('bot_core.whisper')
    async def test_audio_validation_integration_workflow(self, mock_whisper, bot_core, mock_bot, sample_audio):
        """Test complete workflow with various audio validation scenarios."""
        scenarios = [
            ([], "empty or corrupted"),
            ([0] * 800, "too short"),  # 0.05 seconds
            ([0] * 16000, None)  # 1 second - valid
        ]
        
        for i, (audio_data, expected_error) in enumerate(scenarios):
            with patch('tempfile.TemporaryDirectory') as mock_tempdir, \
                 patch('bot_core.asyncio.to_thread') as mock_to_thread:
                
                self.setup_standard_mocks(bot_core, mock_tempdir, mock_whisper, mock_to_thread, f"Valid transcription {i}")
                mock_whisper.load_audio.return_value = audio_data
                
                job = Job(chat_id=123, message_id=1, file_id=f"test_{i}", file_name=f"test_{i}.ogg",
                         mime_type="audio/ogg", file_size=1024*1024, processing_msg_id=2)
                
                result = await bot_core.process_audio_job(job, mock_bot, MagicMock())
                assert result is True  # All handled gracefully
                
                if expected_error:
                    # Check error message was sent
                    sent_messages = [call[1]['message'] for call in mock_bot.send_message.call_args_list]
                    assert any(expected_error in msg for msg in sent_messages)
                
                mock_bot.reset_mock()