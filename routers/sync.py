import httpx
import asyncio
import re
from fastapi import APIRouter, HTTPException
from database import supabase
from typing import Dict, Any, List
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
        response = supabase.rpc("get_students_with_leetcode",{}).execute()
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

# ==========================================
# 🔄 Codeforces Sync
# ==========================================
CODEFORCES_API_BASE = "https://codeforces.com/api"

async def fetch_codeforces_user_info(client: httpx.AsyncClient, username: str) -> Dict[str, Any]:
    """Fetch user info from Codeforces API"""
    try:
        r = await client.get(f"{CODEFORCES_API_BASE}/user.info", params={"handles": username}, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK" and data.get("result"):
            return data["result"][0]
    except Exception as e:
        print(f"Error fetching Codeforces user info for {username}: {e}")
    return {}

async def fetch_codeforces_rating(client: httpx.AsyncClient, username: str) -> List[Dict[str, Any]]:
    """Fetch user's rating history"""
    try:
        r = await client.get(f"{CODEFORCES_API_BASE}/user.rating", params={"handle": username}, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            return data.get("result", [])
    except Exception as e:
        print(f"Error fetching Codeforces rating for {username}: {e}")
    return []

async def fetch_codeforces_submissions(client: httpx.AsyncClient, username: str) -> List[Dict[str, Any]]:
    """Fetch user's submissions for problem stats"""
    try:
        r = await client.get(f"{CODEFORCES_API_BASE}/user.status", params={"handle": username}, timeout=30.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            return data.get("result", [])
    except Exception as e:
        print(f"Error fetching Codeforces submissions for {username}: {e}")
    return []

async def fetch_codeforces_contest(client: httpx.AsyncClient, contest_id: int, username: str) -> Dict[str, Any]:
    """Fetch user's result in a specific contest"""
    try:
        r = await client.get(f"{CODEFORCES_API_BASE}/contest.standings", params={"contestId": contest_id, "handles": username, "includeTeamParticipants": "false"}, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK" and data.get("result", {}).get("rows"):
            return data["result"]["rows"][0]
    except Exception as e:
        print(f"Error fetching Codeforces contest {contest_id}: {e}")
    return {}

async def fetch_codeforces_data(client: httpx.AsyncClient, student: Dict[str, Any], semaphore: asyncio.Semaphore):
    username = student.get("codeforces_id", "").strip()
    if not username:
        print(f"Empty Codeforces ID for student {student.get('roll_no')}")
        return

    async with semaphore:
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(2)  # Rate limiting - 2s between requests

                user_info = await fetch_codeforces_user_info(client, username)
                if not user_info:
                    print(f"User {username} not found on Codeforces")
                    return
                
                if not user_info.get("rating"):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"⏳ Rate limited for {username}, retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        print(f"❌ Rate limit exceeded for {username}")
                        return

                rating_history = await fetch_codeforces_rating(client, username)
                submissions = await fetch_codeforces_submissions(client, username)
                break  # Success
                
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⏳ Rate limited for {username}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    print(f"Error fetching Codeforces data for {username}: {str(e)}")
                    return

                current_rating = user_info.get("rating")
                max_rating = user_info.get("maxRating")
                rank = user_info.get("rank")
                contribution = user_info.get("contribution", 0)

                easy_solved = set()
                medium_solved = set()
                hard_solved = set()

                for sub in submissions:
                    if sub.get("verdict") == "OK":
                        prob = sub.get("problem", {})
                        idx = prob.get("index", "")
                        if idx.startswith("1"):
                            easy_solved.add(prob.get("name"))
                        elif idx.startswith("2"):
                            medium_solved.add(prob.get("name"))
                        elif idx.startswith("3"):
                            hard_solved.add(prob.get("name"))

                total_contests = len(rating_history)
                contest_name = None
                rating_changes = []
                
                if total_contests >= 1:
                    last_contest = rating_history[-1]
                    contest_name = last_contest.get("contestName", None)
                    
                    last_five = rating_history[-5:] if total_contests >= 5 else rating_history
                    rating_changes = [
                        {
                            "contest": c.get("contestName", ""),
                            "rating": c.get("newRating", 0),
                            "change": c.get("newRating", 0) - c.get("oldRating", 0) if c.get("oldRating") else 0
                        }
                        for c in last_five
                    ]

                supabase.table("codeforces_stats").upsert({
                    "roll_no": student["roll_no"],
                    "current_rating": current_rating,
                    "max_rating": max_rating,
                    "rank": rank,
                    "contribution": contribution,
                    "problems_solved": len(easy_solved) + len(medium_solved) + len(hard_solved),
                    "easy_solved": len(easy_solved),
                    "medium_solved": len(medium_solved),
                    "hard_solved": len(hard_solved),
                    "total_contests": total_contests,
                    "contest_name": contest_name,
                    "rating_changes": rating_changes,
                    "updated_at": "now()"
                }).execute()

                print(f"✅ Updated Codeforces: {student.get('roll_no')} - Rating: {current_rating}")
                break  # Success, exit retry loop
                
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ Error for {username}, retrying in {delay}s: {str(e)}")
                    await asyncio.sleep(delay)
                else:
                    print(f"❌ Error fetching Codeforces data for {username}: {str(e)}")

@router.post("/sync/codeforces")
async def sync_codeforces():
    try:
        response = supabase.rpc("get_students_with_codeforces",{}).execute()
        students = response.data

        if not students:
            return {"message": "No students with Codeforces IDs found"}

        semaphore = asyncio.Semaphore(2)  # Lower concurrency for CF API limits

        async with httpx.AsyncClient(timeout=40.0) as client:
            tasks = [fetch_codeforces_data(client, student, semaphore) for student in students]
            await asyncio.gather(*tasks)

        return {"message": f"Codeforces sync completed for {len(students)} students"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sync failed: {str(e)}")

# ==========================================
# 🔄 CodeChef Sync
# ==========================================
CODECHEF_API_URL = "https://code-chef-bot.onrender.com/handle"

async def fetch_codechef_data(client: httpx.AsyncClient, student: Dict[str, Any], semaphore: asyncio.Semaphore):
    username = student.get("codechef_id", "").strip()
    if not username:
        print(f"Empty CodeChef ID for student {student.get('roll_no')}")
        return

    async with semaphore:
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(1.5)  # Rate limit delay between requests

                r = await client.get(f"{CODECHEF_API_URL}/{username}", timeout=30.0)
                
                if r.status_code == 404:
                    print(f"⚠️ CodeChef user not found: {username}")
                    return
                
                if r.status_code == 429:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"⏳ Rate limited, retrying in {delay}s... ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        print(f"❌ Rate limit exceeded for {username}, skipping")
                        return
                
                r.raise_for_status()
                data = r.json()
                
                if not data or not data.get("currentRating"):
                    print(f"⚠️ No rating data for CodeChef user: {username}")
                    return

                current_rating = data.get("currentRating")
                max_rating = data.get("maxRating")
                
                stars_raw = data.get("stars", "0")
                try:
                    stars = int(stars_raw) if isinstance(stars_raw, int) else int(stars_raw.replace("★", "").strip())
                except (ValueError, AttributeError):
                    stars = 0
                
                global_rank_raw = data.get("globalRank")
                try:
                    global_rank = int(global_rank_raw) if global_rank_raw else None
                except (ValueError, TypeError):
                    global_rank = None
                    
                country_rank_raw = data.get("countryRank")
                try:
                    country_rank = int(country_rank_raw) if country_rank_raw else None
                except (ValueError, TypeError):
                    country_rank = None
                
                total_contests = data.get("contestCount", 0)
                problems_solved = data.get("problemCount", 0)

                rating_data = data.get("ratingData", [])
                last_five = rating_data[-5:] if len(rating_data) > 5 else rating_data
                rating_changes = [{"contest": r.get("contestCode", ""), "rating": r.get("rating", 0), "change": r.get("change", 0)} for r in last_five]
                
                contest_name = None
                contest_rank = None
                if rating_data:
                    last_rating = rating_data[-1]
                    contest_name = last_rating.get("contestCode", None)
                    contest_rank = last_rating.get("rank", None)

                supabase.table("codechef_stats").upsert({
                    "roll_no": student["roll_no"],
                    "current_rating": current_rating,
                    "max_rating": max_rating,
                    "stars": stars,
                    "global_rank": global_rank,
                    "country_rank": country_rank,
                    "total_contests": total_contests,
                    "problems_solved": problems_solved,
                    "contest_name": contest_name,
                    "contest_rank": contest_rank,
                    "rating_changes": rating_changes,
                    "updated_at": "now()"
                }).execute()

                print(f"✅ Updated CodeChef: {student.get('roll_no')} - Rating: {current_rating}")
                break  # Success, exit retry loop
                
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ Error for {username}, retrying in {delay}s: {str(e)}")
                    await asyncio.sleep(delay)
                else:
                    print(f"❌ Error fetching CodeChef data for {username}: {str(e)}")

@router.post("/sync/codechef")
async def sync_codechef():
    try:
        response = supabase.rpc("get_students_with_codechef",{}).execute()
        students = response.data

        if not students:
            return {"message": "No students with CodeChef IDs found"}

        semaphore = asyncio.Semaphore(2)  # Reduced to 2 concurrent requests

        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [fetch_codechef_data(client, student, semaphore) for student in students]
            await asyncio.gather(*tasks)

        return {"message": f"CodeChef sync completed for {len(students)} students"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sync failed: {str(e)}")
