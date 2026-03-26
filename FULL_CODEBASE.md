# HackerRank Analysis Backend - Complete Codebase Reference

This document provides comprehensive information about the codebase for AI-assisted development.

---

## Project Overview

**Project Name:** HackerRank Analysis Backend  
**Type:** FastAPI-based REST API Backend  
**Purpose:** Track and analyze competitive programming progress across multiple platforms (HackerRank, LeetCode, Codeforces, CodeChef) for student cohorts  
**Target Users:** Educational institutions tracking student programming progress

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | FastAPI |
| Database | PostgreSQL (Supabase) |
| Caching | Multi-level (Memory + Redis) + Automatic Selection |
| Background Jobs | Celery + Redis (Broker) |
| External APIs | LeetCode GraphQL, Codeforces REST, CodeChef REST, HackerRank |
| AI Integration | Google Gemini API (for natural language SQL queries) |
| Async HTTP | httpx |
| Logging | Structured JSON logging (Python logging) |

---

## File Structure

```
├── main.py                    # FastAPI app entry point
├── database.py                # Supabase + Redis + CacheService (576 lines)
├── schemas.py                 # Pydantic models
├── cron_sync.py               # Cron job for syncing
├── requirements.txt
├── docker-compose.yml
│
├── routers/                   # API route handlers
│   ├── auth.py               # Authentication
│   ├── students.py           # Student management (uses CacheService)
│   ├── leaderboard.py        # Leaderboard (uses CacheService)
│   ├── analytics.py          # Analytics (uses CacheService)
│   ├── sync.py               # V1 sync endpoints (synchronous)
│   ├── sync_v2.py            # V2 Celery endpoints (asynchronous)
│   ├── platforms.py          # Platform mappings (uses CacheService)
│   └── chat.py               # AI Chat (Gemini)
│
├── services/
│   └── job_service.py        # Job tracking service (333 lines)
│
├── worker/
│   ├── celery_app.py         # Celery configuration
│   ├── tasks.py              # Background sync tasks (305 lines)
│   └── __init__.py
│
├── utils/
│   ├── logger.py             # Structured logging + helpers (291 lines)
│   ├── lock.py               # Redis locking utilities (46 lines)
│   └── __init__.py
│
├── middleware/
│   ├── __init__.py
│   └── logging.py            # Request logging middleware
│
└── migrations/
    ├── 002_enhance_sync_jobs.sql
    └── 003_add_failed_students.sql
```

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

#### 7. `sync_jobs` - Sync Job Tracking
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
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/cache/stats` | Cache performance stats |

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/login` | Admin login (cookie-based) |

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

## Key Components

### 1. Multi-Level Caching System (`database.py`)

**CacheService class** provides:
- L1: In-memory dict (thread-safe) - ~0.02ms latency, 30-60s TTL
- L2: Redis (auto-selects fastest provider) - ~5ms latency, 60s TTL
- L3: PostgreSQL - ~50ms latency
- Cache stampede protection with request coalescing
- Stale-while-revalidate pattern
- Gzip compression for payloads >100KB

**Usage:**
```python
from database import CacheService

cache = CacheService(namespace="analytics", default_ttl=60)
result = cache.get(cache_key, fetch_func=lambda: db_query())
```

### 2. Redis Locking (`utils/lock.py`)

- Prevents duplicate sync jobs using `SET NX EX` pattern
- Lock auto-expires after 10 minutes (600s)
- Always released in `finally` block

**Functions:**
```python
acquire_lock(platform: str) -> bool
release_lock(platform: str) -> None
is_locked(platform: str) -> bool
refresh_lock(platform: str) -> bool
```

### 3. Job Service (`services/job_service.py`)

Functions for managing sync jobs:
- `create_job()` - Create new job record
- `start_job()` - Mark job as running
- `update_job_progress()` - Update counts and progress
- `complete_job()` - Mark job as success
- `fail_job()` - Mark job as failed with error
- `get_jobs()` - Fetch jobs with filters
- `get_stuck_jobs()` - Find jobs running >15 min
- `check_lock_db_consistency()` - Detect orphan locks

### 4. Celery Tasks (`worker/tasks.py`)

Background sync tasks:
- `sync_codeforces_task` - Main Codeforces sync task
- Processes students in batches of 50
- Uses semaphore limit of 25 concurrent requests
- Retry with exponential backoff for network errors

### 5. Structured Logging (`utils/logger.py`)

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

Key events: `sync_started`, `sync_completed`, `sync_failed`, `retry_triggered`, `lock_acquired`, `lock_rejected`, `lock_released`, `cache_hit`, `cache_miss`, `cache_set`, `cache_stale_served`, `cache_refreshed`, `http_request`

### 6. Pydantic Schemas (`schemas.py`)

Models:
- `StudentBase`, `StudentCreate`, `Student`, `StudentUpdate`, `StudentFullUpdate`
- `LeaderboardEntryCreate`
- `LoginRequest`
- `StudentPlatform`, `StudentPlatformUpdate`
- `LeetCodeStats`
- `CodeforcesStats`
- `CodeChefStats`

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
```

---

## Dependencies

```
fastapi>=0.104.1
uvicorn[standard]>=0.23.2
supabase>=2.3.0
python-dotenv>=1.0.0
python-multipart>=0.0.9
httpx>=0.25.0
redis>=5.0.0
google-generativeai>=0.3.2
celery>=5.3.0
```

---

## Key Patterns for Development

### Adding a new endpoint:
1. Add Pydantic model to `schemas.py`
2. Create route in appropriate `routers/*.py`
3. Use `CacheService` for cached endpoints
4. Add structured logging

### Adding a new sync task:
1. Create Celery task in `worker/tasks.py`
2. Use `create_job()`, `start_job()`, `update_job_progress()`, `complete_job()` for tracking
3. Use locking in `utils/lock.py`
4. Add structured logging with events

### Cache usage:
```python
cache = CacheService(namespace="custom", default_ttl=60)
result = cache.get("key", fetch_func=lambda: db_query())
cache.set("key", value)
cache.delete("key")
cache.invalidate("pattern")
```

### Database operations:
```python
from database import supabase

# Query
response = supabase.table("table_name").select("*").execute()

# Insert
response = supabase.table("table_name").insert(data).execute()

# Update
response = supabase.table("table_name").update(data).eq("id", id).execute()

# Delete
response = supabase.table("table_name").delete().eq("id", id).execute()

# RPC call
response = supabase.rpc("function_name", params).execute()
```
