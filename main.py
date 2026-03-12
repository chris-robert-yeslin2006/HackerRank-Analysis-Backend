import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from dotenv import load_dotenv
import csv
import io
import httpx

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="HackerRank Analysis API",
    description="API for HackerRank Analysis Backend with Supabase",
    version="1.0.0"
)

# CORS setup for future frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

supabase: Client = create_client(url, key)

# --- Pydantic Models for Data Ingestion ---

class StudentCreate(BaseModel):
    roll_no: str
    name: str
    department: str
    section: str
    year: int
    hackerrank_username: str

class StudentUpdate(BaseModel):
    roll_no: Optional[str] = None
    name: Optional[str] = None
    department: Optional[str] = None
    section: Optional[str] = None
    year: Optional[int] = None
    hackerrank_username: Optional[str] = None

class LeaderboardEntryCreate(BaseModel):
    contest_name: str
    contest_date: Optional[date] = None
    username: str
    score: int
    time_taken: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# --- Basic Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Welcome to HackerRank Analysis Backend API"}

@app.get("/health")
def health_check():
    return {"status": "ok", "supabase_connected": supabase is not None}

# --- Auth Endpoint ---

@app.post("/login")
def login(login_data: LoginRequest, response: Response):
    # Hardcoded admin credentials as requested
    if login_data.username == "admin" and login_data.password == "Admin@123":
        # Set a cookie named 'auth_token' with value 'true'
        # httponly=True protects it from cross-site scripting (XSS)
        # samesite='lax' allows it to be sent with top-level navigations
        response.set_cookie(
            key="auth_token", 
            value="true", 
            httponly=True, 
            samesite="lax",
            max_age=86400 # 1 day expiration
        )
        return {"message": "Login successful", "authenticated": True}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

# --- Data Ingestion Endpoints (Optional but helpful) ---

@app.post("/students")
def add_student(student: StudentCreate):
    try:
        response = supabase.table("students").insert(student.model_dump()).execute()
        return {"message": "Student added successfully", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/students/bulk")
async def add_students_bulk(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        
        students_data = []
        for row in reader:
            # Clean up headers (remove BOM or spaces if any)
            cleaned_row = {k.strip('\ufeff ').lower(): v.strip() for k, v in row.items()}
            
            # Require minimum fields
            if not all(k in cleaned_row for k in ["roll_no", "name", "department", "section", "year", "hackerrank_username"]):
                raise HTTPException(status_code=400, detail="CSV is missing required headers (roll_no, name, department, section, year, hackerrank_username)")
            
            students_data.append({
                "roll_no": cleaned_row["roll_no"],
                "name": cleaned_row["name"],
                "department": cleaned_row["department"],
                "section": cleaned_row["section"],
                "year": int(cleaned_row["year"]),
                "hackerrank_username": cleaned_row["hackerrank_username"]
            })
            
        if not students_data:
            raise HTTPException(status_code=400, detail="CSV file is empty")
            
        response = supabase.table("students").insert(students_data).execute()
        return {"message": "Bulk upload successful", "inserted": len(students_data)}
        
    except httpx.HTTPStatusError as e:
        # Better error handling for Supabase duplication errors
        error_detail = e.response.json()
        raise HTTPException(status_code=400, detail=f"Database error: {error_detail.get('message', str(e))}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/students/{student_id}")
def update_student(student_id: str, student_update: StudentUpdate):
    try:
        # Pass exclude_unset=True to only update the fields provided in the payload
        update_data = student_update.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        response = supabase.table("students").update(update_data).eq("id", student_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Student not found")
            
        return {"message": "Student updated successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/students/{student_id}")
def delete_student(student_id: str):
    try:
        response = supabase.table("students").delete().eq("id", student_id).execute()
        
        # When a deletion doesn't match any row, Supabase returns an empty data list
        if not response.data:
            raise HTTPException(status_code=404, detail="Student not found")
            
        return {"message": "Student deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/leaderboard")
def add_leaderboard_entry(entry: LeaderboardEntryCreate):
    try:
        # Convert date to string if present
        data = entry.model_dump()
        if data.get("contest_date"):
            data["contest_date"] = data["contest_date"].isoformat()
            
        response = supabase.table("leaderboard").insert(data).execute()
        return {"message": "Leaderboard entry added successfully", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/leaderboard/bulk")
def add_leaderboard_bulk(entries: List[LeaderboardEntryCreate]):
    try:
        data = []

        for entry in entries:
            row = entry.model_dump()

            if row.get("contest_date"):
                row["contest_date"] = row["contest_date"].isoformat()

            data.append(row)

        response = supabase.table("leaderboard").insert(data).execute()

        return {"message": "Bulk upload successful", "inserted": len(data)}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Analytics Endpoints ---

@app.get("/analytics/department")
def get_department_leaderboard():
    try:
        # Calling the RPC function deployed on Supabase
        response = supabase.rpc("get_department_leaderboard").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching data. Did you run the RPC SQL in Supabase? Error: {str(e)}")

@app.get("/analytics/section")
def get_section_leaderboard():
    try:
        response = supabase.rpc("get_section_leaderboard").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/analytics/top-students")
def get_top_students():
    try:
        response = supabase.rpc("get_top_students").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/analytics/absent-students/{contest_name}")
def get_absent_students(contest_name: str):
    try:
        response = supabase.rpc("get_absent_students", {"p_contest_name": contest_name}).execute()
        # The RPC will now return {"id": str, "name": str, "dept": str, "section": str, "year": int}
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/frontend-data")
def get_frontend_data():
    try:
        # Get raw joined data with ranks computed in SQL
        response = supabase.rpc("get_all_raw_data").execute()
        raw_data = response.data

        # We need an array of ContestData objects based on the frontend interface
        # interface ContestData { year: string, dept: string, section: string, contests: { ... } }
        
        # We will group by an explicit key to build the structure
        # Key: (year, department, section) -> frontend dictionary
        grouped_data = {}

        for row in raw_data:
            year_int = row.get("year", 1)
            year_str = "I" if year_int == 1 else "II" if year_int == 2 else str(year_int)
            dept = row.get("department", "Unknown")
            sec = row.get("section", "Unknown")
            
            group_key = f"{year_str}-{dept}-{sec}"
            
            if group_key not in grouped_data:
                grouped_data[group_key] = {
                    "year": year_str,
                    "dept": dept,
                    "section": sec,
                    "contests": {}
                }
                
            contest_name = row.get("contest_name", "Unknown")
            if contest_name not in grouped_data[group_key]["contests"]:
                grouped_data[group_key]["contests"][contest_name] = {}
                
            user_id = row.get("username")
            grouped_data[group_key]["contests"][contest_name][user_id] = {
                "name": row.get("name"),
                "user-id": user_id,
                "score": row.get("score"),
                "time": str(row.get("time_taken")), # Format as string based on TS type
                "rank": row.get("rank")
            }
            
        # The frontend seems to expect a list of ContestData objects since they share different years, depts, sections
        return list(grouped_data.values())

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing frontend data: {str(e)}")
