"""
Basic unit tests for the job queue system.

Tests job submission, status updates, and basic operations.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kokoro_tts.jobs import (
    JobManager,
    JobStorage,
    JobLogger,
    JobStatus,
    AudiobookJob,
    JobProgress,
    ErrorInfo,
    ResumeData,
    BookMetadata
)


def test_job_submission():
    """Test basic job submission and retrieval."""
    print("\n=== Test: Job Submission ===")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = JobManager(db_path)

        # Create a test text file
        test_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        test_file.write("Hello, this is a test audiobook.")
        test_file.close()

        output_file = tempfile.NamedTemporaryFile(suffix='.m4a', delete=False).name

        # Submit job
        job_id = manager.submit_job(
            input_file=test_file.name,
            output_file=output_file,
            voice="af_sarah",
            speed=1.0,
            lang="en-us"
        )

        print(f"✓ Job submitted: {job_id}")

        # Retrieve job
        job = manager.get_job(job_id)
        assert job is not None, "Job should exist"
        assert job.status == JobStatus.QUEUED, "Job should be queued"
        assert job.input_file_path == test_file.name, "Input path should match"
        assert job.output_file_path == output_file, "Output path should match"

        print(f"✓ Job retrieved successfully")
        print(f"  - Status: {job.status.value}")
        print(f"  - Input: {job.input_file_path}")
        print(f"  - Output: {job.output_file_path}")

        # Get all jobs
        all_jobs = manager.get_all_jobs()
        assert len(all_jobs) >= 1, "Should have at least one job"

        print(f"✓ Total jobs in database: {len(all_jobs)}")

        # Cleanup
        os.unlink(test_file.name)

    finally:
        os.unlink(db_path)


def test_job_progress():
    """Test job progress tracking."""
    print("\n=== Test: Job Progress ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        storage = JobStorage(db_path)

        # Create a job
        job = AudiobookJob(
            input_file_path="/tmp/test.txt",
            input_file_type="txt",
            output_file_path="/tmp/test.m4a",
            output_format="m4a"
        )

        # Initialize progress
        job.progress = JobProgress(
            total_chapters=10,
            completed_chapters=0,
            total_chunks=100,
            completed_chunks=0
        )

        # Save job
        storage.create_job(job)
        print(f"✓ Job created: {job.job_id}")

        # Simulate progress updates
        for i in range(1, 6):
            job.progress.completed_chapters = i
            job.progress.completed_chunks = i * 10
            job.progress.update_percentage()

            storage.update_job(job)

            print(f"✓ Progress update {i}: {job.progress.percentage:.1f}% "
                  f"({job.progress.completed_chapters}/{job.progress.total_chapters} chapters)")

        # Retrieve and verify
        retrieved = storage.get_job(job.job_id)
        assert retrieved.progress.completed_chapters == 5, "Progress should be saved"
        assert retrieved.progress.percentage == 50.0, "Percentage should be correct"

        print(f"✓ Final progress: {retrieved.progress.percentage}%")

    finally:
        os.unlink(db_path)


def test_job_logging():
    """Test job logging system."""
    print("\n=== Test: Job Logging ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        storage = JobStorage(db_path)

        # Create a job
        job = AudiobookJob(
            input_file_path="/tmp/test.txt",
            input_file_type="txt",
            output_file_path="/tmp/test.m4a"
        )
        storage.create_job(job)

        # Create logger
        logger = JobLogger(job.job_id, storage)

        # Log various messages
        logger.info("Job started")
        logger.debug("Detailed debug information")
        logger.warning("This is a warning")
        logger.error("This is an error")

        print(f"✓ Logged 4 messages")

        # Retrieve logs
        logs = storage.get_logs(job.job_id)
        assert len(logs) == 4, "Should have 4 log entries"

        print(f"✓ Retrieved {len(logs)} log entries:")
        for log in reversed(logs):  # Reverse to show chronologically
            print(f"  - [{log['level']}] {log['message']}")

        # Get only errors
        errors = storage.get_logs(job.job_id, level="ERROR")
        assert len(errors) == 1, "Should have 1 error"

        print(f"✓ Filtered to {len(errors)} error logs")

    finally:
        os.unlink(db_path)


def test_job_cancellation():
    """Test job cancellation."""
    print("\n=== Test: Job Cancellation ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = JobManager(db_path)

        # Create a test file
        test_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        test_file.write("Test content")
        test_file.close()

        output_file = tempfile.NamedTemporaryFile(suffix='.m4a', delete=False).name

        # Submit job
        job_id = manager.submit_job(
            input_file=test_file.name,
            output_file=output_file
        )

        print(f"✓ Job submitted: {job_id}")

        # Cancel job
        success = manager.cancel_job(job_id)
        assert success, "Cancellation should succeed"

        print(f"✓ Job cancelled successfully")

        # Verify status
        job = manager.get_job(job_id)
        assert job.status == JobStatus.CANCELLED, "Job should be cancelled"

        print(f"✓ Status verified: {job.status.value}")

        # Try to cancel again (should fail)
        success = manager.cancel_job(job_id)
        assert not success, "Second cancellation should fail"

        print(f"✓ Cannot cancel already cancelled job")

        # Cleanup
        os.unlink(test_file.name)

    finally:
        os.unlink(db_path)


def test_metadata_extraction():
    """Test book metadata extraction."""
    print("\n=== Test: Metadata Extraction ===")

    # Test BookMetadata model
    metadata = BookMetadata(
        title="Test Book",
        author="Test Author",
        publisher="Test Publisher"
    )

    print(f"✓ Created metadata:")
    print(f"  - Title: {metadata.title}")
    print(f"  - Author: {metadata.author}")
    print(f"  - Publisher: {metadata.publisher}")

    # Test display name
    display = metadata.format_display_name()
    assert display == "Test Book by Test Author"

    print(f"✓ Display name: {display}")

    # Test JSON serialization
    json_str = metadata.to_json()
    deserialized = BookMetadata.from_json(json_str)

    assert deserialized.title == metadata.title
    assert deserialized.author == metadata.author

    print(f"✓ JSON serialization works")


def test_queue_operations():
    """Test atomic queue operations."""
    print("\n=== Test: Queue Operations ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        storage = JobStorage(db_path)

        # Create multiple jobs
        jobs = []
        for i in range(3):
            job = AudiobookJob(
                input_file_path=f"/tmp/test{i}.txt",
                input_file_type="txt",
                output_file_path=f"/tmp/test{i}.m4a",
                status=JobStatus.QUEUED
            )
            storage.create_job(job)
            jobs.append(job)

        print(f"✓ Created {len(jobs)} queued jobs")

        # Get next queued job (should be first one)
        next_job = storage.get_next_queued_job()
        assert next_job is not None, "Should get a job"
        assert next_job.job_id == jobs[0].job_id, "Should get first job"
        assert next_job.status == JobStatus.RUNNING, "Status should be RUNNING"

        print(f"✓ Got next job: {next_job.job_id}")
        print(f"  - Status changed to: {next_job.status.value}")

        # Get next again (should be second job)
        next_job2 = storage.get_next_queued_job()
        assert next_job2.job_id == jobs[1].job_id, "Should get second job"

        print(f"✓ Got next job: {next_job2.job_id}")

        # Get active jobs
        active = storage.get_active_jobs()
        assert len(active) == 3, "Should have 3 active jobs (2 running, 1 queued)"

        print(f"✓ Active jobs: {len(active)}")

    finally:
        os.unlink(db_path)


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KOKORO TTS JOB SYSTEM UNIT TESTS")
    print("=" * 60)

    tests = [
        test_job_submission,
        test_job_progress,
        test_job_logging,
        test_job_cancellation,
        test_metadata_extraction,
        test_queue_operations
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n✗ TEST FAILED: {test_func.__name__}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
