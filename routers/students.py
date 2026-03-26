from fastapi import APIRouter, HTTPException, UploadFile, File
from database import CacheService, supabase
from schemas import StudentCreate, StudentUpdate, Student, StudentFullUpdate
from typing import List
import csv
import io
import re
from utils.logger import get_logger

logger = get_logger("routers.students")

router = APIRouter(tags=["Students"])

cache = CacheService(namespace="students", default_ttl=30)


def clean_leetcode_username(raw_id: str) -> str:
    if not raw_id or not isinstance(raw_id, str):
        return raw_id
    raw_id = raw_id.strip().rstrip('/')
    if '/' in raw_id:
        raw_id = raw_id.split('/')[-1]
    raw_id = raw_id.replace('(new)', '')
    raw_id = re.sub(r'[^a-zA-Z0-9_-].*$', '', raw_id)
    return raw_id.strip()


@router.get("/students", response_model=List[Student])
def get_all_students():
    cache_key = "students_all"
    
    def fetch():
        response = supabase.table("students").select("*").execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.post("/students")
def add_student(student: StudentCreate):
    try:
        response = supabase.table("students").insert(student.model_dump()).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to add student")
        cache.delete("students_all")
        return {"message": "Student added successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error adding student: {str(e)}")


@router.post("/students/bulk")
async def add_students_bulk(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        content = await file.read()
        decoded = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        
        students_data = []
        for row in reader:
            cleaned_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            
            required_fields = ["roll_no", "name", "department", "section", "year", "hackerrank_username"]
            if not all(field in cleaned_row for field in required_fields):
                missing = [f for f in required_fields if f not in cleaned_row]
                raise HTTPException(status_code=400, detail=f"CSV missing required headers: {', '.join(missing)}")
            
            try:
                year_val = int(cleaned_row["year"])
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid year value for student {cleaned_row.get('name', 'unknown')}")

            students_data.append({
                "roll_no": cleaned_row["roll_no"],
                "name": cleaned_row["name"],
                "department": cleaned_row["department"],
                "section": cleaned_row["section"],
                "year": year_val,
                "hackerrank_username": cleaned_row["hackerrank_username"]
            })
            
        if not students_data:
            raise HTTPException(status_code=400, detail="CSV file is empty")
            
        response = supabase.table("students").upsert(students_data, on_conflict="roll_no").execute()
        cache.delete("students_all")
        return {"message": "Bulk upload successful", "inserted": len(response.data), "data": response.data}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bulk upload failed: {str(e)}")


@router.patch("/students/{roll_no}")
def update_student(roll_no: str, student_update: StudentUpdate):
    try:
        data = student_update.model_dump(exclude_unset=True)
        
        if not data:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        existing = supabase.table("students").select("roll_no").eq("roll_no", roll_no).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Student not found")

        student_fields = {}
        platform_fields = {}

        for key, value in data.items():
            if key in ["name", "department", "section", "year", "hackerrank_username"]:
                if value is not None:
                    student_fields[key] = value
            elif key in ["leetcode_id", "codeforces_id", "codechef_id"]:
                if key == "leetcode_id" and value:
                    value = clean_leetcode_username(value)
                if value is not None:
                    platform_fields[key] = value

        if student_fields:
            supabase.table("students").update(student_fields).eq("roll_no", roll_no).execute()
        
        if platform_fields:
            supabase.table("student_platforms").upsert({
                "roll_no": roll_no,
                **platform_fields
            }).execute()
        
        cache.delete("students_all")
            
        return {"message": "Student updated successfully", "roll_no": roll_no}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/students/{student_id}")
def delete_student(student_id: str):
    try:
        response = supabase.table("students").delete().eq("id", student_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Student not found")
        
        cache.delete("students_all")
            
        return {"message": "Student deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/students/roll/{roll_no}")
def get_student_by_roll(roll_no: str):
    try:
        response = supabase.table("students").select("*").eq("roll_no", roll_no).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Student not found")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
