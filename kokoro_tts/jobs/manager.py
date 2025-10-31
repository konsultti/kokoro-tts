"""
High-level job management API.

Provides a clean interface for submitting and managing audiobook generation jobs.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import (
    AudiobookJob,
    JobStatus,
    JobProgress,
    BookMetadata,
    ResumeData,
    JobID
)
from .storage import JobStorage
from .logger import JobLogger


class JobManager:
    """
    High-level API for job management.

    This is the main interface that UI and other components use to interact
    with the job queue system.

    Example:
        manager = JobManager()

        # Submit a job
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

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize job manager.

        Args:
            db_path: Path to SQLite database (None for default)
        """
        self.storage = JobStorage(db_path)

    def submit_job(
        self,
        input_file: str,
        output_file: str,
        voice: str = "af_sarah",
        speed: float = 1.0,
        lang: str = "en-us",
        output_format: str = "m4a",
        skip_front_matter: bool = False,
        intro_text: Optional[str] = None,
        no_intro: bool = False,
        use_gpu: bool = False,
        metadata: Optional[BookMetadata] = None
    ) -> JobID:
        """
        Submit a new audiobook generation job.

        Args:
            input_file: Path to input file (txt, epub, pdf)
            output_file: Path to output audio file
            voice: Voice name or blend (e.g., "af_sarah" or "af_sarah:60,am_adam:40")
            speed: Speech speed (0.5 to 2.0)
            lang: Language code (e.g., "en-us")
            output_format: Audio format (wav, mp3, m4a)
            skip_front_matter: Skip front matter chapters (for audiobooks)
            intro_text: Custom introduction text
            no_intro: Disable automatic introduction
            use_gpu: Enable GPU acceleration
            metadata: Book metadata (auto-extracted if None)

        Returns:
            Job ID for tracking

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If parameters are invalid
        """
        # Validate input file
        input_path = Path(input_file).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Determine file type
        file_ext = input_path.suffix.lower().lstrip('.')
        if file_ext not in ('txt', 'epub', 'pdf'):
            raise ValueError(f"Unsupported file type: {file_ext}")

        # Get file size
        file_size = input_path.stat().st_size

        # Extract metadata if not provided
        if metadata is None and file_ext in ('epub', 'pdf'):
            metadata = self._extract_metadata(str(input_path), file_ext)

        # Create processing options
        processing_options = {
            'voice': voice,
            'speed': speed,
            'lang': lang,
            'use_gpu': use_gpu,
            'format': output_format
        }

        # Create audiobook options
        audiobook_options = None
        if file_ext in ('epub', 'pdf'):
            audiobook_options = {
                'skip_front_matter': skip_front_matter,
                'intro_text': intro_text,
                'no_intro': no_intro
            }

        # Create job
        job = AudiobookJob(
            input_file_path=str(input_path),
            input_file_type=file_ext,
            input_file_size=file_size,
            output_file_path=output_file,
            output_format=output_format,
            processing_options=processing_options,
            audiobook_options=audiobook_options,
            metadata=metadata,
            status=JobStatus.QUEUED
        )

        # Persist to database
        job_id = self.storage.create_job(job)

        # Log submission
        logger = JobLogger(job_id, self.storage)
        logger.info(
            f"Job submitted: {input_file} -> {output_file}",
            metadata={
                'input_file': str(input_path),
                'output_file': output_file,
                'file_type': file_ext,
                'file_size': file_size,
                'voice': voice,
                'speed': speed
            }
        )

        return job_id

    def get_job(self, job_id: JobID) -> Optional[AudiobookJob]:
        """
        Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            AudiobookJob instance or None if not found
        """
        return self.storage.get_job(job_id)

    def get_all_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: Optional[int] = None
    ) -> List[AudiobookJob]:
        """
        Get all jobs, optionally filtered.

        Args:
            status: Filter by status (None for all)
            limit: Maximum number to return

        Returns:
            List of jobs
        """
        return self.storage.get_all_jobs(status=status, limit=limit)

    def get_active_jobs(self) -> List[AudiobookJob]:
        """
        Get all active jobs (queued, running, paused).

        Returns:
            List of active jobs
        """
        return self.storage.get_active_jobs()

    def get_completed_jobs(self, limit: int = 50) -> List[AudiobookJob]:
        """
        Get recently completed jobs.

        Args:
            limit: Maximum number to return

        Returns:
            List of completed jobs
        """
        return self.storage.get_completed_jobs(limit=limit)

    def get_failed_jobs(self) -> List[AudiobookJob]:
        """
        Get all failed jobs that can be resumed.

        Returns:
            List of failed jobs with resume data
        """
        return self.storage.get_failed_jobs()

    def cancel_job(self, job_id: JobID) -> bool:
        """
        Cancel a running or queued job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled, False if job cannot be cancelled
        """
        job = self.storage.get_job(job_id)
        if job is None:
            return False

        if not job.can_be_cancelled():
            return False

        # Update status
        job.status = JobStatus.CANCELLED
        import time
        job.completed_at = time.time()

        self.storage.update_job(job)

        # Log cancellation
        logger = JobLogger(job_id, self.storage)
        logger.warning("Job cancelled by user")

        return True

    def resume_job(self, job_id: JobID) -> bool:
        """
        Resume a failed job.

        The job must have resume data available.

        Args:
            job_id: Job ID to resume

        Returns:
            True if resumed (requeued), False if cannot be resumed
        """
        job = self.storage.get_job(job_id)
        if job is None:
            return False

        if not job.can_be_resumed():
            return False

        # Clear error and requeue
        job.error_info = None
        job.status = JobStatus.QUEUED
        job.started_at = None
        job.completed_at = None

        self.storage.update_job(job)

        # Log resume
        logger = JobLogger(job_id, self.storage)
        logger.info(
            "Job resumed",
            metadata={
                'completed_chapters': len(job.resume_data.completed_chapters),
                'total_chapters': job.progress.total_chapters
            }
        )

        return True

    def delete_job(self, job_id: JobID):
        """
        Delete a job and all associated data.

        Args:
            job_id: Job ID to delete
        """
        self.storage.delete_job(job_id)

    def get_job_logs(
        self,
        job_id: JobID,
        level: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get log entries for a job.

        Args:
            job_id: Job ID
            level: Filter by log level (None for all)
            limit: Maximum number of entries

        Returns:
            List of log entry dictionaries
        """
        return self.storage.get_logs(job_id, level=level, limit=limit)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get job queue statistics.

        Returns:
            Dictionary with counts and metrics
        """
        return self.storage.get_statistics()

    def cleanup_old_jobs(self, days: int = 30):
        """
        Delete completed jobs older than specified days.

        Args:
            days: Age threshold in days
        """
        self.storage.delete_old_completed_jobs(days=days)

    def _extract_metadata(self, file_path: str, file_type: str) -> Optional[BookMetadata]:
        """
        Extract metadata from EPUB or PDF file.

        Args:
            file_path: Path to file
            file_type: File type (epub or pdf)

        Returns:
            BookMetadata instance or None
        """
        metadata = BookMetadata()

        try:
            if file_type == 'epub':
                metadata = self._extract_epub_metadata(file_path)
            elif file_type == 'pdf':
                metadata = self._extract_pdf_metadata(file_path)
        except Exception as e:
            # If metadata extraction fails, just return empty metadata
            # Don't block job submission
            print(f"Warning: Could not extract metadata: {e}")

        return metadata

    def _extract_epub_metadata(self, file_path: str) -> BookMetadata:
        """Extract metadata from EPUB file."""
        try:
            import ebooklib
            from ebooklib import epub

            book = epub.read_epub(file_path)

            metadata = BookMetadata()

            # Extract common metadata fields
            metadata.title = book.get_metadata('DC', 'title')
            if metadata.title and isinstance(metadata.title, list):
                metadata.title = metadata.title[0][0] if metadata.title[0] else None

            metadata.author = book.get_metadata('DC', 'creator')
            if metadata.author and isinstance(metadata.author, list):
                metadata.author = metadata.author[0][0] if metadata.author[0] else None

            metadata.publisher = book.get_metadata('DC', 'publisher')
            if metadata.publisher and isinstance(metadata.publisher, list):
                metadata.publisher = metadata.publisher[0][0] if metadata.publisher[0] else None

            metadata.language = book.get_metadata('DC', 'language')
            if metadata.language and isinstance(metadata.language, list):
                metadata.language = metadata.language[0][0] if metadata.language[0] else None

            metadata.isbn = book.get_metadata('DC', 'identifier')
            if metadata.isbn and isinstance(metadata.isbn, list):
                for identifier in metadata.isbn:
                    if identifier[0] and 'isbn' in str(identifier[0]).lower():
                        metadata.isbn = identifier[0]
                        break
                else:
                    metadata.isbn = None

            metadata.description = book.get_metadata('DC', 'description')
            if metadata.description and isinstance(metadata.description, list):
                metadata.description = metadata.description[0][0] if metadata.description[0] else None

            return metadata

        except Exception as e:
            print(f"Error extracting EPUB metadata: {e}")
            return BookMetadata()

    def _extract_pdf_metadata(self, file_path: str) -> BookMetadata:
        """Extract metadata from PDF file."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            pdf_metadata = doc.metadata

            metadata = BookMetadata()
            metadata.title = pdf_metadata.get('title')
            metadata.author = pdf_metadata.get('author')
            metadata.publisher = pdf_metadata.get('producer')

            doc.close()

            return metadata

        except Exception as e:
            print(f"Error extracting PDF metadata: {e}")
            return BookMetadata()

    def close(self):
        """Close database connections."""
        self.storage.close()
