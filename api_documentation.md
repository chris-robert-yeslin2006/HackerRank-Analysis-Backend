# HackerRank Analysis Backend API

This document provides a complete and updated summary of all available APIs for the frontend developer.

**Base URL**: `http://127.0.0.1:8000`

---

## Authentication Endpoints

### 1. Admin Login
Logs in the administrator and securely sets an authentication cookie.
- **Method**: `POST`
- **Endpoint**: `/login`
- **Body**:
  ```json
  {
    "username": "admin",
    "password": "Admin@123"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "message": "Login successful",
    "authenticated": true
  }
  ```
  (Sets `HttpOnly` cookie: `auth_token=true`)

---

## Data Ingestion Endpoints (Students)

### 2. Get All Students
Fetches all students from the database. Use this to retrieve the `id` (UUID) needed to edit or delete a specific student.
- **Method**: `GET`
- **Endpoint**: `/students`
- **Response**: `200 OK`
  ```json
  [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "roll_no": "23CS001",
      "name": "Jane Doe",
      "department": "CSE",
      "section": "A",
      "year": 1,
      "hackerrank_username": "jane_hr",
      "created_at": "2023-10-01T10:00:00Z"
    }
  ]
  ```

### 3. Add Single Student
Adds a single student to the database.
- **Method**: `POST`
- **Endpoint**: `/students`
- **Body**:
  ```json
  {
    "roll_no": "23CS001",
    "name": "Jane Doe",
    "department": "CSE",
    "section": "A",
    "year": 1,
    "hackerrank_username": "jane_hr"
  }
  ```
- **Response**:
  ```json
  {
    "message": "Student added successfully",
    "data": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "roll_no": "23CS001",
      "name": "Jane Doe",
      "department": "CSE",
      "section": "A",
      "year": 1,
      "hackerrank_username": "jane_hr"
    }
  }
  ```

### 4. Bulk Upload Students (CSV)
Uploads multiple students at once via a CSV file.
- **Method**: `POST`
- **Endpoint**: `/students/bulk`
- **Body**: `multipart/form-data`
  - `file`: The `.csv` file containing headers: `roll_no`, `name`, `department`, `section`, `year`, `hackerrank_username`.
- **Response**:
  ```json
  {
    "message": "Bulk upload successful",
    "inserted": 25,
    "data": [ ... ]
  }
  ```

### 5. Update Single Student
Edits an existing student's data. You only need to pass the fields you want to change.
- **Method**: `PATCH`
- **Endpoint**: `/students/{student_id}`
- **Body**: (Partial object)
  ```json
  {
    "department": "IT",
    "year": 2
  }
  ```
- **Response**:
  ```json
  {
    "message": "Student updated successfully",
    "data": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "roll_no": "23CS001",
      "name": "Jane Doe",
      "department": "IT",
      "section": "A",
      "year": 2,
      "hackerrank_username": "jane_hr"
    }
  }
  ```

### 6. Delete Single Student
Deletes a student by their ID. This only removes the student and does not delete their leaderboard contest records.
- **Method**: `DELETE`
- **Endpoint**: `/students/{student_id}`
- **Response**: `200 OK`
  ```json
  {
    "message": "Student deleted successfully"
  }
  ```

---

## Data Ingestion Endpoints (Leaderboard)

### 7. Add Single Leaderboard Entry
Adds a single scraped contest result.
- **Method**: `POST`
- **Endpoint**: `/leaderboard`
- **Body**:
  ```json
  {
    "contest_name": "week1_batch1",
    "contest_date": "2023-10-01",
    "username": "jane_hr",
    "score": 150,
    "time_taken": 45
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "message": "Leaderboard entry added successfully",
    "data": {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "contest_name": "week1_batch1",
      "contest_date": "2023-10-01",
      "username": "jane_hr",
      "score": 150,
      "time_taken": 45,
      "created_at": "2023-10-01T12:00:00Z"
    }
  }
  ```

### 8. Bulk Upload Leaderboard Entries
Uploads multiple scraped contest results at once.
- **Method**: `POST`
- **Endpoint**: `/leaderboard/bulk`
- **Body**: 
  ```json
  [
    {
      "contest_name": "week1_batch1",
      "contest_date": "2023-10-01",
      "username": "jane_hr",
      "score": 150,
      "time_taken": 45
    },
    {
      "contest_name": "week1_batch1",
      "contest_date": "2023-10-01",
      "username": "john_hr",
      "score": 140,
      "time_taken": 50
    }
  ]
  ```
- **Response**: `200 OK`
  ```json
  {
    "message": "Bulk upload successful",
    "inserted": 2,
    "data": [ ... ]
  }
  ```

---

## Analytics Endpoints

### 9. Frontend Raw Data
Returns deeply nested rank and leaderboard info tailored specifically for the frontend display table.
- **Method**: `GET`
- **Endpoint**: `/frontend-data`
- **Returns**: Array of `ContestData`
  ```json
  [
    {
      "year": "I",
      "dept": "CSE",
      "section": "A",
      "contests": {
        "week1_batch1": {
          "jane_hr": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Jane Doe",
            "user-id": "jane_hr",
            "score": 150,
            "time": "45",
            "rank": 1
          }
        }
      }
    }
  ]
  ```

### 10. Department Leaderboard
Aggregated total scores grouped by department for HackerRank.
- **Method**: `GET`
- **Endpoint**: `/analytics/department`
- **Response**: `200 OK`
  ```json
  [
    {
      "department": "CSE",
      "total_score": 15000
    },
    {
      "department": "IT",
      "total_score": 12000
    }
  ]
  ```

### 11. Section Leaderboard
Aggregated total scores grouped by section for HackerRank.
- **Method**: `GET`
- **Endpoint**: `/analytics/section`
- **Response**: `200 OK`
  ```json
  [
    {
      "section": "A",
      "total_score": 8000
    },
    {
      "section": "B",
      "total_score": 7000
    }
  ]
  ```

### 12. Top 10 Students
Returns the top 10 students across all contests sorted by total score.
- **Method**: `GET`
- **Endpoint**: `/analytics/top-students`
- **Response**: `200 OK`
  ```json
  [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Jane Doe",
      "total_score": 1500
    }
  ]
  ```

### 13. Absent Students for Contest
Returns all students who did NOT participate in a given `contest_name`.
- **Method**: `GET`
- **Endpoint**: `/analytics/absent-students/{contest_name}`
- **Returns**: Array of `AbsentStudent` objects
  ```json
  [
    {
      "id": "abc-123-uuid",
      "hackerrank_username": "john_hr",
      "name": "John Doe",
      "dept": "IT",
      "section": "B",
      "year": 2
    }
  ]
  ```

---

## Platform Management

### 14. Bulk Upload Platform IDs (JSON)
Store multiple student platform IDs via JSON array.
- **Method**: `POST`
- **Endpoint**: `/platforms/bulk`
- **Body**: 
  ```json
  [
    {
      "roll_no": "21CS001",
      "leetcode_id": "arjun_lc",
      "codeforces_id": "arjun_cf",
      "codechef_id": "arjun_cc"
    }
  ]
  ```
- **Response**: `200 OK`
  ```json
  {
    "message": "Platform IDs stored successfully",
    "count": 1,
    "data": [ ... ]
  }
  ```

### 15. Bulk Upload Platform IDs (CSV)
Store student platform IDs via CSV file.
- **Method**: `POST`
- **Endpoint**: `/platforms/csv`
- **Body**: `multipart/form-data`
  - `file`: The `.csv` file containing headers: `roll_no`, `leetcode_id`, `codechef_id`, `codeforces_id`.
- **Response**: `200 OK`
  ```json
  {
    "message": "CSV data stored successfully",
    "count": 25,
    "data": [ ... ]
  }
  ```

### 16. Get All Platforms
Retrieve all stored platform IDs.
- **Method**: `GET`
- **Endpoint**: `/platforms`
- **Response**: `200 OK`
  ```json
  [
    {
      "roll_no": "21CS001",
      "leetcode_id": "arjun_lc",
      "codeforces_id": "arjun_cf",
      "codechef_id": "arjun_cc",
      "created_at": "2023-10-01T12:00:00Z"
    }
  ]
  ```

---

## Platform & LeetCode Analytics

### 17. Platform Department Leaderboard
Aggregated total scores grouped by department for a specific platform.
- **Method**: `GET`
- **Endpoint**: `/analytics/department?platform={platform}`
- **Parameters**: `platform` (optional, default: `hackerrank`)
- **Example**: `/analytics/department?platform=leetcode`
- **Response**: `200 OK`
  ```json
  [
    {
      "department": "CSE",
      "total_score": 25000
    },
    {
      "department": "IT",
      "total_score": 18000
    }
  ]
  ```

### 18. LeetCode Analytics
Returns detailed LeetCode stats for all students.
- **Method**: `GET`
- **Endpoint**: `/analytics/leetcode`
- **Response**: `200 OK`
  ```json
  [
    {
      "roll_no": "23CS001",
      "name": "Jane Doe",
      "department": "CSE",
      "section": "A",
      "year": 1,
      "weekly_rank": 1500,
      "weekly_problems_solved": 3,
      "biweekly_rank": 2000,
      "biweekly_problems_solved": 2,
      "contest_rating": 1650,
      "total_problems_solved": 450
    }
  ]
  ```

### 19. Sync LeetCode Stats
Manually trigger a sync from LeetCode GraphQL API for all students who have a `leetcode_id`.
- **Method**: `POST`
- **Endpoint**: `/sync/leetcode`
- **Response**: `200 OK`
  ```json
  {
    "message": "LeetCode stats synced for 25 students"
  }
  ```

---

## Utility Endpoints

### 20. Welcome Message
The root endpoint of the API.
- **Method**: `GET`
- **Endpoint**: `/`
- **Response**: `200 OK`
  ```json
  {
    "message": "Welcome to HackerRank Analysis Backend API"
  }
  ```

### 21. Health Check
Check the server status and Supabase connection.
- **Method**: `GET`
- **Endpoint**: `/health`
- **Response**: `200 OK`
  ```json
  {
    "status": "ok",
    "supabase_connected": true
  }
  ```
