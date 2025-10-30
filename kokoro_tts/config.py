"""Performance configuration for Kokoro TTS.

This module provides configuration options for optimizing TTS performance
through parallel processing and other performance enhancements.
"""

import os
import multiprocessing
from dataclasses import dataclass


@dataclass
class PerformanceConfig:
    """Configuration for performance optimizations.

    Attributes:
        use_parallel: Enable parallel chunk processing (default: False for safety)
        max_workers: Maximum worker threads for parallel processing (default: CPU count)
        use_async_io: Enable asynchronous file I/O (default: False)
        io_queue_size: Maximum queued I/O operations (default: 10)
        use_memory_streaming: Enable memory-efficient streaming (default: False)
        use_gpu_batching: Enable GPU batch processing (Phase 3, default: False)
        gpu_batch_size: Batch size for GPU processing (Phase 3, default: 4)
    """
    use_parallel: bool = False
    max_workers: int = None
    use_async_io: bool = False
    io_queue_size: int = 10
    use_memory_streaming: bool = False
    use_gpu_batching: bool = False
    gpu_batch_size: int = 4

    def __post_init__(self):
        """Initialize default values after dataclass init."""
        if self.max_workers is None:
            self.max_workers = multiprocessing.cpu_count()

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables.

        Environment variables:
            KOKORO_USE_PARALLEL: Enable parallel processing ('true'/'false')
            KOKORO_MAX_WORKERS: Maximum worker threads (integer)
            KOKORO_ASYNC_IO: Enable asynchronous I/O ('true'/'false')
            KOKORO_IO_QUEUE_SIZE: Maximum queued I/O operations (integer)
            KOKORO_MEMORY_STREAMING: Enable memory streaming ('true'/'false')
            KOKORO_GPU_BATCHING: Enable GPU batching ('true'/'false')
            KOKORO_GPU_BATCH_SIZE: GPU batch size (integer)

        Returns:
            PerformanceConfig instance with values from environment
        """
        max_workers_env = os.getenv('KOKORO_MAX_WORKERS', '')
        max_workers = int(max_workers_env) if max_workers_env else None

        return cls(
            use_parallel=os.getenv('KOKORO_USE_PARALLEL', 'false').lower() == 'true',
            max_workers=max_workers,
            use_async_io=os.getenv('KOKORO_ASYNC_IO', 'false').lower() == 'true',
            io_queue_size=int(os.getenv('KOKORO_IO_QUEUE_SIZE', '10')),
            use_memory_streaming=os.getenv('KOKORO_MEMORY_STREAMING', 'false').lower() == 'true',
            use_gpu_batching=os.getenv('KOKORO_GPU_BATCHING', 'false').lower() == 'true',
            gpu_batch_size=int(os.getenv('KOKORO_GPU_BATCH_SIZE', '4')),
        )
