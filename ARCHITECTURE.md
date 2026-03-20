# HackerRank Analysis Backend - Architecture & Documentation

## Overview

A FastAPI-based backend service for tracking and analyzing competitive programming progress across multiple platforms (HackerRank, LeetCode, Codeforces, CodeChef) for student cohorts.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Framework** | FastAPI |
| **Database** | PostgreSQL (Supabase) |
| **Caching** | Redis + In-Memory Fallback |
| **External APIs** | LeetCode GraphQL, Codeforces REST, CodeChef REST, HackerRank |
| **AI Integration** | Google Gemini API (for natural language SQL queries) |
| **Async HTTP** | httpx |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Client                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Auth      │  │  Students   │  │ Leaderboard │  │  Analytics  │   │
│  │  Router     │  │  Router     │  │  Router     │  │  Router     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Platforms  │  │    Sync     │  │    Chat     │  │             │   │
│  │  Router     │  │  Router     │  │  Router     │  │             │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │  Supabase   │ │   Redis     │ │  External   │
            │ PostgreSQL  │ │   Cache     │ │    APIs     │
            └─────────────┘ └─────────────┘ └─────────────┘
```

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

---

## API Endpoints

### Base URL
```
http://localhost:8000
```

### Authentication

#### POST `/login`
Admin login for cookie-based authentication.

**Request Body:**
```json
{
  "username": "admin",
  "password": "Admin@123"
}
```

**Response:**
```json
{
  "message": "Login successful",
  "authenticated": true
}
```

---

### Students

#### GET `/students`
Get all students.

**Response:** Array of student objects

---

#### GET `/students/roll/{roll_no}`
Get student by roll number.

**Parameters:**
- `roll_no` (path) - Student's roll number

**Response:**
```json
{
  "id": "uuid",
  "roll_no": "22CS001",
  "name": "John Doe",
  "department": "CSE",
  "section": "A",
  "year": 2022,
  "hackerrank_username": "john123"
}
```

---

#### POST `/students`
Add a new student.

**Request Body:**
```json
{
  "roll_no": "22CS001",
  "name": "John Doe",
  "department": "CSE",
  "section": "A",
  "year": 2022,
  "hackerrank_username": "john123"
}
```

---

#### PATCH `/students/{roll_no}`
Update student (partial update - only provided fields are updated).

**Parameters:**
- `roll_no` (path) - Student's roll number

**Request Body (all fields optional):**
```json
{
  "name": "Jane Doe",
  "department": "IT",
  "section": "B",
  "year": 2022,
  "hackerrank_username": "jane123",
  "leetcode_id": "jane_leetcode",
  "codeforces_id": "jane_cf",
  "codechef_id": "jane_cc"
}
```

---

#### POST `/students/bulk`
Bulk upload students from CSV file.

**Form Data:**
- `file` - CSV file with columns: `roll_no`, `name`, `department`, `section`, `year`, `hackerrank_username`

---

#### DELETE `/students/{student_id}`
Delete student by UUID.

---

### Leaderboard

#### POST `/leaderboard`
Add a single leaderboard entry.

**Request Body:**
```json
{
  "contest_name": "Weekly Contest 123",
  "contest_date": "2024-01-15",
  "username": "john123",
  "score": 450,
  "time_taken": 120
}
```

---

#### POST `/leaderboard/bulk`
Bulk upload leaderboard entries.

**Request Body:**
```json
[
  {
    "contest_name": "Weekly Contest 123",
    "username": "john123",
    "score": 450
  },
  {
    "contest_name": "Weekly Contest 123",
    "username": "jane123",
    "score": 420
  }
]
```

---

### Platforms

#### GET `/platforms`
Get all student platform mappings.

---

#### POST `/platforms`
Add platform IDs for a student.

**Request Body:**
```json
{
  "roll_no": "22CS001",
  "leetcode_id": "john_leet",
  "codeforces_id": "john_cf",
  "codechef_id": "john_cc"
}
```

---

#### PATCH `/platforms/{roll_no}`
Update platform IDs for a student (partial update).

**Request Body:**
```json
{
  "leetcode_id": "new_handle",
  "codeforces_id": "new_cf"
}
```

---

#### POST `/platforms/bulk`
Bulk upload platform IDs.

**Request Body:**
```json
[
  {
    "roll_no": "22CS001",
    "leetcode_id": "john_leet",
    "codeforces_id": "john_cf"
  }
]
```

---

#### POST `/platforms/csv`
Upload platform IDs from CSV file.

**Form Data:**
- `file` - CSV with columns: `roll_no`, `leetcode_id`, `codeforces_id`, `codechef_id`

---

### Analytics

#### GET `/analytics/department`
Department-wise leaderboard.

**Query Parameters:**
- `platform` (optional) - `hackerrank`, `leetcode`, `codeforces`, `codechef` (default: `hackerrank`)

**Response:**
```json
[
  {"department": "CSE", "total_score": 15000},
  {"department": "IT", "total_score": 12000}
]
```

---

#### GET `/analytics/platform-department`
Get department leaderboard for specific platform.

**Query Parameters:**
- `platform` - `codeforces`, `codechef`

---

#### GET `/analytics/section`
Section-wise leaderboard.

**Query Parameters:**
- `platform` (optional) - `hackerrank` (default)

---

#### GET `/analytics/top-students`
Get top performing students.

**Query Parameters:**
- `platform` (optional) - `hackerrank` (default)
- `limit` (optional) - Number of students (default: 10)

---

#### GET `/analytics/absent/{contest_name}`
Students who didn't participate in a specific contest.

**Parameters:**
- `contest_name` (path) - Name of the contest

---

#### GET `/analytics/codeforces`
Get Codeforces analytics for all students.

---

#### GET `/analytics/codeforces/absent/{contest_name}`
Codeforces students absent from specific contest.

---

#### GET `/analytics/codeforces/absent`
All Codeforces users with no stats.

---

#### GET `/analytics/codechef`
Get CodeChef analytics for all students.

---

#### GET `/analytics/codechef/absent/{contest_name}`
CodeChef students absent from specific contest.

---

#### GET `/analytics/codechef/absent`
All CodeChef users with no stats.

---

### Sync (Data Fetching)

#### POST `/sync/all`
Sync all platforms in parallel.

---

#### POST `/sync/hackerrank`
Sync HackerRank leaderboard data.

---

#### POST `/sync/leetcode`
Sync LeetCode statistics for all students.

**What it syncs:**
- Contest ranking (weekly & biweekly)
- Total problems solved (easy/medium/hard)
- Today's solved count (easy/medium/hard)

---

#### POST `/sync/codeforces`
Sync Codeforces statistics for all students.

**What it syncs:**
- Current & max rating
- Rank
- Contribution points
- Problems solved by difficulty
- Recent contest participation (last 5 finished contests)

---

#### POST `/sync/codechef`
Sync CodeChef statistics for all students.

**What it syncs:**
- Current & max rating
- Stars
- Global & country rank
- Total contests & problems solved

---

### Chat (AI Assistant)

#### POST `/chat/sql`
Natural language to SQL query using Gemini AI.

**Request Body:**
```json
{
  "text": "Show me top 5 students from CSE department"
}
```

**Response:**
```json
{
  "query": "SELECT ...",
  "data": [...],
  "message": "Success"
}
```

---

#### GET `/chat/models`
List available Gemini models.

---

## Data Flow

### Sync Flow
```
1. Fetch students with platform IDs from database
2. Create batches (50 students per batch)
3. For each student:
   a. Call external API (LeetCode/Codeforces/CodeChef)
   b. Parse response
   c. Calculate deltas (e.g., today's problems)
   d. Upsert to stats table
4. Clear relevant caches
```

### Cache Strategy
```
1. Check Redis first
2. If miss, check in-memory cache
3. If miss, query database
4. Store result in both Redis (60s TTL) and memory (30s TTL)
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/public key |
| `REDIS_URL` | Redis connection URL (optional) |
| `GOOGLE_API_KEY` | Gemini API key for chat |

---

## Running the Application

### Development
```bash
# Activate virtual environment
source venv/bin/activate

# Run with auto-reload
uvicorn main:app --reload

# Run on specific port
uvicorn main:app --reload --port 8000
```

### Production
```bash
# Run with gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## Error Handling

All endpoints return consistent error format:
```json
{
  "detail": "Error message description"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource doesn't exist |
| 401 | Unauthorized - Invalid credentials |
| 500 | Internal Server Error |

---

## Rate Limiting & Retry Strategy

The sync service implements:
- **Exponential backoff** for failed API calls (1s, 2s, 4s delays)
- **Semaphore-based concurrency** limiting (25 parallel requests)
- **Batch processing** (50 students per batch)
- **Sleep between batches** (1 second)

---

## Dependencies

```
fastapi>=0.100.0
uvicorn>=0.23.0
supabase>=2.0.0
httpx>=0.25.0
pydantic>=2.0.0
redis>=5.0.0
python-multipart>=0.0.6
```
