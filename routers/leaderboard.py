from fastapi import APIRouter, HTTPException
from database import CacheService, supabase
from schemas import LeaderboardEntryCreate
from typing import List
from utils.logger import get_logger

logger = get_logger("routers.leaderboard")

router = APIRouter(tags=["Leaderboard"])

cache = CacheService(namespace="leaderboard", default_ttl=60)


@router.post("/leaderboard")
def add_leaderboard_entry(entry: LeaderboardEntryCreate):
    try:
        data = entry.model_dump()
        if data.get("contest_date"):
            data["contest_date"] = data["contest_date"].isoformat()
            
        response = supabase.table("leaderboard").insert(data).execute()
        if not response.data:
             raise HTTPException(status_code=400, detail="Failed to add leaderboard entry")
        
        cache.invalidate()
        
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

        cache.invalidate()

        return {"message": "Bulk upload successful", "inserted": len(response.data), "data": response.data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bulk upload failed: {str(e)}")
