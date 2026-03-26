import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from functools import wraps
import time


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "event"):
            log_data["event"] = record.event

        extra_fields = [
            "job_id", "platform", "roll_no", "task_id",
            "original_job_id", "students_count", "success_count",
            "failed_count", "username", "error_type", "duration_ms",
            "source", "key", "data_size", "cache_type"
        ]
        for field in extra_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if value is not None:
                    log_data[field] = value

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging() -> None:
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    logging.getLogger("app").setLevel(logging.INFO)
    
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(StructuredFormatter())
    
    app_logger = logging.getLogger("app")
    app_logger.addHandler(console)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


setup_logging()


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if name.startswith("app.") or name.startswith("utils.") or name.startswith("routers.") or name.startswith("services.") or name.startswith("worker."):
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)
    return logger


logger = logging.getLogger("app")


def timed_cache_operation(operation: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            
            log_func = logger.info if result is not None else logger.warning
            
            event = "cache_hit" if result is not None else "cache_miss"
            
            key = kwargs.get('key') if 'key' in kwargs else (args[1] if len(args) > 1 else None)
            
            log_func(
                f"Cache {operation}",
                extra={
                    "event": event if operation == "get" else "cache_set",
                    "operation": operation,
                    "source": "redis",
                    "duration_ms": round(duration_ms, 2),
                    "key": key
                }
            )
            
            return result
        return wrapper
    return decorator


def log_cache_hit(key: str, duration_ms: float, data_size: int = 0) -> None:
    logger.info(
        "Cache hit",
        extra={
            "event": "cache_hit",
            "source": "redis",
            "duration_ms": round(duration_ms, 2),
            "data_size": data_size
        }
    )


def log_cache_miss(key: str, duration_ms: float) -> None:
    logger.info(
        "Cache miss",
        extra={
            "event": "cache_miss",
            "source": "redis",
            "duration_ms": round(duration_ms, 2)
        }
    )


def log_cache_set(key: str, duration_ms: float) -> None:
    logger.info(
        "Cache set",
        extra={
            "event": "cache_set",
            "source": "redis",
            "duration_ms": round(duration_ms, 2)
        }
    )


def log_db_query(query_name: str, duration_ms: float, row_count: int = 0) -> None:
    logger.info(
        "DB query completed",
        extra={
            "event": "db_query",
            "query": query_name,
            "duration_ms": round(duration_ms, 2),
            "row_count": row_count
        }
    )


def log_sync_start(logger: logging.Logger, job_id: Optional[str], platform: str, students_count: int = 0) -> None:
    logger.info(
        "Sync started",
        extra={
            "event": "sync_started",
            "job_id": job_id,
            "platform": platform,
            "students_count": students_count
        }
    )


def log_sync_complete(
    logger: logging.Logger,
    job_id: str,
    platform: str,
    total: int,
    success_count: int,
    failed_count: int
) -> None:
    logger.info(
        "Sync completed",
        extra={
            "event": "sync_completed",
            "job_id": job_id,
            "platform": platform,
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count
        }
    )


def log_sync_failed(logger: logging.Logger, job_id: str, platform: str, error: str) -> None:
    logger.error(
        "Sync failed",
        extra={
            "event": "sync_failed",
            "job_id": job_id,
            "platform": platform,
            "error_type": "task_error"
        },
        exc_info=True
    )


def log_retry_triggered(
    logger: logging.Logger,
    original_job_id: str,
    new_job_id: str,
    platform: str,
    students_count: int
) -> None:
    logger.info(
        "Retry triggered",
        extra={
            "event": "retry_triggered",
            "original_job_id": original_job_id,
            "job_id": new_job_id,
            "platform": platform,
            "students_count": students_count
        }
    )


def log_lock_acquired(logger: logging.Logger, platform: str) -> None:
    logger.info(
        "Lock acquired",
        extra={
            "event": "lock_acquired",
            "platform": platform
        }
    )


def log_lock_rejected(logger: logging.Logger, platform: str) -> None:
    logger.warning(
        "Lock rejected - already locked",
        extra={
            "event": "lock_rejected",
            "platform": platform
        }
    )


def log_lock_released(logger: logging.Logger, platform: str) -> None:
    logger.info(
        "Lock released",
        extra={
            "event": "lock_released",
            "platform": platform
        }
    )


def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float
) -> None:
    level = "info" if status_code < 400 else "warning" if status_code < 500 else "error"
    log_func = logger.info if level == "info" else logger.warning if level == "warning" else logger.error
    
    log_func(
        f"{method} {path} {status_code}",
        extra={
            "event": "http_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2)
        }
    )


def log_student_failed(
    logger: logging.Logger,
    job_id: str,
    platform: str,
    roll_no: str,
    reason: str
) -> None:
    logger.warning(
        "Student sync failed",
        extra={
            "event": "student_failed",
            "job_id": job_id,
            "platform": platform,
            "roll_no": roll_no,
            "reason": reason
        }
    )
