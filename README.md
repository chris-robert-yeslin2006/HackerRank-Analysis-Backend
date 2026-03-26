# <h1 align="center">🏆 HackerRank Analysis Backend</h1>

<p align="center">
  <em>Comprehensive competitive programming analytics platform for tracking student progress across HackerRank, LeetCode, Codeforces, and CodeChef</em>
</p>

<p align="center">
  <a href="https://github.com" target="_blank">
    <img src="https://img.shields.io/badge/Status-Active-success?style=for-the-badge" />
  </a>
  <img src="https://img.shields.io/badge/Database-Supabase-3ECF8E?style=for-the-badge&logo=supabase" />
  <img src="https://img.shields.io/badge/Cache-Redis-00E5FF?style=for-the-badge&logo=redis" />
  <img src="https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/Background-Celery-B0C4DE?style=for-the-badge&logo=celery" />
</p>

---

## 🎯 Problem Statement

Educational institutions need to track and analyze student competitive programming progress across multiple platforms (HackerRank, LeetCode, Codeforces, CodeChef). Currently, this data exists in silos with no unified analytics or leaderboard system.

**Solution**: A FastAPI-based backend that aggregates platform data, provides real-time analytics, department/section leaderboards, and AI-powered insights.

---

## ✨ Key Features

- 📊 **Multi-Platform Analytics**: Unified dashboard for HackerRank, LeetCode, Codeforces, CodeChef
- 🏅 **Department & Section Leaderboards**: Track competition progress by groups
- ⚡ **High Performance**: Multi-level caching with sub-100ms response times
- 🔄 **Background Sync**: Celery-based async platform data synchronization
- 🛡️ **Redis Locking**: Prevent duplicate sync jobs with distributed locks
- 🤖 **AI Assistant**: Natural language SQL queries using Google Gemini
- 📈 **Production Monitoring**: Health checks, cache stats, stuck job detection
- 🔄 **Scalable Architecture**: Microservice-ready with async processing

---

## 🏗️ Architecture

<p align="center">
  <img src="https://github.com/yeslin-parker/HackerRank-Analysis-Backend/blob/main/images/system-architecture.png" alt="System Architecture" width="90%">
</p>

### Multi-Level Caching Flow

<p align="center">
  <img src="https://github.com/yeslin-parker/HackerRank-Analysis-Backend/blob/main/images/cache.png" alt="Cache Architecture" width="80%">
</p>

### Sync Queue (Celery)

<p align="center">
  <img src="https://github.com/yeslin-parker/HackerRank-Analysis-Backend/blob/main/images/sync-queue.png" alt="Sync Queue Architecture" width="80%">
</p>

### Performance Improvements

<p align="center">
  <img src="https://github.com/yeslin-parker/HackerRank-Analysis-Backend/blob/main/images/performance-improvements.png" alt="Performance Improvements" width="80%">
</p>

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **API Framework** | FastAPI | High-performance async REST API |
| **Database** | Supabase PostgreSQL | Persistent storage with RLS security |
| **Cache L1** | In-Memory (dict) | Ultra-fast, process-local caching (~0.02ms) |
| **Cache L2** | Upstash/Railway Redis | Shared cross-instance caching (~5ms) |
| **Background Jobs** | Celery + Redis | Async platform synchronization |
| **AI Integration** | Google Gemini | Natural language SQL queries |
| **Authentication** | JWT/Cookies | Secure admin access |
| **Deployment** | Docker + Uvicorn | Production container orchestration |

---

## 📊 Performance Metrics

| Metric | Value |
|--------|-------|
| **L1 Cache (Memory)** | ~0.02ms latency |
| **L2 Cache (Redis)** | ~5ms latency |
| **Database Query** | ~50ms latency |
| **Cache Hit Rate** | 85%+ for frequent queries |
| **Payload Compression** | 43x reduction for large datasets |
| **Sync Batch Size** | 50 students per batch |

---

## 🔧 API Endpoints

### Health & Status
```http
GET /health
GET /cache/stats
```

### Students
```http
GET /students
GET /students/roll/{roll_no}
POST /students
PATCH /students/{roll_no}
POST /students/bulk
DELETE /students/{student_id}
```

### Leaderboard
```http
GET /leaderboard
POST /leaderboard
POST /leaderboard/bulk
```

### Platforms
```http
GET /platforms
POST /platforms
PATCH /platforms/{roll_no}
POST /platforms/bulk
```

### Analytics
```http
GET /analytics/department
GET /analytics/platform-department
GET /analytics/section
GET /analytics/top-students
GET /analytics/codeforces
GET /analytics/codechef
GET /analytics/leetcode
GET /analytics/frontend-data
```

### Sync V1 (Synchronous)
```http
POST /sync/all
POST /sync/hackerrank
POST /sync/codeforces
POST /sync/codechef
GET /sync/jobs
```

### Sync V2 (Asynchronous)
```http
POST /v2/sync/codeforces
GET /v2/sync/status/{task_id}
GET /v2/sync/jobs
GET /v2/sync/jobs/{id}
GET /v2/sync/jobs/stuck/list
GET /v2/sync/consistency-check
POST /v2/sync/codeforces/retry/{job_id}
```

### AI Chat
```http
POST /chat/sql
GET /chat/models
```

---

## 🚀 Quick Start

### Local Development
```bash
# Clone the repository
git clone https://github.com/yeslin-parker/HackerRank-Analysis-Backend.git
cd HackerRank-Analysis-Backend

# Create virtual environment
python3 -m venv venv

# Activate (fish)
source venv/bin/activate.fish

# Or activate (bash/zsh)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the API
uvicorn main:app --reload --log-level info
```

### Running with Celery Worker
```bash
# Terminal 1 - FastAPI
uvicorn main:app --reload --log-level info

# Terminal 2 - Celery Worker
celery -A worker.celery_app worker --loglevel=info -Q sync --pool=solo
```

### Using Docker
```bash
docker build -t hackerrank-backend .
docker run -p 8000:8000 hackerrank-backend
```

---

## 📁 Project Structure

```
HackerRank-Analysis-Backend/
├── main.py                    # FastAPI app entry point
├── database.py                # Supabase + Redis + CacheService
├── schemas.py                 # Pydantic models
├── cron_sync.py               # Cron job for syncing
├── requirements.txt
│
├── routers/                   # API route handlers
│   ├── auth.py               # Authentication
│   ├── students.py           # Student management
│   ├── leaderboard.py        # Leaderboard
│   ├── analytics.py          # Analytics (cached)
│   ├── sync.py               # V1 sync (synchronous)
│   ├── sync_v2.py            # V2 sync (Celery)
│   ├── platforms.py          # Platform mappings
│   └── chat.py               # AI Chat (Gemini)
│
├── services/
│   └── job_service.py        # Job tracking service
│
├── worker/
│   ├── celery_app.py         # Celery configuration
│   └── tasks.py              # Background sync tasks
│
├── utils/
│   ├── logger.py             # Structured JSON logging
│   └── lock.py               # Redis locking utilities
│
├── middleware/
│   └── logging.py            # Request logging middleware
│
├── migrations/
│   ├── 002_enhance_sync_jobs.sql
│   └── 003_add_failed_students.sql
│
└── images/
    ├── system-architecture.png
    ├── cache.png
    ├── sync-queue.png
    └── performance-improvements.png
```

---

## 🛡️ Security Features

- **Input Validation**: Comprehensive Pydantic models
- **Structured Logging**: Complete audit trail
- **Redis Locking**: Prevent duplicate operations
- **Rate Limiting**: Configurable per-endpoint
- **Environment Isolation**: Secure credential management
- **Cache Stampede Protection**: Request coalescing + stale-while-revalidate

---

## 📈 Monitoring & Observability

### Cache Statistics
```bash
curl http://localhost:8000/cache/stats
```

Response:
```json
{
  "memory": {"total": 5, "expired": 1},
  "redis_providers": ["upstash", "railway"],
  "selected_redis": "railway",
  "redis_stats": {"railway": {"avg_get_ms": 5.2, "avg_set_ms": 3.1}}
}
```

### Stuck Job Detection
```bash
curl http://localhost:8000/v2/sync/jobs/stuck/list
```

### Consistency Check
```bash
curl http://localhost:8000/v2/sync/consistency-check
```

---

## 🌍 Environment Configuration

```env
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Redis (auto-selects fastest)
UPSTASH_URL=https://xxx.upstash.io
UPSTASH_TOKEN=xxx
RAILWAY_REDIS_URL=redis://xxx.railway.app:xxx

# Celery
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379

# AI
GOOGLE_API_KEY=your-gemini-api-key

# Application
CRON_BASE_URL=http://localhost:8000
```

---

## 🧪 Testing

### API Testing
```bash
# Test health endpoint
curl http://localhost:8000/health

# Trigger Codeforces sync
curl -X POST http://localhost:8000/v2/sync/codeforces

# Get sync jobs
curl "http://localhost:8000/v2/sync/jobs?limit=10"
```

---

## 🔄 Sync Architecture

### V1 vs V2 Comparison

| Aspect | V1 | V2 |
|--------|----|----|
| Execution | In API request | Background worker |
| Response | Waits for completion | Returns immediately |
| Job Locking | None | Redis-based |
| Progress Tracking | processed_students | success/failed counts |
| Stuck Detection | None | Automatic |
| Caching | Redis only | Multi-level |

---

## 📊 Database Schema

### Tables

| Table | Description |
|-------|-------------|
| `students` | Core student information |
| `student_platforms` | Platform handle mappings |
| `leaderboard` | HackerRank contest results |
| `leetcode_stats` | LeetCode statistics |
| `codeforces_stats` | Codeforces statistics |
| `codechef_stats` | CodeChef statistics |
| `sync_jobs` | Sync job tracking |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests
4. Commit changes
5. Push to branch
6. Open a Pull Request

---

## 👨‍💻 Author

**Yeslin Parker**
- 📷 [Instagram](https://instagram.com/yeslin_parker) – @yeslin_parker

---

## 📜 License

This project is licensed under the MIT License.

---

<p align="center">
  <strong>🎓 Built for educational institutions to track and inspire competitive programming excellence 🌟</strong>
</p>
