from fastapi import APIRouter, HTTPException
from database import supabase, redis_client
from schemas import LeaderboardEntryCreate
from typing import List
import json
import time

router = APIRouter(tags=["Leaderboard"])

_cache = {}
_cache_ttl = 60

def get_cached(key):
    if redis_client:
        try:
            data = redis_client.get(f"cache:{key}")
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"⚠️ Redis error: {e}")
    
    if key in _cache:
        data, timestamp = _cache[key]
        if time.time() - timestamp < _cache_ttl:
            return data
    return None

def set_cached(key, value):
    if redis_client:
        try:
            redis_client.set(f"cache:{key}", json.dumps(value), ex=60)
            return
        except Exception as e:
            print(f"⚠️ Redis set error: {e}")
    
    _cache[key] = (value, time.time())

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

@router.post("/leaderboard")
def add_leaderboard_entry(entry: LeaderboardEntryCreate):
    try:
        # Convert date to string if present
        data = entry.model_dump()
        if data.get("contest_date"):
            data["contest_date"] = data["contest_date"].isoformat()
            
        response = supabase.table("leaderboard").insert(data).execute()
        if not response.data:
             raise HTTPException(status_code=400, detail="Failed to add leaderboard entry")
        
        invalidate_cache("frontend")
        invalidate_cache("section")
        invalidate_cache("top_students")
        invalidate_cache("dept")
        invalidate_cache("leaderboard")
        invalidate_cache("absent")
        
        return {"message": "Leaderboard entry added successfully", "data": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error adding entry: {str(e)}")

@router.post("/leaderboard/bulk")
def add_leaderboard_bulk(entries: List[LeaderboardEntryCreate]):
    try:
        data = []

        for entry in entries:
            row = entry.model_dump()

            if row.get("contest_date"):
                row["contest_date"] = row["contest_date"].isoformat()

            data.append(row)

        if not data:
            raise HTTPException(status_code=400, detail="No entries provided")

        response = supabase.table("leaderboard").insert(data).execute()

        invalidate_cache("frontend")
        invalidate_cache("section")
        invalidate_cache("top_students")
        invalidate_cache("dept")
        invalidate_cache("leaderboard")
        invalidate_cache("absent")

        return {"message": "Bulk upload successful", "inserted": len(response.data), "data": response.data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bulk upload failed: {str(e)}")
