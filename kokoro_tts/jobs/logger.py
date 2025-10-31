"""
Structured logging system for jobs.

Provides thread-safe logging with persistence to the database.
"""

import logging
import threading
from typing import Optional, Dict, Any

from .models import JobID
from .storage import JobStorage


class JobLogger:
    """
    Logger for job-specific structured logging.

    Features:
    - Thread-safe logging operations
    - Persistence to database via JobStorage
    - Structured metadata support
    - Standard Python logging integration
    """

    # Log levels
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __init__(self, job_id: JobID, storage: JobStorage):
        """
        Initialize logger for a specific job.

        Args:
            job_id: Job ID to log for
            storage: JobStorage instance for persistence
        """
        self.job_id = job_id
        self.storage = storage
        self._lock = threading.Lock()

        # Optional Python logger integration
        self._py_logger = logging.getLogger(f"kokoro.job.{job_id}")

    def _log(
        self,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        also_print: bool = False
    ):
        """
        Internal logging method.

        Args:
            level: Log level
            message: Log message
            metadata: Optional structured metadata
            also_print: Whether to also print to console
        """
        with self._lock:
            # Persist to database
            self.storage.add_log(
                job_id=self.job_id,
                level=level,
                message=message,
                metadata=metadata
            )

            # Optionally log to Python logger
            if also_print or self._py_logger.isEnabledFor(self._level_to_py_level(level)):
                py_level = self._level_to_py_level(level)
                extra_msg = f" [{metadata}]" if metadata else ""
                self._py_logger.log(py_level, f"{message}{extra_msg}")

    @staticmethod
    def _level_to_py_level(level: str) -> int:
        """Convert string level to Python logging level."""
        return {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }.get(level, logging.INFO)

    def debug(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log debug message."""
        self._log(self.DEBUG, message, metadata)

    def info(self, message: str, metadata: Optional[Dict[str, Any]] = None, also_print: bool = False):
        """Log info message."""
        self._log(self.INFO, message, metadata, also_print)

    def warning(self, message: str, metadata: Optional[Dict[str, Any]] = None, also_print: bool = True):
        """Log warning message."""
        self._log(self.WARNING, message, metadata, also_print)

    def error(self, message: str, metadata: Optional[Dict[str, Any]] = None, also_print: bool = True):
        """Log error message."""
        self._log(self.ERROR, message, metadata, also_print)

    def critical(self, message: str, metadata: Optional[Dict[str, Any]] = None, also_print: bool = True):
        """Log critical message."""
        self._log(self.CRITICAL, message, metadata, also_print)

    def log_progress(
        self,
        current: int,
        total: int,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log progress update.

        Args:
            current: Current progress value
            total: Total progress value
            operation: Description of current operation
            metadata: Optional additional context
        """
        percentage = (current / total * 100) if total > 0 else 0

        progress_metadata = {
            "current": current,
            "total": total,
            "percentage": percentage,
            **(metadata or {})
        }

        self.info(
            f"{operation}: {current}/{total} ({percentage:.1f}%)",
            metadata=progress_metadata
        )

    def log_chapter_start(self, chapter_index: int, chapter_name: str, total_chapters: int):
        """Log start of chapter processing."""
        self.info(
            f"Starting chapter {chapter_index + 1}/{total_chapters}: {chapter_name}",
            metadata={
                "chapter_index": chapter_index,
                "chapter_name": chapter_name,
                "total_chapters": total_chapters
            }
        )

    def log_chapter_complete(
        self,
        chapter_index: int,
        chapter_name: str,
        chunks_processed: int,
        duration_seconds: float
    ):
        """Log completion of chapter processing."""
        self.info(
            f"Completed chapter {chapter_index + 1}: {chapter_name} "
            f"({chunks_processed} chunks in {duration_seconds:.1f}s)",
            metadata={
                "chapter_index": chapter_index,
                "chapter_name": chapter_name,
                "chunks_processed": chunks_processed,
                "duration_seconds": duration_seconds
            }
        )

    def log_error_with_context(
        self,
        error: Exception,
        context: str,
        chapter_index: Optional[int] = None,
        chunk_index: Optional[int] = None
    ):
        """
        Log an error with full context.

        Args:
            error: Exception that occurred
            context: Description of what was being done
            chapter_index: Chapter being processed (if applicable)
            chunk_index: Chunk being processed (if applicable)
        """
        import traceback

        error_metadata = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "traceback": traceback.format_exc()
        }

        if chapter_index is not None:
            error_metadata["chapter_index"] = chapter_index

        if chunk_index is not None:
            error_metadata["chunk_index"] = chunk_index

        self.error(
            f"Error during {context}: {type(error).__name__}: {str(error)}",
            metadata=error_metadata
        )

    def get_recent_logs(self, limit: int = 50) -> list:
        """
        Get recent log entries for this job.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of log entry dictionaries
        """
        return self.storage.get_logs(self.job_id, limit=limit)

    def get_error_logs(self) -> list:
        """
        Get all error and critical logs for this job.

        Returns:
            List of error log entry dictionaries
        """
        error_logs = self.storage.get_logs(self.job_id, level=self.ERROR)
        critical_logs = self.storage.get_logs(self.job_id, level=self.CRITICAL)

        # Combine and sort by timestamp
        all_errors = error_logs + critical_logs
        all_errors.sort(key=lambda x: x['timestamp'], reverse=True)

        return all_errors


def create_logger(job_id: JobID, storage: Optional[JobStorage] = None) -> JobLogger:
    """
    Factory function to create a JobLogger.

    Args:
        job_id: Job ID to log for
        storage: JobStorage instance (creates default if not provided)

    Returns:
        JobLogger instance
    """
    if storage is None:
        storage = JobStorage()

    return JobLogger(job_id, storage)
