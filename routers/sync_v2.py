from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from worker.tasks import sync_codeforces_task, get_task_status
from database import supabase

router = APIRouter(prefix="/v2/sync", tags=["Sync V2"])


class TaskResponse(BaseModel):
    task_id: str
    message: str
    status_url: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    info: Optional[str] = None


@router.post("/codeforces", response_model=TaskResponse)
def trigger_codeforces_sync():
    """
    Trigger Codeforces sync as a background Celery task.
    Returns immediately with a task_id for status tracking.
    """
    try:
        result = sync_codeforces_task.delay()
        
        return TaskResponse(
            task_id=result.id,
            message="Codeforces sync task queued successfully",
            status_url=f"/v2/sync/status/{result.id}"
        )
    except Exception as e:
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
def get_recent_jobs():
    """Get recent sync jobs from the database."""
    try:
        response = supabase.table("sync_jobs").select("*").order("started_at", desc=True).limit(20).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching jobs: {str(e)}")
