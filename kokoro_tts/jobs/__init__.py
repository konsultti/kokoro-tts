"""
Background job queue system for Kokoro TTS.

This package provides a robust background processing system for long-running
audiobook generation tasks. Jobs are persisted to SQLite and processed by a
separate worker process, allowing the UI to remain responsive.

Key Components:
- JobManager: High-level API for job submission and management
- AudiobookWorker: Background worker process for job execution
- JobStorage: SQLite persistence layer
- JobLogger: Structured logging system

Example Usage:
    from kokoro_tts.jobs import JobManager

    manager = JobManager()
    job_id = manager.submit_job(
        input_file="book.epub",
        output_file="book.m4a",
        voice="af_sarah",
        speed=1.0
    )

    # Check status
    job = manager.get_job(job_id)
    print(f"Progress: {job.progress.percentage}%")
"""

__version__ = "1.0.0"

# Import key components for easy access
from .models import (
    AudiobookJob,
    JobStatus,
    JobProgress,
    ErrorInfo,
    ResumeData,
    BookMetadata,
    JobID
)

from .storage import JobStorage
from .logger import JobLogger, create_logger
from .manager import JobManager
from .worker import AudiobookWorker, start_worker_process, run_worker

__all__ = [
    # Data models
    'AudiobookJob',
    'JobStatus',
    'JobProgress',
    'ErrorInfo',
    'ResumeData',
    'BookMetadata',
    'JobID',

    # Core components
    'JobStorage',
    'JobLogger',
    'create_logger',
    'JobManager',

    # Worker
    'AudiobookWorker',
    'start_worker_process',
    'run_worker',
]
