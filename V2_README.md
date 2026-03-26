# V2 - Enhanced Background Sync with Celery

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                              │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │              RequestLoggingMiddleware (Structured JSON)           │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│  │  Sync V2   │────▶│    Redis    │────▶│   Celery    │            │
│  │  Router    │     │  (Broker)   │     │   Worker    │            │
│  └─────────────┘     └─────────────┘     └─────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Multi-Level Cache                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│  │    L1      │────▶│    L2       │────▶│    L3       │            │
│  │  Memory    │     │   Redis     │     │ PostgreSQL  │            │
│  │  ~0.02ms   │     │  ~5ms       │     │   ~50ms     │            │
│  └─────────────┘     └─────────────┘     └─────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              Supabase                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Students   │  │    Stats    │  │ Leaderboard │  │  Sync Jobs  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
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
- Structured logging for all lock operations

### 3. Multi-Level Caching

| Layer | Storage | Latency | TTL | Features |
|-------|---------|---------|-----|----------|
| **L1** | Memory (dict) | ~0.02ms | 30-60s | Thread-safe, per-key TTL |
| **L2** | Redis | ~5ms | 60s | Auto-select provider, gzip compression |
| **L3** | PostgreSQL | ~50ms | - | Source of truth |

#### Auto Redis Selection
- Benchmarks Upstash vs Railway on startup
- Selects provider with lowest latency
- Logs benchmark results in structured JSON

#### Cache Stampede Protection
- **Request Coalescing**: Per-key locks prevent duplicate DB calls
- **Stale-While-Revalidate**: Serves expired data while refreshing
- **Background Refresh**: Daemon thread updates cache asynchronously

### 4. Structured Logging

All logs are JSON with consistent format:

```json
{
  "timestamp": "2026-03-26T10:30:00+00:00",
  "level": "INFO",
  "logger": "worker.tasks",
  "event": "sync_completed",
  "job_id": "abc123",
  "platform": "codeforces",
  "total": 1000,
  "success_count": 980,
  "failed_count": 20
}
```

#### Key Events

| Event | Description |
|-------|-------------|
| `sync_started` | Task began processing |
| `sync_completed` | Task finished successfully |
| `sync_failed` | Task encountered error |
| `retry_triggered` | Retry for failed students |
| `lock_acquired` | Redis lock obtained |
| `lock_rejected` | Lock denied (already held) |
| `lock_released` | Lock released |
| `cache_hit` | Data found (source: memory/redis) |
| `cache_miss` | Data not found |
| `cache_stale_served` | Expired data while refreshing |
| `cache_refreshed` | Background refresh done |
| `cache_lock_acquired` | DB fetch lock obtained |
| `cache_waiting` | Request waiting for lock |
| `http_request` | API request completed |
| `large_payload` | Payload >100KB compressed |

### 5. Enhanced Job Tracking
- `success_count` / `failed_count` for granular tracking
- `progress` percentage computed dynamically
- `triggered_by` field ('api', 'cron', 'admin')
- Structured JSON error messages
- Failed student list stored for retry

### 6. Observability
- Stuck job detection (>15 min running)
- Lock + DB consistency checker
- Cache stats endpoint
- Request duration logging
- Redis benchmark results

## New Files

```
├── worker/
│   ├── __init__.py
│   ├── celery_app.py      # Celery configuration
│   └── tasks.py           # Background sync tasks (with logging)
├── services/
│   ├── __init__.py
│   └── job_service.py     # Job management service layer
├── utils/
│   ├── __init__.py
│   ├── logger.py          # Structured logging + cache helpers
│   └── lock.py            # Redis locking (with logging)
├── middleware/
│   ├── __init__.py
│   └── logging.py         # Request logging middleware
├── routers/
│   └── sync_v2.py         # V2 endpoints (with logging)
└── migrations/
    └── 002_enhance_sync_jobs.sql
```

## Setup

### 1. Install Dependencies
```bash
pip install celery redis
```

### 2. Configure Environment
```env
# Redis Configuration (auto-selects fastest)
UPSTASH_URL=https://xxx.upstash.io
UPSTASH_TOKEN=xxx
RAILWAY_REDIS_URL=redis://xxx.railway.app:xxx

# Celery
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379
```

### 3. Run Database Migration
Execute `migrations/002_enhance_sync_jobs.sql` in Supabase SQL editor.

## Running

### Terminal 1 - FastAPI Server
```bash
uvicorn main:app --reload --log-level info
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
| POST | `/v2/sync/codeforces/retry/{job_id}` | Retry failed students |
| GET | `/v2/sync/status/{task_id}` | Get Celery task status |
| GET | `/v2/sync/jobs` | Get recent jobs (with filters) |
| GET | `/v2/sync/jobs/{id}` | Get single job details |
| GET | `/v2/sync/jobs/stuck/list` | Get stuck jobs (>15 min) |
| GET | `/v2/sync/consistency-check` | Check lock vs DB consistency |

### Status Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/cache/stats` | Cache performance stats |

## Usage Examples

### Trigger Sync
```bash
curl -X POST http://localhost:8000/v2/sync/codeforces

# Response:
{
  "task_id": "abc-123-def",
  "message": "Codeforces sync task queued successfully",
  "status_url": "/v2/sync/status/abc-123-def"
}
```

### Check Cache Stats
```bash
curl http://localhost:8000/cache/stats

# Response:
{
  "memory": {"total": 5, "expired": 1},
  "redis_providers": ["upstash", "railway"],
  "selected_redis": "railway",
  "redis_stats": {
    "railway": {"avg_get_ms": 5.2, "avg_set_ms": 3.1}
  }
}
```

### Retry Failed Students
```bash
curl -X POST http://localhost:8000/v2/sync/codeforces/retry/123e4567-e89b-12d3-a456-426614174000

# Response:
{
  "task_id": "xyz-789",
  "message": "Retry queued for 20 failed students",
  "original_job_id": "123e4567-e89b-12d3-a456-426614174000",
  "students_to_retry": 20
}
```

## Log Output Examples

### Sync Task Started
```json
{"level": "INFO", "event": "task_started", "task_id": "abc123", "platform": "codeforces"}
{"level": "INFO", "event": "sync_started", "job_id": "abc123", "platform": "codeforces", "students_count": 1000}
```

### Cache Operations
```json
{"level": "INFO", "event": "cache_hit", "source": "memory", "key": "analytics_leetcode", "duration_ms": 0.02}
{"level": "INFO", "event": "cache_miss", "source": "redis", "provider": "railway", "key": "analytics_leetcode", "redis_fetch_ms": 5.2}
{"level": "INFO", "event": "db_fetch", "key": "analytics_leetcode", "db_fetch_ms": 145.23}
{"level": "INFO", "event": "cache_set", "source": "both", "provider": "railway", "key": "analytics_leetcode", "data_size": 480000, "compressed": true}
```

### Cache Stampede Protection
```json
{"level": "INFO", "event": "cache_lock_acquired", "key": "analytics_codeforces"}
{"level": "INFO", "event": "cache_waiting", "key": "analytics_codeforces"}
{"level": "INFO", "event": "db_fetch", "key": "analytics_codeforces", "db_fetch_ms": 500.0}
{"level": "INFO", "event": "cache_refreshed", "key": "analytics_codeforces", "duration_ms": 520.0}
```

### Request Logging
```json
{"level": "INFO", "event": "http_request", "method": "POST", "path": "/v2/sync/codeforces", "status_code": 200, "duration_ms": 45.23}
```

## Database Schema Changes

### New Columns in `sync_jobs`
```sql
ALTER TABLE sync_jobs ADD COLUMN success_count INTEGER DEFAULT 0;
ALTER TABLE sync_jobs ADD COLUMN failed_count INTEGER DEFAULT 0;
ALTER TABLE sync_jobs ADD COLUMN failed_students JSONB DEFAULT '[]';
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
         Lock acquired? → No → Log: "lock_rejected" → Return 409
              ↓ Yes
         Log: "lock_acquired"
         Queue Celery task
         
Task completes → finally: release_lock(platform)
                       ↓
                  Log: "lock_released"
```

### Safety Features
- **TTL**: Lock auto-expires after 10 minutes
- **Manual Release**: Always released in `finally` block
- **Crash Recovery**: If worker crashes, lock expires
- **Consistency Check**: Endpoint to detect orphan locks

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
- `get_retry_job_info()` - Get failed students for retry

## Key Differences V1 vs V2

| Aspect | V1 | V2 |
|--------|----|----|
| Sync execution | In API request | Background worker |
| Response | Waits for completion | Returns immediately |
| Job locking | None | Redis-based with logging |
| Progress tracking | processed_students | success/failed counts |
| Stuck detection | None | Automatic |
| Error format | Plain text | Structured JSON |
| Caching | Redis only | Multi-level (Memory + Redis) |
| Cache protection | None | Stampede protection |
| Logging | Print statements | Structured JSON |

## Backward Compatibility

- V1 endpoints (`/sync/*`) remain unchanged
- V2 uses `/v2/sync/*` prefix
- No breaking changes to existing functionality
- Database changes are additive only
- Existing routers updated to use CacheService

## Troubleshooting

### Check Cache Stats
```bash
curl http://localhost:8000/cache/stats
```

### Check Redis Directly
```bash
redis-cli
> GET lock:sync:codeforces
> DEL lock:sync:codeforces
```

### Check Consistency
```bash
curl http://localhost:8000/v2/sync/consistency-check
```

### View Recent Jobs
```bash
curl "http://localhost:8000/v2/sync/jobs?status=running&limit=5"
```

### Sample Log Output
```bash
# Start server and check logs
uvicorn main:app --log-level info

# Expected output format (JSON):
{"timestamp": "...", "level": "INFO", "logger": "worker.tasks", "event": "sync_started", ...}
{"timestamp": "...", "level": "INFO", "logger": "app.middleware", "event": "http_request", ...}
```
