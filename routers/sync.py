import httpx
import asyncio
import re
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from database import supabase
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sync"])

LEETCODE_URL = "https://leetcode.com/graphql"


def update_job_progress(job_id: str, processed: int, total: int):
    try:
        supabase.table("sync_jobs").update({
            "processed_students": processed,
            "total_students": total
        }).eq("id", job_id).execute()
    except Exception as e:
        logger.error(f"Failed to update job progress: {e}")


async def retry_with_backoff(func, *args, max_retries=3, base_delay=1.0, **kwargs):
    """Retry a function with exponential backoff for network/5xx errors."""
    retryable_exceptions = (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: {str(e)}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Retry failed after {max_retries} attempts: {str(e)}")
                raise
        except Exception as e:
            if isinstance(e, httpx.HTTPStatusError):
                if e.response.status_code == 404:
                    raise
            logger.error(f"Non-retryable error: {str(e)}")
            raise


def chunk_list(lst: list, chunk_size: int) -> list:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def clean_leetcode_username(raw_id: str) -> str:
    if not raw_id or not isinstance(raw_id, str):
        return ""
    
    raw_id = raw_id.strip().rstrip('/')
    if '/' in raw_id:
        raw_id = raw_id.split('/')[-1]
    
    raw_id = raw_id.replace('(new)', '')
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
        logger.info(f"Empty or invalid LeetCode ID for student {student.get('roll_no')}")
        return

    async with semaphore:
        try:
            await asyncio.sleep(0.5) 

            async def leetcode_api_call():
                variables = {"username": username}
                headers = {
                    'Content-Type': 'application/json',
                    'Referer': f'https://leetcode.com/u/{username}/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                r = await client.post(
                    LEETCODE_URL,
                    json={"query": QUERY, "variables": variables},
                    headers=headers,
                    timeout=20.0
                )
                if r.status_code == 429:
                    raise httpx.HTTPStatusError("Rate limited", request=r.request, response=r)
                r.raise_for_status()
                return r.json()

            res_data = await retry_with_backoff(leetcode_api_call, max_retries=3)
            
            if "data" not in res_data or not res_data["data"].get("matchedUser"):
                logger.info(f"User {username} not found on LeetCode.")
                return

            data = res_data["data"]

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

            existing_resp = supabase.table("leetcode_stats").select("easy_solved, medium_solved, hard_solved, easy_today, medium_today, hard_today, updated_at").eq("roll_no", student["roll_no"]).execute()
            
            easy_today = 0
            medium_today = 0
            hard_today = 0
            
            if existing_resp.data:
                old_stats = existing_resp.data[0]
                last_updated_str = old_stats.get("updated_at")
                
                delta_easy = max(0, easy_solved - old_stats.get("easy_solved", 0))
                delta_medium = max(0, medium_solved - old_stats.get("medium_solved", 0))
                delta_hard = max(0, hard_solved - old_stats.get("hard_solved", 0))

                now_utc = datetime.now(timezone.utc)
                is_same_day = False
                if last_updated_str:
                    last_updated_dt = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
                    if last_updated_dt.date() == now_utc.date():
                        is_same_day = True
                
                if is_same_day:
                    easy_today = old_stats.get("easy_today", 0) + delta_easy
                    medium_today = old_stats.get("medium_today", 0) + delta_medium
                    hard_today = old_stats.get("hard_today", 0) + delta_hard
                else:
                    easy_today = delta_easy
                    medium_today = delta_medium
                    hard_today = delta_hard
            else:
                easy_today = easy_solved
                medium_today = medium_solved
                hard_today = hard_solved
            
            rating = None
            if data["userContestRanking"]:
                rating = int(data["userContestRanking"]["rating"])

            weekly_rank = None
            weekly_solved = None
            biweekly_rank = None
            biweekly_solved = None

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
            logger.error(f"HTTP error for {username}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching data for {username}: {str(e)}")


async def sync_leetcode_service(job_id: Optional[str] = None) -> Dict[str, Any]:
    logger.info("Starting LeetCode sync...")
    BATCH_SIZE = 50
    
    try:
        response = supabase.rpc("get_students_with_leetcode",{}).execute()
        students = response.data

        if not students:
            return {"message": "No students with LeetCode IDs found", "status": "success"}

        total = len(students)
        if job_id:
            update_job_progress(job_id, 0, total)

        batches = chunk_list(students, BATCH_SIZE)
        logger.info(f"Processing {len(batches)} batches of up to {BATCH_SIZE} students each")
        
        processed_count = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for batch_num, batch in enumerate(batches, 1):
                logger.info(f"Processing batch {batch_num}/{len(batches)} ({len(batch)} students)")
                semaphore = asyncio.Semaphore(5)
                
                tasks = [fetch_user(client, student, semaphore) for student in batch]
                await asyncio.gather(*tasks)
                
                processed_count += len(batch)
                if job_id:
                    update_job_progress(job_id, processed_count, total)
                
                await asyncio.sleep(1)

        logger.info(f"LeetCode sync completed for {total} students")
        return {"message": f"LeetCode sync completed for {total} students", "status": "success"}
    except Exception as e:
        logger.error(f"LeetCode sync failed: {str(e)}")
        return {"message": f"LeetCode sync failed: {str(e)}", "status": "error", "error": str(e)}


@router.post("/sync/leetcode")
async def sync_leetcode():
    return await sync_leetcode_service()


CODEFORCES_API_BASE = "https://codeforces.com/api"
CF_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

async def fetch_codeforces_user_info(client: httpx.AsyncClient, username: str) -> Dict[str, Any]:
    async def api_call():
        r = await client.get(f"{CODEFORCES_API_BASE}/user.info", params={"handles": username}, headers=CF_HEADERS, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK" and data.get("result"):
            return data["result"][0]
        return {}
    
    try:
        return await retry_with_backoff(api_call, max_retries=3)
    except Exception as e:
        logger.error(f"Error fetching Codeforces user info for {username}: {e}")
        return {}

async def fetch_codeforces_rating(client: httpx.AsyncClient, username: str) -> List[Dict[str, Any]]:
    async def api_call():
        r = await client.get(f"{CODEFORCES_API_BASE}/user.rating", params={"handle": username}, headers=CF_HEADERS, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            return data.get("result", [])
        return []
    
    try:
        return await retry_with_backoff(api_call, max_retries=3)
    except Exception as e:
        logger.error(f"Error fetching Codeforces rating for {username}: {e}")
        return []

async def fetch_codeforces_submissions(client: httpx.AsyncClient, username: str) -> List[Dict[str, Any]]:
    try:
        r = await client.get(f"{CODEFORCES_API_BASE}/user.status", params={"handle": username}, headers=CF_HEADERS, timeout=30.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            return data.get("result", [])
    except Exception as e:
        logger.error(f"Error fetching Codeforces submissions for {username}: {e}")
    return []

async def fetch_codeforces_contest(client: httpx.AsyncClient, contest_id: int, username: str) -> Dict[str, Any]:
    try:
        r = await client.get(f"{CODEFORCES_API_BASE}/contest.standings", params={"contestId": contest_id, "handles": username, "includeTeamParticipants": "false"}, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK" and data.get("result", {}).get("rows"):
            return data["result"]["rows"][0]
    except Exception as e:
        logger.error(f"Error fetching Codeforces contest {contest_id}: {e}")
    return {}

async def fetch_recent_contests(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    try:
        r = await client.get(f"{CODEFORCES_API_BASE}/contest.list", params={"from": 1, "count": 5}, headers=CF_HEADERS, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            contests = data.get("result", [])
            return [{"id": c.get("id"), "name": c.get("name")} for c in reversed(contests)]
    except Exception as e:
        logger.error(f"Error fetching recent contests: {e}")
    return []

_recent_contests_cache = []

async def get_recent_contests(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    global _recent_contests_cache
    if not _recent_contests_cache:
        _recent_contests_cache = await fetch_recent_contests(client)
    return _recent_contests_cache

async def fetch_codeforces_data(client: httpx.AsyncClient, student: Dict[str, Any], semaphore: asyncio.Semaphore):
    username = student.get("codeforces_id", "").strip()
    if not username:
        logger.info(f"Empty Codeforces ID for student {student.get('roll_no')}")
        return

    async with semaphore:
        try:
            await asyncio.sleep(0.3)

            user_info = await fetch_codeforces_user_info(client, username)
            if not user_info:
                logger.warning(f"Could not fetch Codeforces data for {username}")
                return

            rating_history = await fetch_codeforces_rating(client, username)

            current_rating = user_info.get("rating")
            max_rating = user_info.get("maxRating")
            rank = user_info.get("rank")
            contribution = user_info.get("contribution", 0)

            total_contests = len(rating_history)
            
            recent_contests = await get_recent_contests(client)
            attended_contests = []
            
            for contest in recent_contests:
                for rating in rating_history:
                    if rating.get("contestName") == contest["name"]:
                        attended_contests.append({
                            "contest": contest["name"],
                            "rating": rating.get("newRating", 0),
                            "change": rating.get("newRating", 0) - rating.get("oldRating", 0) if rating.get("oldRating") else 0,
                            "rank": rating.get("rank", 0)
                        })
                        break

            contest_name = attended_contests[0]["contest"] if attended_contests else None

            supabase.table("codeforces_stats").upsert({
                "roll_no": student["roll_no"],
                "current_rating": current_rating,
                "max_rating": max_rating,
                "rank": rank,
                "contribution": contribution,
                "total_contests": total_contests,
                "contest_name": contest_name,
                "rating_changes": attended_contests,
                "updated_at": "now()"
            }).execute()

            logger.info(f"Updated Codeforces: {student.get('roll_no')} - Rating: {current_rating}")

        except Exception as e:
            logger.error(f"Error fetching Codeforces data for {username}: {str(e)}")


async def sync_codeforces_service(job_id: Optional[str] = None) -> Dict[str, Any]:
    logger.info("Starting Codeforces sync...")
    BATCH_SIZE = 50
    
    try:
        global _recent_contests_cache
        _recent_contests_cache = []
        
        response = supabase.rpc("get_students_with_codeforces",{}).execute()
        students = response.data

        if not students:
            return {"message": "No students with Codeforces IDs found", "status": "success"}

        total = len(students)
        if job_id:
            update_job_progress(job_id, 0, total)

        batches = chunk_list(students, BATCH_SIZE)
        logger.info(f"Processing {len(batches)} batches of up to {BATCH_SIZE} students each")
        
        processed_count = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for batch_num, batch in enumerate(batches, 1):
                logger.info(f"Processing batch {batch_num}/{len(batches)} ({len(batch)} students)")
                semaphore = asyncio.Semaphore(25)
                
                tasks = [fetch_codeforces_data(client, student, semaphore) for student in batch]
                await asyncio.gather(*tasks)
                
                processed_count += len(batch)
                if job_id:
                    update_job_progress(job_id, processed_count, total)
                
                await asyncio.sleep(1)

        logger.info(f"Codeforces sync completed for {total} students")
        return {"message": f"Codeforces sync completed for {total} students", "status": "success"}
    except Exception as e:
        logger.error(f"Codeforces sync failed: {str(e)}")
        return {"message": f"Codeforces sync failed: {str(e)}", "status": "error", "error": str(e)}


@router.post("/sync/codeforces")
async def sync_codeforces():
    return await sync_codeforces_service()


CODECHEF_API_URL = "https://code-chef-bot.onrender.com/handle"

async def fetch_codechef_data(client: httpx.AsyncClient, student: Dict[str, Any], semaphore: asyncio.Semaphore):
    username = student.get("codechef_id", "").strip()
    if not username:
        logger.info(f"Empty CodeChef ID for student {student.get('roll_no')}")
        return

    async with semaphore:
        try:
            await asyncio.sleep(0.5)

            async def codechef_api_call():
                r = await client.get(f"{CODECHEF_API_URL}/{username}", timeout=30.0)
                if r.status_code == 404:
                    raise httpx.HTTPStatusError("User not found", request=r.request, response=r)
                if r.status_code == 429:
                    raise httpx.HTTPStatusError("Rate limited", request=r.request, response=r)
                r.raise_for_status()
                return r.json()

            data = await retry_with_backoff(codechef_api_call, max_retries=5, base_delay=2.0)
            
            if not data or not data.get("currentRating"):
                logger.warning(f"No rating data for CodeChef user: {username}")
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

            logger.info(f"Updated CodeChef: {student.get('roll_no')} - Rating: {current_rating}")
                
        except Exception as e:
            logger.error(f"Error fetching CodeChef data for {username}: {str(e)}")


async def sync_codechef_service(job_id: Optional[str] = None) -> Dict[str, Any]:
    logger.info("Starting CodeChef sync...")
    BATCH_SIZE = 50
    
    try:
        response = supabase.rpc("get_students_with_codechef",{}).execute()
        students = response.data

        if not students:
            return {"message": "No students with CodeChef IDs found", "status": "success"}

        total = len(students)
        if job_id:
            update_job_progress(job_id, 0, total)

        batches = chunk_list(students, BATCH_SIZE)
        logger.info(f"Processing {len(batches)} batches of up to {BATCH_SIZE} students each")
        
        processed_count = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for batch_num, batch in enumerate(batches, 1):
                logger.info(f"Processing batch {batch_num}/{len(batches)} ({len(batch)} students)")
                semaphore = asyncio.Semaphore(5)
                
                tasks = [fetch_codechef_data(client, student, semaphore) for student in batch]
                await asyncio.gather(*tasks)
                
                processed_count += len(batch)
                if job_id:
                    update_job_progress(job_id, processed_count, total)
                
                await asyncio.sleep(5)

        logger.info(f"CodeChef sync completed for {total} students")
        return {"message": f"CodeChef sync completed for {total} students", "status": "success"}
    except Exception as e:
        logger.error(f"CodeChef sync failed: {str(e)}")
        return {"message": f"CodeChef sync failed: {str(e)}", "status": "error", "error": str(e)}
        return {"message": f"CodeChef sync failed: {str(e)}", "status": "error", "error": str(e)}


@router.post("/sync/codechef")
async def sync_codechef():
    return await sync_codechef_service()


async def run_full_sync():
    logger.info("=== FULL SYNC STARTED ===")
    
    platforms = ["codeforces", "codechef", "leetcode"]
    
    for platform in platforms:
        job_id = None
        try:
            job_response = supabase.table("sync_jobs").insert({
                "platform": platform,
                "status": "running"
            }).execute()
            
            if job_response.data:
                job_id = job_response.data[0]["id"]
                logger.info(f"Created job {job_id} for {platform}")
            
            if platform == "codeforces":
                result = await sync_codeforces_service(job_id)
            elif platform == "codechef":
                result = await sync_codechef_service(job_id)
            elif platform == "leetcode":
                result = await sync_leetcode_service(job_id)
            
            logger.info(f"{platform.capitalize()} sync: {result.get('status')}")
            
            supabase.table("sync_jobs").update({
                "status": "success",
                "completed_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", job_id).execute()
            
        except Exception as e:
            logger.error(f"{platform.capitalize()} sync error: {str(e)}")
            if job_id:
                supabase.table("sync_jobs").update({
                    "status": "failed",
                    "error_message": str(e),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", job_id).execute()
    
    logger.info("=== FULL SYNC COMPLETED ===")


@router.get("/sync/jobs")
async def get_sync_jobs():
    try:
        response = supabase.table("sync_jobs").select("*").order("started_at", desc=True).limit(20).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching sync jobs: {str(e)}")


@router.post("/sync/all")
@router.get("/sync/all")
async def sync_all(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_full_sync)
    return {"message": "Sync started in background"}
