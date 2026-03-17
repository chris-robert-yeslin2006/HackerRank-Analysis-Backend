from fastapi import APIRouter, HTTPException, UploadFile, File
from database import supabase, redis_client
from schemas import StudentPlatform, StudentPlatformUpdate
from typing import List
import csv
import io
import re
import json
import time

router = APIRouter(tags=["Platforms"])

_cache = {}
_cache_ttl = 30

def get_cached(key):
    if redis_client:
        try:
            data = redis_client.get(f"cache:{key}")
            if data:
                print(f"🔵 Redis HIT: {key}")
                return json.loads(data)
            print(f"🔴 Redis MISS: {key}")
        except Exception as e:
            print(f"⚠️ Redis error: {e}")
    
    if key in _cache:
        data, timestamp = _cache[key]
        if time.time() - timestamp < _cache_ttl:
            print(f"🔵 Memory HIT: {key}")
            return data
    return None

def set_cached(key, value):
    if redis_client:
        try:
            redis_client.set(f"cache:{key}", json.dumps(value), ex=30)
            print(f"✅ Redis SET: {key}")
            return
        except Exception as e:
            print(f"⚠️ Redis set error: {e}")
    
    _cache[key] = (value, time.time())
    print(f"✅ Memory SET: {key}")

def invalidate_cache(prefix=None):
    global _cache
    if redis_client:
        try:
            if prefix:
                keys = redis_client.keys(f"cache:{prefix}*")
                if keys:
                    redis_client.delete(*keys)
            else:
                keys = redis_client.keys("cache:*")
                if keys:
                    redis_client.delete(*keys)
        except Exception as e:
            print(f"⚠️ Redis invalidate error: {e}")
    
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
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.table("student_platforms").select("*").execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        
        return {"message": "Platform IDs added successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add platform IDs: {str(e)}")

@router.patch("/platforms/{roll_no}")
def update_platform_entry(roll_no: str, platform_update: StudentPlatformUpdate):
    try:
        update_data = platform_update.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update.")

        if "leetcode_id" in update_data:
            update_data["leetcode_id"] = clean_leetcode_username(update_data["leetcode_id"])

        response = supabase.table("student_platforms").update(update_data).eq("roll_no", roll_no).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail=f"Student with roll_no {roll_no} not found in platform table.")

        return {"message": "Platform IDs updated successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Update failed: {str(e)}")