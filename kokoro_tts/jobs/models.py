"""
Data models for the background job queue system.

All models support JSON serialization/deserialization for storage in SQLite.
"""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List


class JobStatus(str, Enum):
    """Job execution status."""
    QUEUED = "queued"           # Waiting to be processed
    RUNNING = "running"          # Currently being processed
    PAUSED = "paused"            # Temporarily stopped
    COMPLETED = "completed"      # Successfully finished
    FAILED = "failed"            # Failed with error
    CANCELLED = "cancelled"      # Cancelled by user


@dataclass
class JobProgress:
    """
    Progress tracking for a job.

    Provides detailed progress information including ETA calculation.
    """
    total_chapters: int = 0
    completed_chapters: int = 0
    total_chunks: int = 0
    completed_chunks: int = 0

    current_chapter_name: str = ""
    current_operation: str = ""

    percentage: float = 0.0
    eta_seconds: Optional[float] = None
    chunks_per_second: float = 0.0

    last_update: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'JobProgress':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    def update_percentage(self):
        """Calculate and update percentage based on completed chunks."""
        if self.total_chunks > 0:
            self.percentage = (self.completed_chunks / self.total_chunks) * 100
        else:
            self.percentage = 0.0

    def update_eta(self, elapsed_seconds: float):
        """Calculate ETA based on current progress and elapsed time."""
        if self.completed_chunks > 0 and self.total_chunks > 0:
            self.chunks_per_second = self.completed_chunks / elapsed_seconds
            if self.chunks_per_second > 0:
                remaining_chunks = self.total_chunks - self.completed_chunks
                self.eta_seconds = remaining_chunks / self.chunks_per_second
            else:
                self.eta_seconds = None
        else:
            self.eta_seconds = None

    def format_eta(self) -> str:
        """Format ETA as human-readable string."""
        if self.eta_seconds is None:
            return "Calculating..."

        seconds = int(self.eta_seconds)
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"


@dataclass
class ErrorInfo:
    """
    Information about a job failure.

    Includes error details and context for debugging and recovery.
    """
    error_type: str
    error_message: str
    traceback: str
    timestamp: float = field(default_factory=time.time)

    # Context about where the error occurred
    failed_chapter_index: Optional[int] = None
    failed_chunk_index: Optional[int] = None
    failed_operation: Optional[str] = None

    is_recoverable: bool = False
    recovery_suggestion: Optional[str] = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'ErrorInfo':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class ResumeData:
    """
    Data needed to resume a failed job.

    Tracks what has been completed so processing can continue from the failure point.
    """
    completed_chapters: List[int] = field(default_factory=list)
    completed_chunks: Dict[int, List[int]] = field(default_factory=dict)  # chapter_idx -> chunk_idxs

    # Partial audio data for the current chapter
    partial_audio_samples: Optional[str] = None  # Path to temp file if needed
    partial_chapter_index: Optional[int] = None

    # Checksum for validation
    checkpoint_hash: Optional[str] = None
    checkpoint_timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'ResumeData':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    def is_chapter_completed(self, chapter_index: int) -> bool:
        """Check if a chapter has been fully completed."""
        return chapter_index in self.completed_chapters

    def is_chunk_completed(self, chapter_index: int, chunk_index: int) -> bool:
        """Check if a specific chunk has been completed."""
        if chapter_index not in self.completed_chunks:
            return False
        return chunk_index in self.completed_chunks[chapter_index]

    def mark_chunk_completed(self, chapter_index: int, chunk_index: int):
        """Mark a chunk as completed."""
        if chapter_index not in self.completed_chunks:
            self.completed_chunks[chapter_index] = []
        if chunk_index not in self.completed_chunks[chapter_index]:
            self.completed_chunks[chapter_index].append(chunk_index)

    def mark_chapter_completed(self, chapter_index: int):
        """Mark an entire chapter as completed."""
        if chapter_index not in self.completed_chapters:
            self.completed_chapters.append(chapter_index)


@dataclass
class BookMetadata:
    """
    Metadata about the book being converted.

    Extracted from EPUB/PDF or provided by user.
    """
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    language: Optional[str] = None
    isbn: Optional[str] = None
    publication_date: Optional[str] = None
    description: Optional[str] = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'BookMetadata':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    def format_display_name(self) -> str:
        """Format a display name for the book."""
        if self.title and self.author:
            return f"{self.title} by {self.author}"
        elif self.title:
            return self.title
        else:
            return "Unknown Book"


@dataclass
class AudiobookJob:
    """
    Complete job definition for audiobook generation.

    This is the main data model that gets persisted to the database.
    Includes all information needed to process a job and track its progress.
    """
    # Identity
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    # Status
    status: JobStatus = JobStatus.QUEUED
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Input
    input_file_path: str = ""
    input_file_type: str = ""  # txt, epub, pdf
    input_file_size: Optional[int] = None

    # Output
    output_file_path: str = ""
    output_format: str = "m4a"  # wav, mp3, m4a
    output_file_size: Optional[int] = None

    # Processing options (will be serialized as JSON)
    processing_options: Dict[str, Any] = field(default_factory=dict)
    audiobook_options: Optional[Dict[str, Any]] = None

    # Progress tracking
    progress: JobProgress = field(default_factory=JobProgress)

    # Metadata
    metadata: Optional[BookMetadata] = None

    # Error handling
    error_info: Optional[ErrorInfo] = None
    resume_data: Optional[ResumeData] = None

    # Performance metrics
    processing_time_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for database storage.

        JSON-serializable fields are converted to JSON strings.
        """
        return {
            'job_id': self.job_id,
            'created_at': self.created_at,
            'status': self.status.value,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'input_file_path': self.input_file_path,
            'input_file_type': self.input_file_type,
            'input_file_size': self.input_file_size,
            'output_file_path': self.output_file_path,
            'output_format': self.output_format,
            'output_file_size': self.output_file_size,
            'processing_options': json.dumps(self.processing_options),
            'audiobook_options': json.dumps(self.audiobook_options) if self.audiobook_options else None,
            'progress': self.progress.to_json(),
            'metadata': self.metadata.to_json() if self.metadata else None,
            'error_info': self.error_info.to_json() if self.error_info else None,
            'resume_data': self.resume_data.to_json() if self.resume_data else None,
            'processing_time_seconds': self.processing_time_seconds,
            'total_chunks': self.progress.total_chunks,
            'completed_chunks': self.progress.completed_chunks,
            'total_chapters': self.progress.total_chapters,
            'completed_chapters': self.progress.completed_chapters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudiobookJob':
        """
        Create from dictionary loaded from database.

        Deserializes JSON strings back to objects.
        """
        # Deserialize nested JSON fields
        processing_options = json.loads(data['processing_options']) if data.get('processing_options') else {}
        audiobook_options = json.loads(data['audiobook_options']) if data.get('audiobook_options') else None

        progress = JobProgress.from_json(data['progress']) if data.get('progress') else JobProgress()
        metadata = BookMetadata.from_json(data['metadata']) if data.get('metadata') else None
        error_info = ErrorInfo.from_json(data['error_info']) if data.get('error_info') else None
        resume_data = ResumeData.from_json(data['resume_data']) if data.get('resume_data') else None

        return cls(
            job_id=data['job_id'],
            created_at=data['created_at'],
            status=JobStatus(data['status']),
            started_at=data.get('started_at'),
            completed_at=data.get('completed_at'),
            input_file_path=data['input_file_path'],
            input_file_type=data['input_file_type'],
            input_file_size=data.get('input_file_size'),
            output_file_path=data['output_file_path'],
            output_format=data['output_format'],
            output_file_size=data.get('output_file_size'),
            processing_options=processing_options,
            audiobook_options=audiobook_options,
            progress=progress,
            metadata=metadata,
            error_info=error_info,
            resume_data=resume_data,
            processing_time_seconds=data.get('processing_time_seconds'),
        )

    def get_elapsed_time(self) -> Optional[float]:
        """Get elapsed processing time in seconds."""
        if self.started_at is None:
            return None

        if self.completed_at is not None:
            return self.completed_at - self.started_at
        else:
            return time.time() - self.started_at

    def format_status_message(self) -> str:
        """Format a user-friendly status message."""
        if self.status == JobStatus.QUEUED:
            return "Waiting in queue..."
        elif self.status == JobStatus.RUNNING:
            if self.progress.current_operation:
                return f"{self.progress.current_operation} ({self.progress.percentage:.1f}%)"
            else:
                return f"Processing... ({self.progress.percentage:.1f}%)"
        elif self.status == JobStatus.COMPLETED:
            return "Completed successfully"
        elif self.status == JobStatus.FAILED:
            if self.error_info:
                return f"Failed: {self.error_info.error_message}"
            else:
                return "Failed"
        elif self.status == JobStatus.CANCELLED:
            return "Cancelled by user"
        elif self.status == JobStatus.PAUSED:
            return "Paused"
        else:
            return str(self.status.value)

    def can_be_resumed(self) -> bool:
        """Check if this job can be resumed after failure."""
        return (
            self.status == JobStatus.FAILED and
            self.resume_data is not None and
            self.error_info is not None and
            self.error_info.is_recoverable
        )

    def can_be_cancelled(self) -> bool:
        """Check if this job can be cancelled."""
        return self.status in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED)


# Type aliases for clarity
JobID = str
