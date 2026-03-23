# V2 - Celery Background Sync

## New Architecture

```
API Layer (FastAPI) → Celery Task Queue → Worker Process
         ↓                                    ↓
    Triggers task                    Processes sync logic
    Returns task_id                 Updates database
```

## New Files

- `worker/celery_app.py` - Celery configuration
- `worker/tasks.py` - Background sync tasks
- `routers/sync_v2.py` - New v2 endpoints

## Setup

1. Install dependencies:
```bash
pip install celery redis
```

2. Ensure Redis is running (Upstash URL is in .env):
```bash
# For local Redis:
redis-server
```

## Running

### Terminal 1 - FastAPI Server
```bash
uvicorn main:app --reload --port 8000
```

### Terminal 2 - Celery Worker
```bash
celery -A worker.celery_app worker --loglevel=info -Q sync
```

## New V2 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v2/sync/codeforces` | Trigger Codeforces sync (returns immediately) |
| GET | `/v2/sync/status/{task_id}` | Get sync task status |
| GET | `/v2/sync/jobs` | Get recent sync jobs |

## Usage Example

```bash
# Trigger sync
curl -X POST http://localhost:8000/v2/sync/codeforces

# Response:
# {
#   "task_id": "abc-123-def",
#   "message": "Codeforces sync task queued successfully",
#   "status_url": "/v2/sync/status/abc-123-def"
# }

# Check status
curl http://localhost:8000/v2/sync/status/abc-123-def

# Response:
# {
#   "task_id": "abc-123-def",
#   "status": "SUCCESS",
#   "result": {"status": "success", "total": 50, "success": 48, "failed": 2}
# }
```

## Key Differences from V1

| Aspect | V1 (Original) | V2 (Celery) |
|--------|--------------|-------------|
| Sync execution | In API request | In background worker |
| Response | Waits for completion | Returns immediately |
| Scalability | Single-threaded | Multiple workers possible |
| Job tracking | Database only | Database + Celery result backend |

## Backward Compatibility

- Original `/sync/codeforces` endpoint still works as-is
- V2 endpoints are at `/v2/sync/*` prefix
- No breaking changes to existing functionality
