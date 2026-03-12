# HackerRank Analysis Backend API

This document provides a summary of all available APIs for the frontend dev to test out.

**Base URL**: `http://127.0.0.1:8000`

---

## Data Ingestion Endpoints

### 1. Add Single Student
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

### 2. Bulk Upload Students (CSV)
Uploads multiple students at once via a CSV file.
- **Method**: `POST`
- **Endpoint**: `/students/bulk`
- **Body**: `multipart/form-data`
  - [file](file:///Users/yeslin-parker/project/HackerRank-Analysis-Backend/Dockerfile): The `.csv` file containing headers: `roll_no`, `name`, [department](file:///Users/yeslin-parker/project/HackerRank-Analysis-Backend/main.py#180-188), [section](file:///Users/yeslin-parker/project/HackerRank-Analysis-Backend/main.py#189-196), `year`, `hackerrank_username`.

### 3. Update Single Student
Edits an existing student's data. You can pass only the fields you want to change.
- **Method**: `PATCH`
- **Endpoint**: `/students/{student_id}`
- **Body**: (Partial JSON object)
  ```json
  {
    "department": "IT",
    "year": 2
  }
  ```

### 4. Delete Single Student
Deletes a student by their ID. This only removes the student and does not delete their leaderboard records.

- **Method**: `DELETE`
- **Endpoint**: `/students/{student_id}`
- **Body**: (Partial JSON object)
  ```json
  {
    "department": "IT",
    "year": 2
  }
  ```

### 5. Add Single Leaderboard Entry
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

### 6. Bulk Upload Leaderboard Entries
Uploads multiple scraped contest results at once.
- **Method**: `POST`
- **Endpoint**: `/leaderboard/bulk`
- **Body**: Array of JSON objects
  ```json
  [
    {
      "contest_name": "week1_batch1",
      "contest_date": "2023-10-01",
      "username": "jane_hr",
      "score": 150,
      "time_taken": 45
    }
  ]
  ```

---

## Analytics Endpoints

### 7. Frontend Raw Data
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

### 8. Department Leaderboard
Aggregated total scores grouped by department.
- **Method**: `GET`
- **Endpoint**: `/analytics/department`

### 9. Section Leaderboard
Aggregated total scores grouped by section.
- **Method**: `GET`
- **Endpoint**: `/analytics/section`

### 10. Top 10 Students
Returns the top 10 students across all contests sorted by total score.
- **Method**: `GET`
- **Endpoint**: `/analytics/top-students`

### 11. Absent Students for Contest
Returns all students who did NOT participate in a given `contest_name`.
- **Method**: `GET`
- **Endpoint**: `/analytics/absent-students/{contest_name}`
- **Returns**: Array of `AbsentStudent` objects
  ```json
  [
    {
      "id": "abc-123",
      "name": "John Doe",
      "dept": "IT",
      "section": "B",
      "year": 2
    }
  ]
  ```

---

## Utility Endpoints

### 12. Health Check
Check the server status and Supabase connection.
- **Method**: `GET`
- **Endpoint**: `/health`

---

## Authentication Endpoints

### 13. Admin Login
Logs in the administrator. On success, this endpoint returns a `200 OK` and sets an `HttpOnly` cookie named `auth_token` with the value `true`. The frontend can check this cookie presence using credentials/middleware.
- **Method**: `POST`
- **Endpoint**: `/login`
- **Body**:
  ```json
  {
    "username": "admin",
    "password": "Admin@123"
  }
  ```
- **Response**:
  ```json
  {
    "message": "Login successful",
    "authenticated": true
  }
  ```
