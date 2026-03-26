import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from supabase import Client as SupabaseClient

from database import supabase
from utils.lock import is_locked

logger = logging.getLogger(__name__)

STUCK_THRESHOLD_MINUTES = 15


def create_job(platform: str, total_students: int = 0, triggered_by: str = "api") -> Optional[str]:
    """
    Create a new sync job record.
    
    Args:
        platform: Platform name (e.g., 'codeforces', 'leetcode')
        total_students: Total number of students to process
        triggered_by: What triggered the job ('api', 'cron', 'admin')
    
    Returns:
        Job ID if created, None otherwise
    """
    try:
        response = supabase.table("sync_jobs").insert({
            "platform": platform,
            "status": "pending",
            "total_students": total_students,
            "processed_students": 0,
            "success_count": 0,
            "failed_count": 0,
            "triggered_by": triggered_by
        }).execute()
        
        if response.data:
            job_id = response.data[0]["id"]
            logger.info(f"Created job {job_id} for {platform}")
            return job_id
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
    return None


def start_job(job_id: str) -> bool:
    """Mark a job as running."""
    try:
        supabase.table("sync_jobs").update({
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", job_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to start job {job_id}: {e}")
        return False


def update_job_progress(
    job_id: str,
    processed: int,
    total: int,
    success: int = 0,
    failed: int = 0
) -> None:
    """Update job progress with granular counts."""
    try:
        supabase.table("sync_jobs").update({
            "processed_students": processed,
            "total_students": total,
            "success_count": success,
            "failed_count": failed
        }).eq("id", job_id).execute()
    except Exception as e:
        logger.error(f"Failed to update job progress: {e}")


def complete_job(job_id: str, success: int = 0, failed: int = 0, failed_students: List[str] = None) -> bool:
    """Mark a job as successfully completed."""
    try:
        update_data = {
            "status": "success",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "processed_students": success + failed,
            "success_count": success,
            "failed_count": failed
        }
        if failed_students is not None:
            update_data["failed_students"] = failed_students
        
        supabase.table("sync_jobs").update(update_data).eq("id", job_id).execute()
        logger.info(f"Job {job_id} completed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to complete job {job_id}: {e}")
        return False


def fail_job(job_id: str, error: Dict[str, Any]) -> bool:
    """Mark a job as failed with structured error."""
    try:
        error_json = json.dumps(error)
        supabase.table("sync_jobs").update({
            "status": "failed",
            "error_message": error_json,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", job_id).execute()
        logger.info(f"Job {job_id} marked as failed")
        return True
    except Exception as e:
        logger.error(f"Failed to fail job {job_id}: {e}")
        return False


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a single job by ID."""
    try:
        response = supabase.table("sync_jobs").select("*").eq("id", job_id).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
    return None


def get_jobs(
    limit: int = 10,
    status: Optional[str] = None,
    platform: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get recent jobs with optional filters.
    
    Args:
        limit: Maximum number of jobs to return
        status: Filter by status ('pending', 'running', 'success', 'failed')
        platform: Filter by platform ('codeforces', 'leetcode', etc.)
    
    Returns:
        List of jobs ordered by started_at DESC
    """
    try:
        query = supabase.table("sync_jobs").select("*").order("started_at", desc=True).limit(limit)
        
        if status:
            query = query.eq("status", status)
        if platform:
            query = query.eq("platform", platform)
        
        response = query.execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Failed to get jobs: {e}")
        return []


def get_stuck_jobs() -> List[Dict[str, Any]]:
    """
    Detect jobs that are stuck (running for more than STUCK_THRESHOLD_MINUTES).
    
    Returns:
        List of stuck jobs
    """
    try:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
        threshold_str = threshold.isoformat()
        
        response = supabase.table("sync_jobs").select("*").eq("status", "running").lt("started_at", threshold_str).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Failed to get stuck jobs: {e}")
        return []


def check_lock_db_consistency() -> Dict[str, Any]:
    """
    Check for inconsistencies between Redis locks and DB running jobs.
    
    Returns:
        Dict with inconsistencies found
    """
    platforms = ["codeforces", "leetcode", "codechef"]
    inconsistencies = []
    
    for platform in platforms:
        lock_exists = is_locked(platform)
        
        response = supabase.table("sync_jobs").select("id").eq("platform", platform).eq("status", "running").execute()
        running_job_exists = len(response.data) > 0
        
        if lock_exists and not running_job_exists:
            msg = f"WARNING: Redis lock exists for {platform} but no running job in DB"
            logger.warning(msg)
            inconsistencies.append({
                "type": "orphan_lock",
                "platform": platform,
                "message": msg
            })
        elif not lock_exists and running_job_exists:
            msg = f"WARNING: Running job in DB for {platform} but no Redis lock"
            logger.warning(msg)
            inconsistencies.append({
                "type": "missing_lock",
                "platform": platform,
                "message": msg
            })
    
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "inconsistencies": inconsistencies,
        "clean": len(inconsistencies) == 0
    }


def build_job_response(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build enhanced job response with computed fields.
    
    Args:
        job: Job record from database
    
    Returns:
        Enhanced job response with progress and metadata
    """
    total = job.get("total_students", 0)
    processed = job.get("processed_students", 0)
    
    progress = 0.0
    if total > 0:
        progress = round((processed / total) * 100, 2)
    
    error_message = job.get("error_message")
    if error_message:
        try:
            error_message = json.loads(error_message)
        except (json.JSONDecodeError, TypeError):
            pass
    
    failed_students = job.get("failed_students", [])
    if isinstance(failed_students, str):
        try:
            failed_students = json.loads(failed_students)
        except (json.JSONDecodeError, TypeError):
            failed_students = []
    
    return {
        "id": job.get("id"),
        "platform": job.get("platform"),
        "status": job.get("status"),
        "triggered_by": job.get("triggered_by", "api"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "total_students": total,
        "processed_students": processed,
        "success_count": job.get("success_count", 0),
        "failed_count": job.get("failed_count", 0),
        "failed_students": failed_students,
        "progress": progress,
        "error": error_message
    }


def build_error_dict(error_type: str, student: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
    """
    Build structured error dictionary.
    
    Args:
        error_type: Type of error ('api_error', 'timeout', 'validation_error', etc.)
        student: Student roll_no if applicable
        reason: Human-readable reason
    
    Returns:
        Structured error dict
    """
    error = {
        "type": error_type,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if student:
        error["student"] = student
    return error


def get_students_by_roll_nos(roll_nos: List[str]) -> List[Dict[str, Any]]:
    """
    Get students by list of roll numbers (for retry mode).
    
    Args:
        roll_nos: List of student roll numbers to fetch
    
    Returns:
        List of student records with platform IDs
    """
    try:
        response = supabase.table("student_platforms").select(
            "roll_no, codeforces_id, leetcode_id, codechef_id, students(name)"
        ).in_("roll_no", roll_nos).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Failed to get students by roll_nos: {e}")
        return []


def get_retry_job_info(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get job info for retry, including failed_students.
    
    Args:
        job_id: The job ID to get info for
    
    Returns:
        Job info dict with failed_students, or None if not found
    """
    job = get_job(job_id)
    if not job:
        return None
    
    failed_students = job.get("failed_students", [])
    if isinstance(failed_students, str):
        try:
            failed_students = json.loads(failed_students)
        except (json.JSONDecodeError, TypeError):
            failed_students = []
    
    return {
        "id": job["id"],
        "platform": job["platform"],
        "status": job["status"],
        "failed_count": job.get("failed_count", 0),
        "failed_students": failed_students
    }
