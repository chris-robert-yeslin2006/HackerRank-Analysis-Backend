from fastapi import APIRouter, HTTPException, UploadFile, File
from database import supabase
from schemas import StudentPlatform
from typing import List
import csv
import io

router = APIRouter(tags=["Platforms"])

@router.post("/platforms/bulk")
def add_platforms_bulk(platforms: List[StudentPlatform]):
    """
    Store multiple student platform IDs via JSON array.
    """
    try:
        data = [p.model_dump() for p in platforms]
        
        # Using upsert to update if roll_no exists
        response = supabase.table("student_platforms").upsert(data).execute()
        
        return {
            "message": "Platform IDs stored successfully",
            "count": len(response.data),
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to store platforms: {str(e)}")

@router.post("/platforms/csv")
async def add_platforms_csv(file: UploadFile = File(...)):
    """
    Store student platform IDs via CSV file.
    Expected headers: roll_no, leetcode_id, codechef_id, codeforces_id
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
    try:
        content = await file.read()
        decoded = content.decode('utf-8-sig') # Handle BOM
        reader = csv.DictReader(io.StringIO(decoded))
        
        platform_data = []
        for row in reader:
            # Clean up headers (case-insensitive and trimmed)
            cleaned_row = {k.strip().lower(): v.strip() if v else None for k, v in row.items() if k}
            
            if "roll_no" not in cleaned_row:
                raise HTTPException(status_code=400, detail="CSV must contain 'roll_no' column")
                
            platform_data.append({
                "roll_no": cleaned_row["roll_no"],
                "leetcode_id": cleaned_row.get("leetcode_id"),
                "codechef_id": cleaned_row.get("codechef_id"),
                "codeforces_id": cleaned_row.get("codeforces_id")
            })
            
        if not platform_data:
            raise HTTPException(status_code=400, detail="CSV file is empty")
            
        # Using upsert to update if roll_no exists
        response = supabase.table("student_platforms").upsert(platform_data).execute()
        
        return {
            "message": "CSV data stored successfully",
            "count": len(response.data),
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV upload failed: {str(e)}")

@router.get("/platforms")
def get_all_platforms():
    """
    Retrieve all stored platform IDs.
    """
    try:
        response = supabase.table("student_platforms").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
