-- Kokoro TTS Background Job Queue Database Schema
-- SQLite database for persisting audiobook generation jobs

-- Enable WAL mode for better concurrent access
-- This must be set at connection time, not in schema
-- PRAGMA journal_mode=WAL;

-- Jobs table: Core job data and state
CREATE TABLE IF NOT EXISTS jobs (
    -- Identity
    job_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,          -- Unix timestamp

    -- Status
    status TEXT NOT NULL,               -- queued, running, paused, completed, failed, cancelled
    started_at REAL,                    -- Unix timestamp
    completed_at REAL,                  -- Unix timestamp

    -- Input
    input_file_path TEXT NOT NULL,
    input_file_type TEXT NOT NULL,      -- txt, epub, pdf
    input_file_size INTEGER,            -- Bytes

    -- Output
    output_file_path TEXT NOT NULL,
    output_format TEXT NOT NULL,        -- wav, mp3, m4a
    output_file_size INTEGER,           -- Bytes (when completed)

    -- Processing options (JSON serialized)
    processing_options TEXT NOT NULL,   -- ProcessingOptions as JSON
    audiobook_options TEXT,             -- AudiobookOptions as JSON (optional)

    -- Progress tracking (JSON serialized)
    progress TEXT,                      -- JobProgress as JSON

    -- Metadata
    metadata TEXT,                      -- Book title, author, etc. as JSON

    -- Error handling (JSON serialized)
    error_info TEXT,                    -- ErrorInfo as JSON (if failed)
    resume_data TEXT,                   -- ResumeData as JSON (for resuming)

    -- Performance metrics
    processing_time_seconds REAL,
    total_chunks INTEGER DEFAULT 0,
    completed_chunks INTEGER DEFAULT 0,
    total_chapters INTEGER DEFAULT 0,
    completed_chapters INTEGER DEFAULT 0,

    -- Constraints
    CHECK(status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    CHECK(input_file_type IN ('txt', 'epub', 'pdf')),
    CHECK(output_format IN ('wav', 'mp3', 'm4a'))
);

-- Index for efficient job queue polling
CREATE INDEX IF NOT EXISTS idx_jobs_status_created
ON jobs(status, created_at);

-- Index for user dashboard queries (get all jobs)
CREATE INDEX IF NOT EXISTS idx_jobs_created
ON jobs(created_at DESC);

-- Job logs table: Structured logging per job
CREATE TABLE IF NOT EXISTS job_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    timestamp REAL NOT NULL,            -- Unix timestamp
    level TEXT NOT NULL,                -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    message TEXT NOT NULL,
    metadata TEXT,                      -- Additional context as JSON

    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    CHECK(level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

-- Index for efficient log retrieval per job
CREATE INDEX IF NOT EXISTS idx_job_logs_job_timestamp
ON job_logs(job_id, timestamp);

-- Job files table: Track input/output files for cleanup
CREATE TABLE IF NOT EXISTS job_files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,            -- input, output, temp, chunk
    file_size INTEGER,                  -- Bytes
    created_at REAL NOT NULL,           -- Unix timestamp

    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    CHECK(file_type IN ('input', 'output', 'temp', 'chunk'))
);

-- Index for cleanup operations
CREATE INDEX IF NOT EXISTS idx_job_files_job
ON job_files(job_id);

-- Worker status table: Monitor worker health
CREATE TABLE IF NOT EXISTS worker_status (
    worker_id TEXT PRIMARY KEY,         -- Process ID or UUID
    started_at REAL NOT NULL,           -- Unix timestamp
    last_heartbeat REAL NOT NULL,       -- Unix timestamp
    current_job_id TEXT,                -- Currently processing job
    status TEXT NOT NULL,               -- idle, processing, stopping

    CHECK(status IN ('idle', 'processing', 'stopping'))
);

-- Database metadata table: Schema version and settings
CREATE TABLE IF NOT EXISTS db_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Insert schema version
INSERT OR REPLACE INTO db_metadata (key, value)
VALUES ('schema_version', '1.0.0');

INSERT OR REPLACE INTO db_metadata (key, value)
VALUES ('created_at', strftime('%s', 'now'));

-- Views for common queries

-- Active jobs view: All jobs currently being processed or queued
CREATE VIEW IF NOT EXISTS active_jobs AS
SELECT
    job_id,
    status,
    created_at,
    started_at,
    input_file_path,
    output_file_path,
    progress,
    completed_chapters,
    total_chapters
FROM jobs
WHERE status IN ('queued', 'running', 'paused')
ORDER BY created_at ASC;

-- Failed jobs view: Jobs that can be resumed
CREATE VIEW IF NOT EXISTS failed_jobs AS
SELECT
    job_id,
    created_at,
    completed_at,
    input_file_path,
    output_file_path,
    error_info,
    resume_data,
    completed_chapters,
    total_chapters
FROM jobs
WHERE status = 'failed' AND resume_data IS NOT NULL
ORDER BY completed_at DESC;

-- Completed jobs view: Successfully finished jobs
CREATE VIEW IF NOT EXISTS completed_jobs AS
SELECT
    job_id,
    created_at,
    started_at,
    completed_at,
    output_file_path,
    output_file_size,
    processing_time_seconds,
    metadata
FROM jobs
WHERE status = 'completed'
ORDER BY completed_at DESC;

-- Job statistics view: Performance metrics
CREATE VIEW IF NOT EXISTS job_statistics AS
SELECT
    status,
    COUNT(*) as count,
    AVG(processing_time_seconds) as avg_processing_time,
    SUM(output_file_size) as total_output_size
FROM jobs
GROUP BY status;
