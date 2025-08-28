import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from bot_core import BotCore, Job, AudioMessage

pytestmark = pytest.mark.asyncio


class TestEndToEndIntegration:
    """Test complete end-to-end workflows from message to response."""

    @pytest.fixture
    def integration_bot_core(self):
        """BotCore configured for integration testing."""
        return BotCore(
            whisper_model="base",
            num_workers=2,
            max_file_size=20 * 1024 * 1024,
            max_queue_size=10  # Smaller for testing
        )

    @pytest.fixture
    def realistic_audio_job(self):
        """Job that simulates a real user interaction."""
        return Job(
            chat_id=123456789,
            message_id=42,
            file_id="BAADBAADrwADBREAAYag2eLPt_vdAg",
            file_name="voice_message.ogg",
            mime_type="audio/ogg",
            file_size=245760,  # ~240KB realistic voice message
            processing_msg_id=43
        )

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_complete_voice_message_workflow(self, mock_tempdir, mock_to_thread, mock_whisper,
                                                  integration_bot_core, mock_bot, realistic_audio_job):
        """Test complete workflow: queue → download → process → transcribe → respond."""
        # Setup realistic mocks
        integration_bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/integration_test"
        
        # Realistic audio duration (15 seconds)
        mock_whisper.load_audio.return_value = [0] * (16000 * 15)
        
        # Realistic transcription result
        mock_to_thread.return_value = {
            "text": "Hello, this is a test voice message sent to the Whisper bot for transcription. I hope it works correctly and provides an accurate transcription of what I'm saying right now."
        }
        
        # Execute complete workflow
        result = await integration_bot_core.process_audio_job(realistic_audio_job, mock_bot)
        
        # Verify successful completion
        assert result is True
        
        # Verify complete workflow steps
        # 1. File download
        mock_bot.get_file.assert_called_once_with(realistic_audio_job.file_id)
        
        # 2. Progress updates (download, analyze, process)
        assert mock_bot.edit_message_text.call_count >= 3
        progress_messages = [call[1]['text'] for call in mock_bot.edit_message_text.call_args_list]
        assert any("Downloading" in msg for msg in progress_messages)
        assert any("Analyzing" in msg for msg in progress_messages)
        assert any("Processing" in msg for msg in progress_messages)
        
        # 3. Audio analysis
        mock_whisper.load_audio.assert_called_once()
        
        # 4. Transcription
        mock_to_thread.assert_called_once()
        
        # 5. Response delivery
        mock_bot.send_message.assert_called_once()
        response = mock_bot.send_message.call_args[1]['text']
        assert "Transcription:" in response
        assert "Hello, this is a test voice message" in response

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_multiple_concurrent_user_workflows(self, mock_tempdir, mock_to_thread, mock_whisper,
                                                     integration_bot_core, mock_bot):
        """Test multiple users submitting files concurrently."""
        # Create jobs for different users
        user_jobs = [
            Job(
                chat_id=100000 + i,
                message_id=i,
                file_id=f"user_{i}_file",
                file_name=f"user_{i}_voice.ogg",
                mime_type="audio/ogg",
                file_size=128 * 1024,  # 128KB each
                processing_msg_id=i + 1000
            ) for i in range(5)  # 5 concurrent users
        ]
        
        # Setup mocks
        integration_bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/multi_user_test"
        mock_whisper.load_audio.return_value = [0] * 16000  # 1 second each
        
        # Unique response per user
        def mock_transcribe_per_user(*args):
            # Extract user info from the call context
            call_count = mock_to_thread.call_count
            return {"text": f"User {call_count} transcription result"}
        
        mock_to_thread.side_effect = mock_transcribe_per_user
        
        # Process all users concurrently
        tasks = [
            integration_bot_core.process_audio_job(job, mock_bot)
            for job in user_jobs
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All users should be processed successfully
        assert all(results), "All user workflows should complete successfully"
        
        # Verify each user got their own transcription
        assert mock_bot.send_message.call_count == 5
        
        # Check that different users got different responses
        responses = [call[1]['text'] for call in mock_bot.send_message.call_args_list]
        unique_responses = set(responses)
        assert len(unique_responses) == 5, "Each user should get unique transcription"

    async def test_queue_to_completion_integration(self, integration_bot_core, mock_bot):
        """Test complete workflow from queue addition to job completion."""
        # Create realistic audio message
        audio = AudioMessage(
            file_id="integration_test_file",
            file_size=512 * 1024,  # 512KB
            mime_type="audio/mp3",
            file_name="integration_test.mp3",
            file_unique_id="unique_integration"
        )
        
        # 1. Queue the job
        success = await integration_bot_core.queue_audio_job(
            chat_id=987654321,
            message_id=100,
            audio=audio,
            processing_msg_id=101
        )
        assert success is True
        assert integration_bot_core.get_queue_position() == 1
        
        # 2. Process the queued job
        with patch('bot_core.whisper') as mock_whisper, \
             patch('bot_core.asyncio.to_thread') as mock_to_thread, \
             patch('tempfile.TemporaryDirectory') as mock_tempdir:
            
            # Setup processing mocks
            integration_bot_core.model = MagicMock()
            mock_tempdir.return_value.__enter__.return_value = "/tmp/queue_test"
            mock_whisper.load_audio.return_value = [0] * (16000 * 3)  # 3 seconds
            mock_to_thread.return_value = {"text": "Integration test successful"}
            
            # Get and process the job
            job = await integration_bot_core.processing_queue.get()
            result = await integration_bot_core.process_audio_job(job, mock_bot)
            
            assert result is True
            assert job.file_name == "integration_test.mp3"
            assert job.chat_id == 987654321

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_error_recovery_integration(self, mock_tempdir, mock_to_thread, mock_whisper,
                                            integration_bot_core, mock_bot, realistic_audio_job):
        """Test complete error handling and recovery workflow."""
        # Setup mocks for initial failure then recovery
        integration_bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/error_recovery"
        mock_whisper.load_audio.return_value = [0] * 16000
        
        # First attempt fails, recovery should handle gracefully
        mock_to_thread.side_effect = RuntimeError("Temporary processing error")
        
        # Process job - should handle error gracefully
        result = await integration_bot_core.process_audio_job(realistic_audio_job, mock_bot)
        
        assert result is False  # Job failed
        
        # Verify error was communicated to user
        mock_bot.send_message.assert_called_once()
        error_response = mock_bot.send_message.call_args[1]['text']
        assert "Sorry" in error_response
        assert "error occurred" in error_response

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_long_transcription_chunking_integration(self, mock_tempdir, mock_to_thread, mock_whisper,
                                                          integration_bot_core, mock_bot, realistic_audio_job):
        """Test complete workflow with long transcription requiring chunking."""
        # Setup mocks
        integration_bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/long_transcript"
        mock_whisper.load_audio.return_value = [0] * (16000 * 300)  # 5 minutes of audio
        
        # Generate very long transcription (over 4096 chars)
        long_text = "This is a very long transcription. " * 150  # ~5250 characters
        mock_to_thread.return_value = {"text": long_text}
        
        # Process job
        result = await integration_bot_core.process_audio_job(realistic_audio_job, mock_bot)
        
        assert result is True
        
        # Should send multiple message chunks
        assert mock_bot.send_message.call_count > 1
        
        # Verify all chunks contain header and no chunk exceeds limit
        responses = [call[1]['text'] for call in mock_bot.send_message.call_args_list]
        for response in responses:
            assert "Transcription:" in response
            assert len(response) <= 4096
        
        # Verify complete text was sent across chunks
        combined_text = "".join(resp.replace("Transcription:\n\n", "") for resp in responses)
        assert long_text in combined_text

    async def test_queue_capacity_workflow_integration(self, integration_bot_core, mock_bot):
        """Test complete workflow when queue reaches capacity."""
        audio = AudioMessage("test_file", 1024*1024, "audio/ogg", "test.ogg")
        
        # Fill queue to capacity
        queued_jobs = []
        for i in range(integration_bot_core.max_queue_size):
            success = await integration_bot_core.queue_audio_job(i, i, audio, i+100)
            assert success is True
            queued_jobs.append(i)
        
        # Verify queue is full
        assert integration_bot_core.is_queue_full()
        assert integration_bot_core.get_queue_position() == integration_bot_core.max_queue_size
        
        # Attempt to add one more - should be rejected
        rejection = await integration_bot_core.queue_audio_job(999, 999, audio, 999)
        assert rejection is False
        
        # Process one job to free space
        with patch('bot_core.whisper') as mock_whisper, \
             patch('bot_core.asyncio.to_thread') as mock_to_thread, \
             patch('tempfile.TemporaryDirectory') as mock_tempdir:
            
            integration_bot_core.model = MagicMock()
            mock_tempdir.return_value.__enter__.return_value = "/tmp/capacity_test"
            mock_whisper.load_audio.return_value = [0] * 16000
            mock_to_thread.return_value = {"text": "Capacity test"}
            
            job = await integration_bot_core.processing_queue.get()
            await integration_bot_core.process_audio_job(job, mock_bot)
            
            # Now should be able to queue another job
            success = await integration_bot_core.queue_audio_job(1000, 1000, audio, 1000)
            assert success is True

    @patch('bot_core.whisper')
    @patch('bot_core.asyncio.to_thread')
    @patch('tempfile.TemporaryDirectory')
    async def test_realistic_timing_workflow(self, mock_tempdir, mock_to_thread, mock_whisper,
                                           integration_bot_core, mock_bot, realistic_audio_job):
        """Test workflow with realistic timing constraints."""
        # Setup mocks with realistic delays
        integration_bot_core.model = MagicMock()
        mock_tempdir.return_value.__enter__.return_value = "/tmp/timing_test"
        
        # 2-minute audio file
        mock_whisper.load_audio.return_value = [0] * (16000 * 120)
        
        # Simulate realistic processing time
        async def realistic_transcribe(*args):
            await asyncio.sleep(0.1)  # Simulate processing delay
            return {"text": "Realistic timing test transcription with proper duration estimation."}
        
        mock_to_thread.side_effect = realistic_transcribe
        
        # Track timing
        start_time = asyncio.get_event_loop().time()
        result = await integration_bot_core.process_audio_job(realistic_audio_job, mock_bot)
        end_time = asyncio.get_event_loop().time()
        
        assert result is True
        
        # Should complete within reasonable time
        total_time = end_time - start_time
        assert total_time < 1.0, "Workflow should complete quickly in test environment"
        
        # Verify duration estimation was shown to user
        progress_calls = mock_bot.edit_message_text.call_args_list
        estimation_messages = [call[1]['text'] for call in progress_calls]
        time_estimates = [msg for msg in estimation_messages if "Estimated time:" in msg]
        assert len(time_estimates) > 0, "Should show time estimation to user"

    @patch('bot_core.whisper')
    async def test_audio_validation_integration_workflow(self, mock_whisper,
                                                        integration_bot_core, mock_bot):
        """Test complete workflow with various audio validation scenarios."""
        test_scenarios = [
            {
                "name": "empty_audio",
                "audio_data": [],
                "expected_message": "empty or corrupted"
            },
            {
                "name": "short_audio",
                "audio_data": [0] * 800,  # 0.05 seconds
                "expected_message": "too short"
            },
            {
                "name": "valid_audio",
                "audio_data": [0] * 16000,  # 1 second
                "expected_message": None  # Should proceed to transcription
            }
        ]
        
        for scenario in test_scenarios:
            with patch('tempfile.TemporaryDirectory') as mock_tempdir, \
                 patch('bot_core.asyncio.to_thread') as mock_to_thread:
                
                # Setup scenario
                integration_bot_core.model = MagicMock()
                mock_tempdir.return_value.__enter__.return_value = "/tmp/validation_test"
                mock_whisper.load_audio.return_value = scenario["audio_data"]
                mock_to_thread.return_value = {"text": f"Valid transcription for {scenario['name']}"}
                
                job = Job(
                    chat_id=123,
                    message_id=1,
                    file_id=f"test_{scenario['name']}",
                    file_name=f"{scenario['name']}.ogg",
                    mime_type="audio/ogg",
                    file_size=1024*1024,
                    processing_msg_id=2
                )
                
                result = await integration_bot_core.process_audio_job(job, mock_bot)
                
                if scenario["expected_message"]:
                    # Should handle validation error gracefully
                    assert result is True  # Handled gracefully
                    # Check error message was sent
                    sent_messages = [call[1]['text'] for call in mock_bot.send_message.call_args_list]
                    validation_msgs = [msg for msg in sent_messages if scenario["expected_message"] in msg]
                    assert len(validation_msgs) > 0, f"Should send validation error for {scenario['name']}"
                else:
                    # Should proceed to transcription
                    assert result is True
                    mock_to_thread.assert_called()
                
                # Reset mocks for next scenario
                mock_bot.reset_mock()