"""
SQLite storage layer for job persistence.

Provides thread-safe database operations for the job queue system.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import AudiobookJob, JobStatus, JobID


class JobStorage:
    """
    SQLite-based storage for job persistence.

    Features:
    - Thread-safe operations using connection pooling
    - WAL mode for better concurrent access
    - Atomic queue operations
    - Transaction support
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize storage.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.kokoro-tts/jobs.db
        """
        if db_path is None:
            # Default to user's home directory
            home_dir = Path.home()
            kokoro_dir = home_dir / ".kokoro-tts"
            kokoro_dir.mkdir(exist_ok=True)
            db_path = str(kokoro_dir / "jobs.db")

        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()

        # Initialize database
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a thread-local database connection.

        Each thread gets its own connection for thread safety.
        """
        if not hasattr(self._local, 'connection'):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # Enable column access by name

            # Enable WAL mode for better concurrent access
            conn.execute("PRAGMA journal_mode=WAL")

            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys=ON")

            self._local.connection = conn

        return self._local.connection

    @contextmanager
    def _transaction(self):
        """
        Context manager for database transactions.

        Automatically commits on success, rolls back on error.
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _initialize_database(self):
        """Initialize database schema from schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        conn = self._get_connection()
        conn.executescript(schema_sql)
        conn.commit()

    # Job CRUD Operations

    def create_job(self, job: AudiobookJob) -> JobID:
        """
        Create a new job in the database.

        Args:
            job: AudiobookJob instance to persist

        Returns:
            Job ID of created job
        """
        job_dict = job.to_dict()

        with self._transaction() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    job_id, created_at, status, started_at, completed_at,
                    input_file_path, input_file_type, input_file_size,
                    output_file_path, output_format, output_file_size,
                    processing_options, audiobook_options,
                    progress, metadata,
                    error_info, resume_data,
                    processing_time_seconds,
                    total_chunks, completed_chunks,
                    total_chapters, completed_chapters
                ) VALUES (
                    :job_id, :created_at, :status, :started_at, :completed_at,
                    :input_file_path, :input_file_type, :input_file_size,
                    :output_file_path, :output_format, :output_file_size,
                    :processing_options, :audiobook_options,
                    :progress, :metadata,
                    :error_info, :resume_data,
                    :processing_time_seconds,
                    :total_chunks, :completed_chunks,
                    :total_chapters, :completed_chapters
                )
            """, job_dict)

        return job.job_id

    def get_job(self, job_id: JobID) -> Optional[AudiobookJob]:
        """
        Retrieve a job by ID.

        Args:
            job_id: Job ID to retrieve

        Returns:
            AudiobookJob instance or None if not found
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM jobs WHERE job_id = ?
        """, (job_id,))

        row = cursor.fetchone()
        if row is None:
            return None

        return AudiobookJob.from_dict(dict(row))

    def update_job(self, job: AudiobookJob):
        """
        Update an existing job.

        Args:
            job: AudiobookJob instance with updated data
        """
        job_dict = job.to_dict()

        with self._transaction() as conn:
            conn.execute("""
                UPDATE jobs SET
                    status = :status,
                    started_at = :started_at,
                    completed_at = :completed_at,
                    output_file_size = :output_file_size,
                    progress = :progress,
                    error_info = :error_info,
                    resume_data = :resume_data,
                    processing_time_seconds = :processing_time_seconds,
                    total_chunks = :total_chunks,
                    completed_chunks = :completed_chunks,
                    total_chapters = :total_chapters,
                    completed_chapters = :completed_chapters
                WHERE job_id = :job_id
            """, job_dict)

    def delete_job(self, job_id: JobID):
        """
        Delete a job and all related data (cascades to logs and files).

        Args:
            job_id: Job ID to delete
        """
        with self._transaction() as conn:
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))

    def get_all_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: Optional[int] = None
    ) -> List[AudiobookJob]:
        """
        Get all jobs, optionally filtered by status.

        Args:
            status: Filter by job status (None for all)
            limit: Maximum number of jobs to return

        Returns:
            List of AudiobookJob instances
        """
        conn = self._get_connection()

        query = "SELECT * FROM jobs"
        params = []

        if status is not None:
            query += " WHERE status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        return [AudiobookJob.from_dict(dict(row)) for row in rows]

    def get_active_jobs(self) -> List[AudiobookJob]:
        """
        Get all active jobs (queued, running, paused).

        Returns:
            List of active AudiobookJob instances
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM jobs
            WHERE status IN ('queued', 'running', 'paused')
            ORDER BY created_at ASC
        """)
        rows = cursor.fetchall()

        return [AudiobookJob.from_dict(dict(row)) for row in rows]

    def get_failed_jobs(self) -> List[AudiobookJob]:
        """
        Get all failed jobs that can be resumed.

        Returns:
            List of failed AudiobookJob instances with resume data
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM failed_jobs")
        rows = cursor.fetchall()

        jobs = []
        for row in rows:
            job = self.get_job(row['job_id'])
            if job:
                jobs.append(job)

        return jobs

    def get_completed_jobs(self, limit: Optional[int] = None) -> List[AudiobookJob]:
        """
        Get all completed jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of completed AudiobookJob instances
        """
        return self.get_all_jobs(status=JobStatus.COMPLETED, limit=limit)

    # Queue Operations (Atomic)

    def get_next_queued_job(self) -> Optional[AudiobookJob]:
        """
        Get the next queued job and atomically mark it as running.

        This is the critical method for the worker to claim jobs from the queue.
        Uses a transaction to ensure only one worker claims each job.

        Returns:
            AudiobookJob instance or None if queue is empty
        """
        with self._lock:  # Extra safety for concurrent access
            with self._transaction() as conn:
                # Find the next queued job
                cursor = conn.execute("""
                    SELECT job_id FROM jobs
                    WHERE status = 'queued'
                    ORDER BY created_at ASC
                    LIMIT 1
                """)

                row = cursor.fetchone()
                if row is None:
                    return None

                job_id = row['job_id']

                # Atomically mark it as running
                import time
                conn.execute("""
                    UPDATE jobs
                    SET status = 'running', started_at = ?
                    WHERE job_id = ?
                """, (time.time(), job_id))

        # Return the full job object
        return self.get_job(job_id)

    def requeue_job(self, job_id: JobID):
        """
        Reset a job to queued status.

        Useful for retrying failed jobs or reprocessing.

        Args:
            job_id: Job ID to requeue
        """
        with self._transaction() as conn:
            conn.execute("""
                UPDATE jobs
                SET status = 'queued',
                    started_at = NULL,
                    completed_at = NULL,
                    error_info = NULL
                WHERE job_id = ?
            """, (job_id,))

    # Job Log Operations

    def add_log(
        self,
        job_id: JobID,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a log entry for a job.

        Args:
            job_id: Job ID
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            metadata: Optional additional context
        """
        import time
        import json

        metadata_json = json.dumps(metadata) if metadata else None

        with self._transaction() as conn:
            conn.execute("""
                INSERT INTO job_logs (job_id, timestamp, level, message, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, time.time(), level, message, metadata_json))

    def get_logs(
        self,
        job_id: JobID,
        level: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get log entries for a job.

        Args:
            job_id: Job ID
            level: Filter by log level (None for all)
            limit: Maximum number of entries to return

        Returns:
            List of log entry dictionaries
        """
        conn = self._get_connection()

        query = "SELECT * FROM job_logs WHERE job_id = ?"
        params = [job_id]

        if level is not None:
            query += " AND level = ?"
            params.append(level)

        query += " ORDER BY timestamp DESC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        import json
        logs = []
        for row in rows:
            log_dict = dict(row)
            if log_dict.get('metadata'):
                log_dict['metadata'] = json.loads(log_dict['metadata'])
            logs.append(log_dict)

        return logs

    # Job File Operations

    def add_job_file(
        self,
        job_id: JobID,
        file_path: str,
        file_type: str,
        file_size: Optional[int] = None
    ):
        """
        Track a file associated with a job.

        Args:
            job_id: Job ID
            file_path: Path to file
            file_type: Type of file (input, output, temp, chunk)
            file_size: Size in bytes
        """
        import time

        with self._transaction() as conn:
            conn.execute("""
                INSERT INTO job_files (job_id, file_path, file_type, file_size, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, file_path, file_type, file_size, time.time()))

    def get_job_files(
        self,
        job_id: JobID,
        file_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get files associated with a job.

        Args:
            job_id: Job ID
            file_type: Filter by file type (None for all)

        Returns:
            List of file info dictionaries
        """
        conn = self._get_connection()

        query = "SELECT * FROM job_files WHERE job_id = ?"
        params = [job_id]

        if file_type is not None:
            query += " AND file_type = ?"
            params.append(file_type)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    # Worker Status Operations

    def update_worker_heartbeat(
        self,
        worker_id: str,
        current_job_id: Optional[JobID] = None
    ):
        """
        Update worker heartbeat to indicate it's alive.

        Args:
            worker_id: Worker process ID
            current_job_id: Currently processing job (None if idle)
        """
        import time

        status = 'processing' if current_job_id else 'idle'

        with self._transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO worker_status
                (worker_id, started_at, last_heartbeat, current_job_id, status)
                VALUES (?, COALESCE((SELECT started_at FROM worker_status WHERE worker_id = ?), ?), ?, ?, ?)
            """, (worker_id, worker_id, time.time(), time.time(), current_job_id, status))

    def get_worker_status(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a worker.

        Args:
            worker_id: Worker process ID

        Returns:
            Worker status dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM worker_status WHERE worker_id = ?
        """, (worker_id,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def remove_worker(self, worker_id: str):
        """
        Remove a worker from the status table (on shutdown).

        Args:
            worker_id: Worker process ID
        """
        with self._transaction() as conn:
            conn.execute("DELETE FROM worker_status WHERE worker_id = ?", (worker_id,))

    # Statistics

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get job queue statistics.

        Returns:
            Dictionary with counts by status and performance metrics
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM job_statistics")
        rows = cursor.fetchall()

        stats = {}
        for row in rows:
            stats[row['status']] = {
                'count': row['count'],
                'avg_processing_time': row['avg_processing_time'],
                'total_output_size': row['total_output_size']
            }

        return stats

    # Cleanup Operations

    def delete_old_completed_jobs(self, days: int = 30):
        """
        Delete completed jobs older than specified days.

        Args:
            days: Number of days to keep
        """
        import time

        cutoff = time.time() - (days * 24 * 60 * 60)

        with self._transaction() as conn:
            conn.execute("""
                DELETE FROM jobs
                WHERE status = 'completed' AND completed_at < ?
            """, (cutoff,))

    def vacuum(self):
        """
        Reclaim disk space by vacuuming the database.

        Should be called periodically (e.g., weekly).
        """
        conn = self._get_connection()
        conn.execute("VACUUM")

    def close(self):
        """Close database connections."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')
