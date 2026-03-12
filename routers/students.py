from fastapi import APIRouter, HTTPException, UploadFile, File
from database import supabase
from schemas import StudentCreate, StudentUpdate
import csv
import io
import httpx

router = APIRouter(tags=["Students"])

@router.get("/students")
def get_all_students():
    try:
        # Fetch all students from the database
        response = supabase.table("students").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/students")
def add_student(student: StudentCreate):
    try:
        response = supabase.table("students").insert(student.model_dump()).execute()
        return {"message": "Student added successfully", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/students/bulk")
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
