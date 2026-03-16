import httpx
import asyncio
from fastapi import APIRouter, HTTPException
from database import supabase
from typing import Dict, Any

router = APIRouter(tags=["Sync"])

LEETCODE_URL = "https://leetcode.com/graphql"

QUERY = """
query getUserData($username: String!) {
  matchedUser(username: $username) {
    submitStats {
      acSubmissionNum {
        difficulty
        count
      }
    }
  }

  userContestRanking(username: $username) {
    rating
  }

  userContestRankingHistory(username: $username) {
    contest {
      title
    }
    ranking
    problemsSolved
  }
}
"""

async def fetch_user(client: httpx.AsyncClient, student: Dict[str, Any]):
    variables = {"username": student["leetcode_id"]}
    try:
        r = await client.post(
            LEETCODE_URL,
            json={"query": QUERY, "variables": variables},
            timeout=20.0
        )
        r.raise_for_status()
        res_data = r.json()
        
        if "data" not in res_data or not res_data["data"].get("matchedUser"):
            print(f"User {student['leetcode_id']} not found or invalid response.")
            return

        data = res_data["data"]

        # Extract total solved
        total_solved = 0
        if data["matchedUser"] and data["matchedUser"]["submitStats"]:
            total_solved = data["matchedUser"]["submitStats"]["acSubmissionNum"][0]["count"]

        # Extract rating
        rating = None
        if data["userContestRanking"]:
            rating = int(data["userContestRanking"]["rating"])

        weekly_rank = None
        weekly_solved = None
        biweekly_rank = None
        biweekly_solved = None

        # Extract history
        history = data.get("userContestRankingHistory", [])
        if history:
            for contest in reversed(history):
                if not contest.get("contest"):
                    continue
                    
                title = contest["contest"]["title"]

                if "Weekly Contest" in title and weekly_rank is None:
                    weekly_rank = contest["ranking"]
                    weekly_solved = contest["problemsSolved"]

                if "Biweekly Contest" in title and biweekly_rank is None:
                    biweekly_rank = contest["ranking"]
                    biweekly_solved = contest["problemsSolved"]
                
                if weekly_rank is not None and biweekly_rank is not None:
                    break

        # Upsert stats to Supabase
        supabase.table("leetcode_stats").upsert({
            "roll_no": student["roll_no"],
            "weekly_rank": weekly_rank,
            "weekly_problems_solved": weekly_solved,
            "biweekly_rank": biweekly_rank,
            "biweekly_problems_solved": biweekly_solved,
            "contest_rating": rating,
            "total_problems_solved": total_solved,
            "updated_at": "now()"
        }).execute()

    except Exception as e:
        print(f"Error fetching data for {student['leetcode_id']}: {str(e)}")

@router.post("/sync/leetcode")
async def sync_leetcode():
    try:
        # Get students who have a leetcode_id
        response = supabase.rpc("get_students_with_leetcode").execute()
        students = response.data

        if not students:
            return {"message": "No students with LeetCode IDs found"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [fetch_user(client, student) for student in students]
            await asyncio.gather(*tasks)

        return {"message": f"LeetCode stats synced for {len(students)} students"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sync failed: {str(e)}")
