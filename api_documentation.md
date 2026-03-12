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
- **Response**: `200 OK` (Sets `HttpOnly` cookie: `auth_token=true`)

---

## Data Ingestion Endpoints (Students)

### 2. Get All Students
Fetches all students from the database. Use this to retrieve the `id` (UUID) needed to edit or delete a specific student.
- **Method**: `GET`
- **Endpoint**: `/students`
- **Returns**: Array of Student objects

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

### 4. Bulk Upload Students (CSV)
Uploads multiple students at once via a CSV file.
- **Method**: `POST`
- **Endpoint**: `/students/bulk`
- **Body**: `multipart/form-data`
  - `file`: The `.csv` file containing headers: `roll_no`, `name`, `department`, `section`, `year`, `hackerrank_username`.

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

### 6. Delete Single Student
Deletes a student by their ID. This only removes the student and does not delete their leaderboard contest records.
- **Method**: `DELETE`
- **Endpoint**: `/students/{student_id}`

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

### 8. Bulk Upload Leaderboard Entries
Uploads multiple scraped contest results at once.
- **Method**: `POST`
- **Endpoint**: `/leaderboard/bulk`
- **Body**: Array of JSON objects

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
Aggregated total scores grouped by department.
- **Method**: `GET`
- **Endpoint**: `/analytics/department`

### 11. Section Leaderboard
Aggregated total scores grouped by section.
- **Method**: `GET`
- **Endpoint**: `/analytics/section`

### 12. Top 10 Students
Returns the top 10 students across all contests sorted by total score.
- **Method**: `GET`
- **Endpoint**: `/analytics/top-students`

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

## Utility Endpoints

### 14. Health Check
Check the server status and Supabase connection.
- **Method**: `GET`
- **Endpoint**: `/health`
