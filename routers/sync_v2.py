from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Union

from worker.tasks import sync_codeforces_task, get_task_status
from utils.lock import acquire_lock
from services.job_service import (
    get_jobs, get_job, get_stuck_jobs,
    check_lock_db_consistency, build_job_response, get_retry_job_info
)
from utils.logger import get_logger, log_retry_triggered

logger = get_logger("routers.sync_v2")

router = APIRouter(prefix="/v2/sync", tags=["Sync V2"])


class TaskResponse(BaseModel):
    task_id: str
    message: str
    status_url: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Union[dict, None] = None
    info: Union[str, None] = None


class JobsResponse(BaseModel):
    jobs: List[dict]
    total: int


@router.post("/codeforces")
def trigger_codeforces_sync():
    logger.info(
        "Sync request received",
        extra={"event": "sync_request", "platform": "codeforces", "path": "/v2/sync/codeforces"}
    )
    
    if not acquire_lock("codeforces"):
        return JSONResponse(
            status_code=409,
            content={"message": "Sync already running", "status": "locked"}
        )
    
    try:
        result = sync_codeforces_task.delay()
        
        logger.info(
            "Sync task queued",
            extra={"event": "task_queued", "platform": "codeforces", "task_id": result.id}
        )
        
        return {
            "task_id": result.id,
            "message": "Codeforces sync task queued successfully",
            "status_url": f"/v2/sync/status/{result.id}"
        }
    except Exception as e:
        from utils.lock import release_lock
        release_lock("codeforces")
        logger.exception(
            "Failed to queue sync task",
            extra={"event": "task_queue_error", "platform": "codeforces"}
        )
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_task_status_endpoint(task_id: str):
    """Get the status of a sync task by its ID."""
    try:
        status = get_task_status(task_id)
        return TaskStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching task status: {str(e)}")


@router.get("/jobs")
def get_recent_jobs(
    limit: int = Query(default=10, ge=1, le=100),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    platform: Optional[str] = Query(default=None, description="Filter by platform")
):
    """
    Get recent sync jobs with optional filters.
    
    - **limit**: Number of jobs to return (1-100, default 10)
    - **status**: Filter by status ('pending', 'running', 'success', 'failed')
    - **platform**: Filter by platform ('codeforces', 'leetcode', 'codechef')
    """
    try:
        jobs = get_jobs(limit=limit, status=status, platform=platform)
        enhanced_jobs = [build_job_response(job) for job in jobs]
        
        return {
            "jobs": enhanced_jobs,
            "total": len(enhanced_jobs)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching jobs: {str(e)}")


@router.get("/jobs/{job_id}")
def get_single_job(job_id: str):
    """Get a single job by ID with computed fields."""
    try:
        job = get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return build_job_response(job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching job: {str(e)}")


@router.get("/jobs/stuck/list")
def get_stuck_jobs_endpoint():
    """Get jobs that have been running for more than 15 minutes."""
    try:
        jobs = get_stuck_jobs()
        return {
            "stuck_jobs": jobs,
            "count": len(jobs),
            "message": f"Found {len(jobs)} stuck job(s)"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error checking stuck jobs: {str(e)}")


@router.get("/consistency-check")
def check_consistency():
    """
    Check for inconsistencies between Redis locks and database running jobs.
    Useful for debugging stuck jobs or orphaned locks.
    """
    try:
        result = check_lock_db_consistency()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error checking consistency: {str(e)}")


@router.post("/codeforces/retry/{job_id}")
def retry_failed_students(job_id: str):
    logger.info(
        "Retry request received",
        extra={"event": "retry_request", "original_job_id": job_id, "platform": "codeforces"}
    )
    
    try:
        job_info = get_retry_job_info(job_id)
        
        if not job_info:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        failed_students = job_info.get("failed_students", [])
        
        if not failed_students:
            logger.info(
                "No failed students to retry",
                extra={"event": "retry_skipped", "original_job_id": job_id, "failed_count": 0}
            )
            return {
                "message": "No failed students to retry",
                "job_id": job_id,
                "failed_count": 0
            }
        
        if not acquire_lock("codeforces"):
            return JSONResponse(
                status_code=409,
                content={"message": "Sync already running", "status": "locked"}
            )
        
        try:
            result = sync_codeforces_task.delay(failed_students)
            
            log_retry_triggered(logger, job_id, result.id, "codeforces", len(failed_students))
            
            return {
                "task_id": result.id,
                "message": f"Retry queued for {len(failed_students)} failed students",
                "status_url": f"/v2/sync/status/{result.id}",
                "original_job_id": job_id,
                "students_to_retry": len(failed_students)
            }
        except Exception as e:
            from utils.lock import release_lock
            release_lock("codeforces")
            logger.exception(
                "Failed to queue retry task",
                extra={"event": "retry_queue_error", "original_job_id": job_id}
            )
            raise HTTPException(status_code=500, detail=f"Failed to queue retry task: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error retrying job: {str(e)}")
