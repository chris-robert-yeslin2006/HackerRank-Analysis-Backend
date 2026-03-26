# HackerRank Analysis Backend - Architecture & Documentation

## Overview

A FastAPI-based backend service for tracking and analyzing competitive programming progress across multiple platforms (HackerRank, LeetCode, Codeforces, CodeChef) for student cohorts.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Framework** | FastAPI |
| **Database** | PostgreSQL (Supabase) |
| **Caching** | Multi-level (Memory + Redis) + Automatic Selection |
| **Background Jobs** | Celery + Redis (Broker) |
| **External APIs** | LeetCode GraphQL, Codeforces REST, CodeChef REST, HackerRank |
| **AI Integration** | Google Gemini API (for natural language SQL queries) |
| **Async HTTP** | httpx |
| **Logging** | Structured JSON logging (Python logging) |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Client                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application                             │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                   RequestLoggingMiddleware                            ││
│  │  (JSON logs: method, path, status_code, duration_ms)                ││
│  └─────────────────────────────────────────────────────────────────────┘│
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Auth      │  │  Students   │  │ Leaderboard │  │  Analytics  │   │
│  │  Router     │  │  Router     │  │  Router     │  │  Router     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Platforms  │  │    Sync     │  │    Chat     │  │  Sync V2    │   │
│  │  Router     │  │  Router     │  │  Router     │  │  Router     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Multi-Level    │       │   Supabase      │       │   External      │
│     Cache       │       │   PostgreSQL     │       │    APIs         │
│ ┌─────────────┐ │       └─────────────────┘       └─────────────────┘
│ │ L1: Memory  │ │
│ │ L2: Redis   │ │
│ └─────────────┘ │
└─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Celery Worker                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │
│  │ sync_*      │  │  Job Track  │  │   Lock      │                     │
│  │   Tasks     │  │   Service   │  │  Manager    │                     │
│  └─────────────┘  └─────────────┘  └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Redis                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │
│  │  Broker    │  │   Result    │  │    Lock     │                     │
│  │   Queue    │  │   Backend   │  │   Store     │                     │
│  └─────────────┘  └─────────────┘  └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Level Caching System

### Cache Layers

| Layer | Technology | Latency | TTL | Purpose |
|-------|------------|---------|-----|---------|
| **L1** | In-memory dict (thread-safe) | ~0.02ms | 30-60s | Ultra-fast, process-local |
| **L2** | Redis (Upstash or Railway) | ~5ms | 60s | Shared across instances |
| **L3** | PostgreSQL | ~50ms | - | Source of truth |

### Cache Flow

```
Request
   │
   ▼
┌─────────────────────────────────────┐
│           L1: Memory Cache          │
│  • Thread-safe dict                 │
│  • Per-key TTL                      │
│  • Stale-while-revalidate (30s)     │
└─────────────────────────────────────┘
   │ hit
   ▼ return (0.02ms)
   
Request (L1 miss)
   │
   ▼
┌─────────────────────────────────────┐
│           L2: Redis Cache            │
│  • Auto-selects fastest provider    │
│  • Gzip compression >100KB         │
│  • JSON serialization               │
└─────────────────────────────────────┘
   │ hit
   ▼ populate L1 + return (~5ms)
   
Request (L2 miss)
   │
   ▼
┌─────────────────────────────────────┐
│           L3: PostgreSQL             │
│  • Original data source             │
│  • Paginated RPC calls              │
└─────────────────────────────────────┘
   │ miss
   ▼ populate L1 + L2 + return
```

### Cache Service API

```python
from database import CacheService

cache = CacheService(namespace="analytics", default_ttl=60)

# Get with auto-fetch on miss
result = cache.get(cache_key, fetch_func=lambda: db_query())

# Delete specific key
cache.delete(cache_key)

# Invalidate namespace
cache.invalidate()
```

### Cache Stampede Protection

Prevents multiple concurrent requests from hitting the database when cache expires.

| Feature | Implementation |
|---------|---------------|
| **Request Coalescing** | Per-key `threading.Lock` - only 1 thread fetches |
| **Stale-While-Revalidate** | Serves expired data (<30s) while refreshing in background |
| **Background Refresh** | Daemon thread refreshes without blocking |
| **Waiters** | `_results` dict shares result with waiting threads |

### Redis Provider Selection

Automatically benchmarks and selects the fastest Redis provider:

```python
# On startup, benchmarks both providers:
# - UPSTASH_REDIS (Upstash)
# - RAILWAY_REDIS_URL (Railway)

# Benchmark results logged:
{"event": "redis_benchmark", "provider": "railway", "avg_get_ms": 5.2}
{"event": "redis_selected", "provider": "railway", "avg_get_ms": 5.2}
```

### Payload Optimization

| Data Size | Action |
|-----------|--------|
| < 100KB | Store as JSON string |
| > 100KB | Gzip compress + store as hex |

Typical compression: **43x reduction** for large datasets.

---

## Structured Logging System

### Log Format

All logs are JSON-structured with consistent fields:

```json
{
  "timestamp": "2026-03-26T10:30:00.123456+00:00",
  "level": "INFO",
  "logger": "worker.tasks",
  "message": "Sync completed",
  "event": "sync_completed",
  "job_id": "abc123",
  "platform": "codeforces",
  "total": 1000,
  "success_count": 980,
  "failed_count": 20,
  "duration_ms": 125.45
}
```

### Key Events

| Event | Description |
|-------|-------------|
| `sync_started` | Sync task began processing |
| `sync_completed` | Sync task finished successfully |
| `sync_failed` | Sync task encountered error |
| `retry_triggered` | Retry initiated for failed students |
| `lock_acquired` | Redis lock obtained |
| `lock_rejected` | Lock denied (already held) |
| `lock_released` | Lock released |
| `cache_hit` | Cache data found (with source: memory/redis) |
| `cache_miss` | Cache data not found |
| `cache_set` | Data stored in cache |
| `cache_stale_served` | Expired data served while refreshing |
| `cache_refreshed` | Background refresh completed |
| `cache_lock_acquired` | DB fetch lock obtained |
| `cache_waiting` | Request waiting for other thread |
| `http_request` | API request completed |

### Suppressed Logs

External library logs are silenced to reduce noise:

- `uvicorn.access` → WARNING
- `httpx` → WARNING
- `httpcore` → WARNING
- `urllib3` → WARNING

---

## Database Schema

### Tables

#### 1. `students` - Core Student Information
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY |
| roll_no | TEXT | UNIQUE, NOT NULL |
| name | TEXT | NOT NULL |
| department | TEXT | NOT NULL |
| section | TEXT | NOT NULL |
| year | INT | NOT NULL |
| hackerrank_username | TEXT | UNIQUE |
| created_at | TIMESTAMP | DEFAULT NOW() |

#### 2. `student_platforms` - Platform Handles Mapping
| Column | Type | Constraints |
|--------|------|-------------|
| roll_no | TEXT | PRIMARY KEY, FK → students |
| leetcode_id | TEXT | - |
| codeforces_id | TEXT | - |
| codechef_id | TEXT | - |
| created_at | TIMESTAMP | DEFAULT NOW() |

#### 3. `leaderboard` - HackerRank Contest Results
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY |
| contest_name | TEXT | NOT NULL |
| contest_date | DATE | - |
| username | TEXT | NOT NULL |
| score | INT | - |
| time_taken | INT | - |
| created_at | TIMESTAMP | DEFAULT NOW() |

#### 4. `leetcode_stats` - LeetCode Statistics
| Column | Type | Constraints |
|--------|------|-------------|
| roll_no | TEXT | PRIMARY KEY, FK → students |
| weekly_rank | INT | - |
| weekly_problems_solved | INT | - |
| biweekly_rank | INT | - |
| biweekly_problems_solved | INT | - |
| contest_rating | INT | - |
| total_problems_solved | INT | - |
| easy_solved | INT | DEFAULT 0 |
| medium_solved | INT | DEFAULT 0 |
| hard_solved | INT | DEFAULT 0 |
| easy_today | INT | DEFAULT 0 |
| medium_today | INT | DEFAULT 0 |
| hard_today | INT | DEFAULT 0 |
| updated_at | TIMESTAMP | DEFAULT NOW() |

#### 5. `codeforces_stats` - Codeforces Statistics
| Column | Type | Constraints |
|--------|------|-------------|
| roll_no | TEXT | PRIMARY KEY, FK → students |
| current_rating | INT | - |
| max_rating | INT | - |
| rank | TEXT | - |
| contribution | INT | DEFAULT 0 |
| problems_solved | INT | DEFAULT 0 |
| easy_solved | INT | DEFAULT 0 |
| medium_solved | INT | DEFAULT 0 |
| hard_solved | INT | DEFAULT 0 |
| total_contests | INT | DEFAULT 0 |
| contest_name | TEXT | - |
| rating_changes | JSONB | DEFAULT [] |
| updated_at | TIMESTAMP | DEFAULT NOW() |

#### 6. `codechef_stats` - CodeChef Statistics
| Column | Type | Constraints |
|--------|------|-------------|
| roll_no | TEXT | PRIMARY KEY, FK → students |
| current_rating | INT | - |
| max_rating | INT | - |
| stars | INT | DEFAULT 0 |
| global_rank | INT | - |
| country_rank | INT | - |
| total_contests | INT | DEFAULT 0 |
| problems_solved | INT | DEFAULT 0 |
| contest_name | TEXT | - |
| contest_rank | INT | - |
| rating_changes | JSONB | DEFAULT [] |
| updated_at | TIMESTAMP | DEFAULT NOW() |

#### 7. `sync_jobs` - Sync Job Tracking (V2)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY |
| platform | TEXT | NOT NULL |
| status | TEXT | pending/running/success/failed |
| total_students | INT | DEFAULT 0 |
| processed_students | INT | DEFAULT 0 |
| success_count | INT | DEFAULT 0 |
| failed_count | INT | DEFAULT 0 |
| failed_students | JSONB | DEFAULT [] |
| error_message | JSONB | - |
| triggered_by | TEXT | api/cron/admin |
| started_at | TIMESTAMP | - |
| completed_at | TIMESTAMP | - |
| created_at | TIMESTAMP | DEFAULT NOW() |

---

## API Endpoints

### Base URL
```
http://localhost:8000
```

### Health & Status

#### GET `/health`
```json
{"status": "ok", "supabase_connected": true}
```

#### GET `/cache/stats`
```json
{
  "memory": {"total": 5, "expired": 1},
  "redis_providers": ["upstash", "railway"],
  "selected_redis": "railway",
  "redis_stats": {"railway": {"avg_get_ms": 5.2, "avg_set_ms": 3.1}}
}
```

### Authentication

#### POST `/login`
Admin login for cookie-based authentication.

### Students

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/students` | Get all students (cached) |
| GET | `/students/roll/{roll_no}` | Get student by roll number |
| POST | `/students` | Add new student |
| PATCH | `/students/{roll_no}` | Update student |
| POST | `/students/bulk` | Bulk upload from CSV |
| DELETE | `/students/{student_id}` | Delete student |

### Leaderboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/leaderboard` | Get leaderboard entries |
| POST | `/leaderboard` | Add single entry |
| POST | `/leaderboard/bulk` | Bulk upload entries |

### Platforms

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/platforms` | Get all platform mappings (cached) |
| POST | `/platforms` | Add platform entry |
| PATCH | `/platforms/{roll_no}` | Update platform IDs |
| POST | `/platforms/bulk` | Bulk upload |
| POST | `/platforms/csv` | Upload from CSV |

### Analytics (V1 - Synchronous)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/department` | Department leaderboard (cached) |
| GET | `/analytics/platform-department` | Platform-specific dept leaderboard |
| GET | `/analytics/section` | Section leaderboard (cached) |
| GET | `/analytics/top-students` | Top students (cached) |
| GET | `/analytics/absent/{contest_name}` | Absent students |
| GET | `/analytics/codeforces` | Codeforces analytics (cached) |
| GET | `/analytics/codeforces/absent/*` | Codeforces absent tracking |
| GET | `/analytics/codechef` | CodeChef analytics (cached) |
| GET | `/analytics/codechef/absent/*` | CodeChef absent tracking |
| GET | `/analytics/leetcode` | LeetCode analytics (cached) |
| GET | `/analytics/frontend-data` | Aggregated frontend data (cached) |

### Sync V1 (Synchronous)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sync/all` | Sync all platforms |
| POST | `/sync/hackerrank` | Sync HackerRank |
| POST | `/sync/leetcode` | Sync LeetCode |
| POST | `/sync/codeforces` | Sync Codeforces |
| POST | `/sync/codechef` | Sync CodeChef |
| GET | `/sync/jobs` | Get sync job history |

### Sync V2 (Asynchronous with Celery)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v2/sync/codeforces` | Trigger Codeforces sync |
| GET | `/v2/sync/status/{task_id}` | Get task status |
| GET | `/v2/sync/jobs` | List jobs (filters: limit, status, platform) |
| GET | `/v2/sync/jobs/{id}` | Get job details |
| GET | `/v2/sync/jobs/stuck/list` | Get stuck jobs (>15 min) |
| GET | `/v2/sync/consistency-check` | Check lock/DB consistency |
| POST | `/v2/sync/codeforces/retry/{job_id}` | Retry failed students |

### Chat (AI Assistant)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/sql` | Natural language to SQL |
| GET | `/chat/models` | List available models |

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_KEY` | Supabase anon/public key | Yes |
| `UPSTASH_URL` | Upstash Redis URL | No |
| `UPSTASH_TOKEN` | Upstash Redis token | No |
| `RAILWAY_REDIS_URL` | Railway Redis URL | No |
| `REDIS_URL` | Generic Redis URL (fallback) | No |
| `CELERY_BROKER_URL` | Celery broker (Redis) | For V2 |
| `CELERY_RESULT_BACKEND` | Celery result backend | For V2 |
| `GOOGLE_API_KEY` | Gemini API key | For chat |
| `CRON_BASE_URL` | Base URL for cron sync | For cron jobs |

---

## Running the Application

### Development

```bash
# FastAPI server with structured logging
uvicorn main:app --reload --log-level info

# Celery worker (for V2 sync)
celery -A worker.celery_app worker --loglevel=info -Q sync --pool=solo
```

### Production

```bash
# With gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker

# With logging to file
uvicorn main:app --log-level info 2>&1 | tee logs/app.log
```

---

## File Structure

```
├── main.py                    # FastAPI app entry point
├── database.py                # Supabase + Redis + CacheService
├── schemas.py                 # Pydantic models
├── cron_sync.py               # Cron job for syncing
├── requirements.txt
├── docker-compose.yml
│
├── routers/                   # API route handlers
│   ├── auth.py
│   ├── students.py            # Uses CacheService
│   ├── leaderboard.py         # Uses CacheService
│   ├── analytics.py           # Uses CacheService
│   ├── sync.py                # V1 sync endpoints
│   ├── sync_v2.py             # V2 Celery endpoints
│   ├── platforms.py           # Uses CacheService
│   └── chat.py
│
├── services/
│   └── job_service.py         # Job tracking service
│
├── worker/
│   ├── celery_app.py          # Celery configuration
│   └── tasks.py               # Background sync tasks
│
├── utils/
│   ├── logger.py              # Structured logging + helpers
│   └── lock.py                # Redis locking utilities
│
├── middleware/
│   ├── __init__.py
│   └── logging.py             # Request logging middleware
│
└── migrations/
    └── 002_enhance_sync_jobs.sql
```

---

## Dependencies

```
fastapi>=0.100.0
uvicorn>=0.23.0
supabase>=2.0.0
httpx>=0.25.0
pydantic>=2.0.0
redis>=5.0.0
celery>=5.3.0
python-multipart>=0.0.6
python-dotenv>=1.0.0
gunicorn>=21.0.0
```
