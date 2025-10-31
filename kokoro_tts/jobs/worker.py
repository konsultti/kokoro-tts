"""
Background worker for processing audiobook generation jobs.

This module runs as a separate process and polls the job queue for work.
"""

import os
import sys
import time
import signal
import traceback
import multiprocessing
from pathlib import Path
from typing import Optional

import numpy as np

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
from .logger import JobLogger
from ..core import KokoroEngine, ProcessingOptions, AudioFormat, Chapter


class AudiobookWorker:
    """
    Background worker process for audiobook generation.

    Features:
    - Polls job queue continuously
    - Processes jobs using KokoroEngine
    - Updates progress in real-time
    - Handles errors with resume capability
    - Sends heartbeats to indicate alive status
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        model_path: str = "kokoro-v1.0.onnx",
        voices_path: str = "voices-v1.0.bin",
        poll_interval: float = 2.0
    ):
        """
        Initialize worker.

        Args:
            db_path: Path to SQLite database
            model_path: Path to Kokoro model
            voices_path: Path to voices file
            poll_interval: Seconds between queue polls
        """
        self.db_path = db_path
        self.model_path = model_path
        self.voices_path = voices_path
        self.poll_interval = poll_interval

        self.storage = JobStorage(db_path)
        self.worker_id = f"worker-{os.getpid()}"
        self.engine: Optional[KokoroEngine] = None

        self.running = False
        self.current_job_id: Optional[JobID] = None

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False

    def start(self):
        """
        Start the worker loop.

        This is the main entry point that runs indefinitely until shutdown.
        """
        print(f"Worker {self.worker_id} starting...")

        # Initialize engine
        try:
            self.engine = KokoroEngine(
                model_path=self.model_path,
                voices_path=self.voices_path
            )
            self.engine.load_model()
            print(f"Model loaded successfully")
        except Exception as e:
            print(f"Failed to load model: {e}")
            return

        self.running = True
        last_heartbeat = 0

        try:
            while self.running:
                # Send heartbeat every 10 seconds
                current_time = time.time()
                if current_time - last_heartbeat > 10:
                    self.storage.update_worker_heartbeat(
                        self.worker_id,
                        self.current_job_id
                    )
                    last_heartbeat = current_time

                # Poll for next job
                job = self.storage.get_next_queued_job()

                if job:
                    self.current_job_id = job.job_id
                    print(f"\nProcessing job {job.job_id}")

                    try:
                        self.execute_job(job)
                    except Exception as e:
                        print(f"Unexpected error executing job: {e}")
                        traceback.print_exc()

                    self.current_job_id = None
                else:
                    # No jobs, sleep and continue polling
                    time.sleep(self.poll_interval)

        finally:
            print(f"Worker {self.worker_id} shutting down...")
            self.storage.remove_worker(self.worker_id)
            self.storage.close()

    def execute_job(self, job: AudiobookJob):
        """
        Execute a job.

        Args:
            job: Job to execute
        """
        logger = JobLogger(job.job_id, self.storage)
        logger.info("Job execution started", also_print=True)

        start_time = time.time()

        try:
            # Extract chapters from input file
            chapters = self._extract_chapters(job, logger)

            if not chapters:
                raise ValueError("No chapters extracted from input file")

            # Initialize progress
            job.progress.total_chapters = len(chapters)
            job.progress.total_chunks = 0  # Will be updated as we process
            self.storage.update_job(job)

            # Check for resume data
            resume_data = job.resume_data
            if resume_data:
                logger.info(
                    f"Resuming job from chapter {len(resume_data.completed_chapters)}/{len(chapters)}",
                    also_print=True
                )

            # Process each chapter
            all_samples = []
            sample_rate = None

            for chapter_idx, chapter in enumerate(chapters):
                # Skip if already completed (resume case)
                if resume_data and resume_data.is_chapter_completed(chapter_idx):
                    logger.info(f"Skipping completed chapter {chapter_idx + 1}: {chapter.title}")
                    job.progress.completed_chapters += 1
                    self.storage.update_job(job)
                    continue

                chapter_start = time.time()
                logger.log_chapter_start(chapter_idx, chapter.title, len(chapters))

                # Update progress
                job.progress.current_chapter_name = chapter.title
                job.progress.current_operation = f"Processing chapter {chapter_idx + 1}/{len(chapters)}"
                self.storage.update_job(job)

                # Create progress callback for this chapter
                def progress_callback(message: str, current: int, total: int):
                    job.progress.current_operation = message
                    # We'll update chunks count based on current progress
                    self.storage.update_job(job)

                # Build processing options
                options = self._build_processing_options(job)

                # Generate audio for this chapter
                try:
                    samples, sr = self.engine.generate_audio(
                        chapter.content,
                        options,
                        progress_callback=progress_callback
                    )

                    if samples is not None:
                        all_samples.extend(samples)
                        if sample_rate is None:
                            sample_rate = sr

                        # Update progress
                        job.progress.completed_chapters += 1
                        job.progress.update_percentage()

                        elapsed = time.time() - start_time
                        job.progress.update_eta(elapsed)

                        self.storage.update_job(job)

                        # Log chapter completion
                        chapter_duration = time.time() - chapter_start
                        logger.log_chapter_complete(
                            chapter_idx,
                            chapter.title,
                            len(samples),
                            chapter_duration
                        )

                        # Mark chapter as completed for resume purposes
                        if not resume_data:
                            resume_data = ResumeData()
                            job.resume_data = resume_data

                        resume_data.mark_chapter_completed(chapter_idx)
                        self.storage.update_job(job)

                except Exception as e:
                    logger.log_error_with_context(
                        e,
                        f"processing chapter {chapter_idx + 1}",
                        chapter_index=chapter_idx
                    )
                    raise

            # All chapters processed, save final output
            if all_samples and sample_rate:
                logger.info("Saving final audio file...", also_print=True)

                job.progress.current_operation = "Saving audio file"
                self.storage.update_job(job)

                output_format = AudioFormat[job.output_format.upper()]
                self.engine.save_audio(
                    np.array(all_samples),
                    sample_rate,
                    job.output_file_path,
                    output_format
                )

                # Get file size
                output_size = os.path.getsize(job.output_file_path)
                job.output_file_size = output_size

                # Mark as completed
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()
                job.processing_time_seconds = job.completed_at - start_time

                job.progress.percentage = 100.0
                job.progress.current_operation = "Completed"

                self.storage.update_job(job)

                logger.info(
                    f"Job completed successfully in {job.processing_time_seconds:.1f}s",
                    metadata={
                        'output_file': job.output_file_path,
                        'output_size': output_size,
                        'processing_time': job.processing_time_seconds
                    },
                    also_print=True
                )

            else:
                raise ValueError("No audio generated")

        except Exception as e:
            # Job failed
            logger.error(f"Job failed: {e}", also_print=True)
            logger.log_error_with_context(e, "job execution")

            # Create error info
            error_info = ErrorInfo(
                error_type=type(e).__name__,
                error_message=str(e),
                traceback=traceback.format_exc(),
                is_recoverable=True,  # Most errors are recoverable
                recovery_suggestion="Resume the job to continue from where it left off"
            )

            job.status = JobStatus.FAILED
            job.completed_at = time.time()
            job.error_info = error_info

            # Ensure resume data is saved
            if job.resume_data is None:
                job.resume_data = ResumeData()

            self.storage.update_job(job)

            print(f"Job {job.job_id} failed: {e}")

    def _extract_chapters(self, job: AudiobookJob, logger: JobLogger) -> list:
        """
        Extract chapters from input file.

        Args:
            job: Job to extract chapters from
            logger: Logger for this job

        Returns:
            List of Chapter objects
        """
        logger.info(f"Extracting chapters from {job.input_file_type} file")

        try:
            if job.input_file_type == 'epub':
                chapters = self.engine.extract_chapters_from_epub(
                    job.input_file_path,
                    debug=False
                )
            elif job.input_file_type == 'pdf':
                chapters = self.engine.extract_chapters_from_pdf(
                    job.input_file_path,
                    debug=False
                )
            elif job.input_file_type == 'txt':
                with open(job.input_file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                chapters = [Chapter(title="Chapter 1", content=text, order=1)]
            else:
                raise ValueError(f"Unsupported file type: {job.input_file_type}")

            # Handle audiobook-specific options
            if job.audiobook_options:
                # Skip front matter if requested
                if job.audiobook_options.get('skip_front_matter', False):
                    from ..core import is_front_matter
                    original_count = len(chapters)
                    chapters = [
                        ch for ch in chapters
                        if not is_front_matter(ch.title, ch.order, len(ch.content.split()))
                    ]
                    skipped = original_count - len(chapters)
                    if skipped > 0:
                        logger.info(f"Skipped {skipped} front matter chapters")

                # Add introduction if requested
                if not job.audiobook_options.get('no_intro', False):
                    intro_text = job.audiobook_options.get('intro_text')
                    if not intro_text and job.metadata:
                        # Generate default intro
                        intro_text = self._generate_intro_text(job.metadata)

                    if intro_text:
                        intro_chapter = Chapter(
                            title="Introduction",
                            content=intro_text,
                            order=0
                        )
                        chapters.insert(0, intro_chapter)
                        logger.info("Added introduction chapter")

            logger.info(f"Extracted {len(chapters)} chapters")
            return chapters

        except Exception as e:
            logger.error(f"Failed to extract chapters: {e}")
            raise

    def _generate_intro_text(self, metadata: BookMetadata) -> str:
        """Generate introduction text from metadata."""
        parts = []

        if metadata.title:
            parts.append(f"This is {metadata.title}")

        if metadata.author:
            parts.append(f"written by {metadata.author}")

        parts.append("narrated by Kokoro Text-to-Speech")

        return ", ".join(parts) + "."

    def _build_processing_options(self, job: AudiobookJob) -> ProcessingOptions:
        """
        Build ProcessingOptions from job configuration.

        Args:
            job: Job to build options for

        Returns:
            ProcessingOptions instance
        """
        opts = job.processing_options

        return ProcessingOptions(
            voice=opts.get('voice', 'af_sarah'),
            speed=opts.get('speed', 1.0),
            lang=opts.get('lang', 'en-us'),
            format=AudioFormat[opts.get('format', 'M4A').upper()],
            debug=opts.get('debug', False)
        )


def run_worker(
    db_path: Optional[str] = None,
    model_path: str = "kokoro-v1.0.onnx",
    voices_path: str = "voices-v1.0.bin"
):
    """
    Entry point for running worker as a separate process.

    Args:
        db_path: Path to SQLite database
        model_path: Path to Kokoro model
        voices_path: Path to voices file
    """
    worker = AudiobookWorker(
        db_path=db_path,
        model_path=model_path,
        voices_path=voices_path
    )

    worker.start()


def start_worker_process(
    db_path: Optional[str] = None,
    model_path: str = "kokoro-v1.0.onnx",
    voices_path: str = "voices-v1.0.bin"
) -> multiprocessing.Process:
    """
    Start worker as a background process.

    Args:
        db_path: Path to SQLite database
        model_path: Path to Kokoro model
        voices_path: Path to voices file

    Returns:
        Process object (already started)
    """
    process = multiprocessing.Process(
        target=run_worker,
        args=(db_path, model_path, voices_path),
        daemon=True,
        name="kokoro-worker"
    )

    process.start()
    print(f"Started worker process (PID: {process.pid})")

    return process


if __name__ == '__main__':
    # Allow running worker directly
    run_worker()
