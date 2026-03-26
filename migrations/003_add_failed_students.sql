-- Migration: Add failed_students column for retry mechanism
-- Date: 2026-03-26
-- Description: Track failed students per sync job for retry functionality

ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS failed_students JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_sync_jobs_failed_students ON sync_jobs USING GIN (failed_students);

-- Verification:
-- SELECT id, platform, status, failed_students FROM sync_jobs LIMIT 5;
