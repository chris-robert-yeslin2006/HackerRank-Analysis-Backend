from fastapi import APIRouter, HTTPException
from database import supabase
from schemas import LeaderboardEntryCreate
from typing import List

router = APIRouter(tags=["Leaderboard"])

@router.post("/leaderboard")
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

@router.post("/leaderboard/bulk")
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
