import redis
import os
from dotenv import load_dotenv
from utils.logger import get_logger, log_lock_acquired, log_lock_rejected, log_lock_released

load_dotenv()

logger = get_logger("utils.lock")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

LOCK_PREFIX = "lock:sync:"
LOCK_TTL = 600


def acquire_lock(platform: str) -> bool:
    key = f"{LOCK_PREFIX}{platform}"
    result = redis_client.set(key, "locked", nx=True, ex=LOCK_TTL)
    
    if result:
        log_lock_acquired(logger, platform)
    else:
        log_lock_rejected(logger, platform)
    
    return result is True


def release_lock(platform: str) -> None:
    key = f"{LOCK_PREFIX}{platform}"
    redis_client.delete(key)
    log_lock_released(logger, platform)


def is_locked(platform: str) -> bool:
    key = f"{LOCK_PREFIX}{platform}"
    return redis_client.exists(key) > 0


def refresh_lock(platform: str) -> bool:
    key = f"{LOCK_PREFIX}{platform}"
    if redis_client.exists(key):
        redis_client.expire(key, LOCK_TTL)
        return True
    return False
