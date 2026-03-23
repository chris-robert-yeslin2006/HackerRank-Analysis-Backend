import httpx
import asyncio
import logging
import time
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

sys.path.insert(0, '/Users/yeslin-parker/project/HackerRank-Analysis-Backend')

from worker.celery_app import celery_app
from database import supabase
from utils.lock import release_lock
from services.job_service import (
    create_job, start_job, update_job_progress,
    complete_job, fail_job, build_error_dict
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHUNK_SIZE = 50
SEMAPHORE_LIMIT = 25
CODEFORCES_API_BASE = "https://codeforces.com/api"
CF_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def retry_with_backoff(func, *args, max_retries=3, base_delay=1.0, **kwargs):
    """Retry a function with exponential backoff for network/5xx errors."""
    retryable_exceptions = (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: {str(e)}")
                time.sleep(delay)
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
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def fetch_codeforces_user_info_sync(username: str) -> Dict[str, Any]:
    def api_call():
        r = httpx.get(
            f"{CODEFORCES_API_BASE}/user.info",
            params={"handles": username},
            headers=CF_HEADERS,
            timeout=20.0
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK" and data.get("result"):
            return data["result"][0]
        return {}
    
    try:
        return retry_with_backoff(api_call, max_retries=3)
    except Exception as e:
        logger.error(f"Error fetching Codeforces user info for {username}: {e}")
        return {}


def fetch_codeforces_rating_sync(username: str) -> List[Dict[str, Any]]:
    def api_call():
        r = httpx.get(
            f"{CODEFORCES_API_BASE}/user.rating",
            params={"handle": username},
            headers=CF_HEADERS,
            timeout=20.0
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            return data.get("result", [])
        return []
    
    try:
        return retry_with_backoff(api_call, max_retries=3)
    except Exception as e:
        logger.error(f"Error fetching Codeforces rating for {username}: {e}")
        return []


def fetch_recent_contests_sync() -> List[Dict[str, Any]]:
    try:
        r = httpx.get(
            f"{CODEFORCES_API_BASE}/contest.list",
            headers=CF_HEADERS,
            timeout=20.0
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            contests = data.get("result", [])
            current_time = int(time.time())
            finished_contests = [c for c in contests if c.get("startTimeSeconds", 0) < current_time]
            recent_contests = [
                {"id": c.get("id"), "name": c.get("name"), "startTime": c.get("startTimeSeconds")}
                for c in finished_contests[:5]
            ]
            logger.info(f"Fetched {len(recent_contests)} recent contests")
            return recent_contests
    except Exception as e:
        logger.error(f"Error fetching recent contests: {e}")
    return []


def process_student_codeforces(
    student: Dict[str, Any],
    recent_contests: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Process a single student's Codeforces data."""
    username = student.get("codeforces_id", "").strip()
    roll_no = student.get("roll_no")
    
    if not username:
        logger.info(f"Empty Codeforces ID for student {roll_no}")
        return {"status": "skipped", "reason": "empty_id"}
    
    try:
        time.sleep(0.3)
        
        user_info = fetch_codeforces_user_info_sync(username)
        if not user_info:
            logger.warning(f"Could not fetch Codeforces data for {username}")
            return {"status": "failed", "reason": "user_not_found"}
        
        rating_history = fetch_codeforces_rating_sync(username)
        
        current_rating = user_info.get("rating")
        max_rating = user_info.get("maxRating")
        rank = user_info.get("rank")
        contribution = user_info.get("contribution", 0)
        
        total_contests = len(rating_history)
        
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
        
        upsert_data = {
            "roll_no": roll_no,
            "current_rating": current_rating,
            "max_rating": max_rating,
            "rank": rank,
            "contribution": contribution,
            "total_contests": total_contests,
            "updated_at": "now()"
        }
        
        if attended_contests:
            upsert_data["contest_name"] = attended_contests[0]["contest"]
            upsert_data["rating_changes"] = attended_contests
        
        supabase.table("codeforces_stats").upsert(upsert_data).execute()
        
        logger.info(f"Updated Codeforces: {roll_no} - Rating: {current_rating}")
        return {"status": "success", "rating": current_rating}
         
    except Exception as e:
        logger.error(f"Error processing Codeforces data for {username}: {str(e)}")
        return {"status": "failed", "reason": str(e)}


@celery_app.task(bind=True, name="worker.tasks.sync_codeforces")
def sync_codeforces_task(self) -> Dict[str, Any]:
    """
    Celery task for syncing Codeforces data.
    Processes students in batches with progress tracking.
    Lock is released in finally block for safety.
    """
    logger.info("=== CELERY: Starting Codeforces sync task ===")
    task_id = self.request.id
    
    job_id = None
    try:
        response = supabase.rpc("get_students_with_codeforces", {}).execute()
        students = response.data or []
        
        if not students:
            logger.info("No students with Codeforces IDs found")
            return {"status": "success", "message": "No students with Codeforces IDs found"}
        
        total = len(students)
        job_id = create_job("codeforces", total, triggered_by="api")
        
        if job_id:
            start_job(job_id)
            update_job_progress(job_id, 0, total)
        
        recent_contests = fetch_recent_contests_sync()
        logger.info(f"Processing {total} students in batches of {CHUNK_SIZE}")
        
        batches = chunk_list(students, CHUNK_SIZE)
        success_count = 0
        failed_count = 0
        
        for batch_num, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {batch_num}/{len(batches)} ({len(batch)} students)")
            
            for student in batch:
                result = process_student_codeforces(student, recent_contests)
                if result["status"] == "success":
                    success_count += 1
                elif result["status"] == "failed":
                    failed_count += 1
            
            processed = batch_num * len(batch)
            if job_id:
                update_job_progress(job_id, min(processed, total), total, success_count, failed_count)
            time.sleep(1)
        
        logger.info(f"=== CELERY: Codeforces sync completed. Success: {success_count}, Failed: {failed_count} ===")
        
        if job_id:
            complete_job(job_id, success_count, failed_count)
        
        return {
            "status": "success",
            "total": total,
            "success": success_count,
            "failed": failed_count
        }
        
    except Exception as e:
        logger.error(f"Codeforces sync failed: {str(e)}")
        
        if job_id:
            error = build_error_dict("task_error", reason=str(e))
            fail_job(job_id, error)
        
        return {"status": "error", "error": str(e)}
    
    finally:
        logger.info("=== CELERY: Releasing Codeforces sync lock ===")
        release_lock("codeforces")


def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a Celery task."""
    from worker.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    
    return {
        "task_id": task_id,
        "status": result.state,
        "result": result.result if result.ready() else None,
        "info": str(result.info) if result.info else None
    }
