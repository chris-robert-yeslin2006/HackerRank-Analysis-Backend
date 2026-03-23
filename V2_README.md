# V2 - Enhanced Background Sync with Celery

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────▶│   Redis     │────▶│   Celery    │
│   Server    │     │  (Broker)   │     │   Worker    │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       │
       │                                       │
       ▼                                       ▼
┌─────────────────────────────────────────────────────┐
│                    Supabase                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Students   │  │ Sync Jobs   │  │ Platform    │  │
│  │             │  │ (Enhanced)  │  │ Stats       │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Features

### 1. Celery Background Processing
- Long-running sync tasks run in background workers
- API returns immediately with task_id
- No request timeout issues

### 2. Redis-Based Job Locking
- Prevents duplicate sync jobs for same platform
- Uses `SET NX EX` pattern (atomic operation)
- Lock auto-expires after 10 minutes (safety net)
- Always released in `finally` block

### 3. Enhanced Job Tracking
- `success_count` / `failed_count` for granular tracking
- `progress` percentage computed dynamically
- `triggered_by` field ('api', 'cron', 'admin')
- Structured JSON error messages

### 4. Observability
- Stuck job detection (>15 min running)
- Lock + DB consistency checker
- Progress updates during sync

## New Files

```
├── worker/
│   ├── __init__.py
│   ├── celery_app.py      # Celery configuration
│   └── tasks.py           # Background sync tasks
├── services/
│   ├── __init__.py
│   └── job_service.py     # Job management service layer
├── utils/
│   ├── __init__.py
│   └── lock.py            # Redis locking utilities
├── migrations/
│   └── 002_enhance_sync_jobs.sql  # Database migration
└── routers/
    └── sync_v2.py          # V2 endpoints
```

## Setup

### 1. Install Dependencies
```bash
pip install celery redis
```

### 2. Run Database Migration
Execute `migrations/002_enhance_sync_jobs.sql` in Supabase SQL editor.

### 3. Configure Redis
Add to `.env`:
```env
REDIS_URL=redis://default:YOUR_PASSWORD@host:port
CELERY_BROKER_URL=redis://default:YOUR_PASSWORD@host:port
CELERY_RESULT_BACKEND=redis://default:YOUR_PASSWORD@host:port
```

## Running

### Terminal 1 - FastAPI Server
```bash
uvicorn main:app --reload --port 8000
```

### Terminal 2 - Celery Worker
```bash
celery -A worker.celery_app worker --loglevel=info -Q sync --pool=solo
```

## V2 Endpoints

### Sync Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v2/sync/codeforces` | Trigger Codeforces sync |
| GET | `/v2/sync/status/{task_id}` | Get Celery task status |
| GET | `/v2/sync/jobs` | Get recent jobs (with filters) |
| GET | `/v2/sync/jobs/{id}` | Get single job details |
| GET | `/v2/sync/jobs/stuck/list` | Get stuck jobs (>15 min) |
| GET | `/v2/sync/consistency-check` | Check lock vs DB consistency |

### Query Parameters for `/v2/sync/jobs`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 10 | Number of jobs (1-100) |
| status | string | null | Filter: pending, running, success, failed |
| platform | string | null | Filter: codeforces, leetcode, codechef |

## Usage Examples

### Trigger Sync
```bash
curl -X POST http://localhost:8000/v2/sync/codeforces

# Response (success):
{
  "task_id": "abc-123-def",
  "message": "Codeforces sync task queued successfully",
  "status_url": "/v2/sync/status/abc-123-def"
}

# Response (if already running):
{
  "message": "Sync already running",
  "status": "locked"
}
```

### Get Job Status
```bash
curl http://localhost:8000/v2/sync/status/abc-123-def

# Response:
{
  "task_id": "abc-123-def",
  "status": "SUCCESS",
  "result": {"status": "success", "total": 1000, "success": 980, "failed": 20}
}
```

### Get Jobs with Filters
```bash
# Running jobs only
curl "http://localhost:8000/v2/sync/jobs?status=running&limit=5"

# Codeforces jobs
curl "http://localhost:8000/v2/sync/jobs?platform=codeforces&limit=10"
```

### Get Enhanced Job Details
```bash
curl http://localhost:8000/v2/sync/jobs/123e4567-e89b-12d3-a456-426614174000

# Response:
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "platform": "codeforces",
  "status": "success",
  "triggered_by": "api",
  "started_at": "2026-03-23T10:00:00Z",
  "completed_at": "2026-03-23T10:05:30Z",
  "total_students": 1000,
  "processed_students": 1000,
  "success_count": 980,
  "failed_count": 20,
  "progress": 100.0,
  "error": null
}
```

### Check Stuck Jobs
```bash
curl http://localhost:8000/v2/sync/jobs/stuck/list

# Response:
{
  "stuck_jobs": [...],
  "count": 2,
  "message": "Found 2 stuck job(s)"
}
```

### Check Consistency
```bash
curl http://localhost:8000/v2/sync/consistency-check

# Response:
{
  "checked_at": "2026-03-23T10:00:00Z",
  "inconsistencies": [...],
  "clean": false
}
```

## Database Schema Changes

### New Columns in `sync_jobs`
```sql
ALTER TABLE sync_jobs ADD COLUMN success_count INTEGER DEFAULT 0;
ALTER TABLE sync_jobs ADD COLUMN failed_count INTEGER DEFAULT 0;
ALTER TABLE sync_jobs ADD COLUMN triggered_by TEXT DEFAULT 'api';
```

### New Indexes
```sql
CREATE INDEX idx_sync_jobs_status_started ON sync_jobs(status, started_at);
CREATE INDEX idx_sync_jobs_platform ON sync_jobs(platform);
```

## Lock Mechanism

```
Request → acquire_lock(platform)
              ↓
         Redis SET NX EX 600
              ↓
         Lock acquired? → No → Return 409 "Sync already running"
              ↓ Yes
         Queue Celery task
         
Task completes → finally: release_lock(platform)
```

### Safety Features
- **TTL**: Lock auto-expires after 10 minutes
- **Manual Release**: Always released in `finally` block
- **Crash Recovery**: If worker crashes, lock expires

## Service Layer

`services/job_service.py` provides:
- `create_job()` - Create new job record
- `start_job()` - Mark job as running
- `update_job_progress()` - Update counts and progress
- `complete_job()` - Mark job as success
- `fail_job()` - Mark job as failed with error
- `get_jobs()` - Fetch jobs with filters
- `get_stuck_jobs()` - Find jobs running >15 min
- `check_lock_db_consistency()` - Detect orphan locks
- `build_job_response()` - Add computed fields

## Key Differences V1 vs V2

| Aspect | V1 | V2 |
|--------|----|----|
| Sync execution | In API request | Background worker |
| Response | Waits for completion | Returns immediately |
| Job locking | None | Redis-based |
| Progress tracking | processed_students | success/failed counts |
| Stuck detection | None | Automatic |
| Error format | Plain text | Structured JSON |

## Backward Compatibility

- V1 endpoints (`/sync/*`) remain unchanged
- V2 uses `/v2/sync/*` prefix
- No breaking changes to existing functionality
- Database changes are additive only

## Troubleshooting

### Lock stuck?
```bash
# Check Redis directly
redis-cli
> GET lock:sync:codeforces

# Manually release
> DEL lock:sync:codeforces
```

### Check consistency
```bash
curl http://localhost:8000/v2/sync/consistency-check
```

### View recent jobs
```bash
curl "http://localhost:8000/v2/sync/jobs?status=running&limit=5"
```
