from fastapi import APIRouter, HTTPException, UploadFile, File
from database import supabase
from schemas import StudentCreate, StudentUpdate, Student, StudentFullUpdate
from typing import List
import csv
import io
import re
import time

router = APIRouter(tags=["Students"])

_cache = {}
_cache_ttl = 30  # Cache TTL in seconds

def get_cached(key):
    if key in _cache:
        data, timestamp = _cache[key]
        if time.time() - timestamp < _cache_ttl:
            return data
    return None

def set_cached(key, value):
    _cache[key] = (value, time.time())

def invalidate_cache(prefix=None):
    global _cache
    if prefix:
        _cache = {k: v for k, v in _cache.items() if not k.startswith(prefix)}
    else:
        _cache = {}

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
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.table("students").select("*").execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch students: {str(e)}")

@router.post("/students")
def add_student(student: StudentCreate):
    try:
        response = supabase.table("students").insert(student.model_dump()).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to add student")
        invalidate_cache("students")
        return {"message": "Student added successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error adding student: {str(e)}")

@router.post("/students/bulk")
async def add_students_bulk(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        content = await file.read()
        decoded = content.decode('utf-8-sig') # Handle BOM
        reader = csv.DictReader(io.StringIO(decoded))
        
        students_data = []
        for row in reader:
            # Clean up headers (case-insensitive and trimmed)
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
            
        # Use upsert to handle existing records if roll_no or username matches
        response = supabase.table("students").upsert(students_data, on_conflict="roll_no").execute()
        invalidate_cache("students")
        return {"message": "Bulk upload successful", "inserted": len(response.data), "data": response.data}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bulk upload failed: {str(e)}")

@router.patch("/students/{student_id}")
def update_student(student_id: str, student_update: StudentUpdate):
    try:
        # Pass exclude_unset=True to only update the fields provided in the payload
        update_data = student_update.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        response = supabase.table("students").update(update_data).eq("id", student_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Student not found")
        invalidate_cache("students")
        return {"message": "Student updated successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/students/{student_id}")
def delete_student(student_id: str):
    try:
        response = supabase.table("students").delete().eq("id", student_id).execute()
        
        # When a deletion doesn't match any row, Supabase returns an empty data list
        if not response.data:
            raise HTTPException(status_code=404, detail="Student not found")
            
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

@router.put("/students/full")
def update_student_full(student_update: StudentFullUpdate):
    try:
        data = student_update.model_dump(exclude_unset=True)
        roll_no = data.pop("roll_no")
        
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
            student_response = supabase.table("students").update(student_fields).eq("roll_no", roll_no).execute()
            if not student_response.data:
                raise HTTPException(status_code=404, detail="Student not found")
        
        if platform_fields:
            platform_response = supabase.table("student_platforms").upsert({
                "roll_no": roll_no,
                **platform_fields
            }).execute()
        
        return {"message": "Student updated successfully", "roll_no": roll_no}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/students/full")
def patch_student_full(student_update: StudentFullUpdate):
    return update_student_full(student_update)
