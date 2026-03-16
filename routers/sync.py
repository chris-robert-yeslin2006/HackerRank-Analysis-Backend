import httpx
import asyncio
import re
from fastapi import APIRouter, HTTPException
from database import supabase
from typing import Dict, Any
from datetime import datetime, timezone

router = APIRouter(tags=["Sync"])

LEETCODE_URL = "https://leetcode.com/graphql"

def clean_leetcode_username(raw_id: str) -> str:
    """
    Cleans a raw LeetCode ID by removing URLs, suffixes like '(new)', and trailing slashes.
    Example: 'https://leetcode.com/u/Bharathvaj77/:' -> 'Bharathvaj77'
    """
    if not raw_id or not isinstance(raw_id, str):
        return ""
    
    # Remove trailing slashes and common URL prefixes
    raw_id = raw_id.strip().rstrip('/')
    if '/' in raw_id:
        raw_id = raw_id.split('/')[-1]
    
    # Remove common suffixes like (new)
    raw_id = raw_id.replace('(new)', '')
    
    # Remove non-alphanumeric trailing characters (like : in the user's example)
    raw_id = re.sub(r'[^a-zA-Z0-9_-].*$', '', raw_id)
    
    return raw_id.strip()

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

async def fetch_user(client: httpx.AsyncClient, student: Dict[str, Any], semaphore: asyncio.Semaphore):
    raw_username = student.get("leetcode_id", "")
    username = clean_leetcode_username(raw_username)
    
    if not username:
        print(f"Empty or invalid LeetCode ID for student {student.get('roll_no')}")
        return

    async with semaphore:
        variables = {"username": username}
        headers = {
            'Content-Type': 'application/json',
            'Referer': f'https://leetcode.com/u/{username}/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        try:
            # Add a small staggered delay
            await asyncio.sleep(0.5) 

            r = await client.post(
                LEETCODE_URL,
                json={"query": QUERY, "variables": variables},
                headers=headers,
                timeout=20.0
            )
            
            if r.status_code == 429:
                print(f"Rate limited for {username}. Retrying later.")
                return

            r.raise_for_status()
            res_data = r.json()
            
            if "data" not in res_data or not res_data["data"].get("matchedUser"):
                print(f"User {username} not found on LeetCode.")
                return

            data = res_data["data"]

            # Extract total solved by difficulty
            total_solved = 0
            easy_solved = 0
            medium_solved = 0
            hard_solved = 0
            
            if data["matchedUser"] and data["matchedUser"]["submitStats"]:
                stats = data["matchedUser"]["submitStats"]["acSubmissionNum"]
                for s in stats:
                    if s["difficulty"] == "All":
                        total_solved = s["count"]
                    elif s["difficulty"] == "Easy":
                        easy_solved = s["count"]
                    elif s["difficulty"] == "Medium":
                        medium_solved = s["count"]
                    elif s["difficulty"] == "Hard":
                        hard_solved = s["count"]

            # Fetch existing stats to calculate "today" delta
            existing_resp = supabase.table("leetcode_stats").select("easy_solved, medium_solved, hard_solved, easy_today, medium_today, hard_today, updated_at").eq("roll_no", student["roll_no"]).execute()
            
            easy_today = 0
            medium_today = 0
            hard_today = 0
            
            if existing_resp.data:
                old_stats = existing_resp.data[0]
                last_updated_str = old_stats.get("updated_at")
                
                # Calculate delta from last sync
                delta_easy = max(0, easy_solved - old_stats.get("easy_solved", 0))
                delta_medium = max(0, medium_solved - old_stats.get("medium_solved", 0))
                delta_hard = max(0, hard_solved - old_stats.get("hard_solved", 0))

                # Check if the last update was on the same day (UTC)
                now_utc = datetime.now(timezone.utc)
                is_same_day = False
                if last_updated_str:
                    last_updated_dt = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
                    if last_updated_dt.date() == now_utc.date():
                        is_same_day = True
                
                if is_same_day:
                    # If same day, add the new delta to the existing "today" count
                    easy_today = old_stats.get("easy_today", 0) + delta_easy
                    medium_today = old_stats.get("medium_today", 0) + delta_medium
                    hard_today = old_stats.get("hard_today", 0) + delta_hard
                else:
                    # If new day, the delta itself becomes the new "today" count
                    easy_today = delta_easy
                    medium_today = delta_medium
                    hard_today = delta_hard
            else:
                # No previous record, so today's count is the total count
                easy_today = easy_solved
                medium_today = medium_solved
                hard_today = hard_solved
            
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
                "easy_solved": easy_solved,
                "medium_solved": medium_solved,
                "hard_solved": hard_solved,
                "easy_today": easy_today,
                "medium_today": medium_today,
                "hard_today": hard_today,
                "updated_at": "now()"
            }).execute()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error for {username}: {e.response.status_code}")
        except Exception as e:
            print(f"Error fetching data for {username}: {str(e)}")

@router.post("/sync/leetcode")
async def sync_leetcode():
    try:
        # Get students who have a leetcode_id
        response = supabase.rpc("get_students_with_leetcode").execute()
        students = response.data

        if not students:
            return {"message": "No students with LeetCode IDs found"}

        # Limit concurrency to 5 simultaneous requests
        semaphore = asyncio.Semaphore(5)

        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [fetch_user(client, student, semaphore) for student in students]
            await asyncio.gather(*tasks)

        return {"message": f"LeetCode sync completed for {len(students)} students"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sync failed: {str(e)}")
