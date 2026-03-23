-- Migration: Enhanced Sync Jobs Table
-- Date: 2026-03-23
-- Description: Add granular tracking columns to sync_jobs table

-- 1. Add granular count columns
ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0;
ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS failed_count INTEGER DEFAULT 0;

-- 2. Add triggered_by column (optional enhancement)
ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS triggered_by TEXT DEFAULT 'api';

-- 3. Update existing rows to set triggered_by
UPDATE sync_jobs SET triggered_by = 'api' WHERE triggered_by IS NULL;

-- 4. Add composite index for stuck job detection queries
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status_started ON sync_jobs(status, started_at);

-- 5. Add index for platform filtering
CREATE INDEX IF NOT EXISTS idx_sync_jobs_platform ON sync_jobs(platform);

-- Verification query (run in SQL editor):
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'sync_jobs';
