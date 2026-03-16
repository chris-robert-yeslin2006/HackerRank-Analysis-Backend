from fastapi import APIRouter, HTTPException, UploadFile, File
from database import supabase
from schemas import StudentPlatform, StudentPlatformUpdate
from typing import List
import csv
import io
import re

router = APIRouter(tags=["Platforms"])

def clean_leetcode_username(raw_id: str) -> str:
    """
    Cleans a raw LeetCode ID by removing URLs, suffixes like '(new)', and trailing slashes.
    """
    if not raw_id or not isinstance(raw_id, str):
        return raw_id
    
    # Remove trailing slashes and common URL prefixes
    raw_id = raw_id.strip().rstrip('/')
    if '/' in raw_id:
        raw_id = raw_id.split('/')[-1]
    
    # Remove common suffixes like (new)
    raw_id = raw_id.replace('(new)', '')
    
    # Remove non-alphanumeric trailing characters
    raw_id = re.sub(r'[^a-zA-Z0-9_-].*$', '', raw_id)
    
    return raw_id.strip()

@router.post("/platforms/bulk")
def add_platforms_bulk(platforms: List[StudentPlatform]):
    """
    Store multiple student platform IDs via JSON array.
    """
    try:
        data = []
        for p in platforms:
            item = p.model_dump()
            if item.get("leetcode_id"):
                item["leetcode_id"] = clean_leetcode_username(item["leetcode_id"])
            data.append(item)
        
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
            
            leetcode_id = cleaned_row.get("leetcode_id")
            if leetcode_id:
                leetcode_id = clean_leetcode_username(leetcode_id)
                
            platform_data.append({
                "roll_no": cleaned_row["roll_no"],
                "leetcode_id": leetcode_id,
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

@router.post("/platforms")
def add_platform_entry(platform_data: StudentPlatform):
    """
    Adds platform IDs for a single student, verifying the student exists first.
    """
    try:
        # 1. Verify student exists
        student_resp = supabase.table("students").select("roll_no").eq("roll_no", platform_data.roll_no).execute()
        if not student_resp.data:
            raise HTTPException(status_code=404, detail=f"Student with roll_no {platform_data.roll_no} not found.")

        # 2. Clean and upsert data
        data = platform_data.model_dump()
        if data.get("leetcode_id"):
            data["leetcode_id"] = clean_leetcode_username(data["leetcode_id"])

        response = supabase.table("student_platforms").upsert(data).execute()
        
        return {"message": "Platform IDs added successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add platform IDs: {str(e)}")

@router.patch("/platforms/{roll_no}")
def update_platform_entry(roll_no: str, platform_update: StudentPlatformUpdate):
    """
    Updates one or more platform IDs for an existing student.
    """
    try:
        update_data = platform_update.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update.")

        # Clean LeetCode ID if present
        if "leetcode_id" in update_data:
            update_data["leetcode_id"] = clean_leetcode_username(update_data["leetcode_id"])

        response = supabase.table("student_platforms").update(update_data).eq("roll_no", roll_no).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail=f"Student with roll_no {roll_no} not found in platform table.")

        return {"message": "Platform IDs updated successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Update failed: {str(e)}")
