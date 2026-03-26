from fastapi import APIRouter, HTTPException, UploadFile, File
from database import CacheService, supabase
from schemas import StudentPlatform, StudentPlatformUpdate
from typing import List
import csv
import io
import re
from utils.logger import get_logger

logger = get_logger("routers.platforms")

router = APIRouter(tags=["Platforms"])

cache = CacheService(namespace="platforms", default_ttl=30)


def clean_leetcode_username(raw_id: str) -> str:
    if not raw_id or not isinstance(raw_id, str):
        return raw_id
    raw_id = raw_id.strip().rstrip('/')
    if '/' in raw_id:
        raw_id = raw_id.split('/')[-1]
    raw_id = raw_id.replace('(new)', '')
    raw_id = re.sub(r'[^a-zA-Z0-9_-].*$', '', raw_id)
    return raw_id.strip()


@router.post("/platforms/bulk")
def add_platforms_bulk(platforms: List[StudentPlatform]):
    try:
        data = []
        for p in platforms:
            item = p.model_dump()
            if item.get("leetcode_id"):
                item["leetcode_id"] = clean_leetcode_username(item["leetcode_id"])
            data.append(item)
        
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
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
    try:
        content = await file.read()
        decoded = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        
        platform_data = []
        for row in reader:
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
            
        response = supabase.table("student_platforms").upsert(platform_data).execute()
        cache.delete("platforms_all")
        
        return {
            "message": "CSV data stored successfully",
            "count": len(response.data),
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV upload failed: {str(e)}")


@router.get("/platforms")
def get_all_platforms():
    cache_key = "platforms_all"
    
    def fetch():
        response = supabase.table("student_platforms").select("*").execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.post("/platforms")
def add_platform_entry(platform_data: StudentPlatform):
    try:
        student_resp = supabase.table("students").select("roll_no").eq("roll_no", platform_data.roll_no).execute()
        if not student_resp.data:
            raise HTTPException(status_code=404, detail=f"Student with roll_no {platform_data.roll_no} not found.")

        data = platform_data.model_dump()
        if data.get("leetcode_id"):
            data["leetcode_id"] = clean_leetcode_username(data["leetcode_id"])

        response = supabase.table("student_platforms").upsert(data).execute()
        cache.delete("platforms_all")
        
        return {"message": "Platform IDs added successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add platform IDs: {str(e)}")


@router.patch("/platforms/{roll_no}")
def update_platform_entry(roll_no: str, platform_update: StudentPlatformUpdate):
    try:
        update_data = platform_update.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update.")

        student_fields = {}
        platform_fields = {}

        if "hackerrank_username" in update_data:
            student_fields["hackerrank_username"] = update_data.pop("hackerrank_username")

        if "leetcode_id" in update_data:
            update_data["leetcode_id"] = clean_leetcode_username(update_data["leetcode_id"])

        platform_fields = update_data

        if student_fields:
            response = supabase.table("students").update(student_fields).eq("roll_no", roll_no).execute()
            if not response.data:
                raise HTTPException(status_code=404, detail=f"Student with roll_no {roll_no} not found.")

        if platform_fields:
            response = supabase.table("student_platforms").update(platform_fields).eq("roll_no", roll_no).execute()

            if not response.data:
                raise HTTPException(status_code=404, detail=f"Student with roll_no {roll_no} not found in platform table.")

        cache.delete("platforms_all")
        
        return {"message": "Platform IDs updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Update failed: {str(e)}")
