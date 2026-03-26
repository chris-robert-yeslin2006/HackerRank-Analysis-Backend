import redis
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

LOCK_PREFIX = "lock:sync:"
LOCK_TTL = 600  # 10 minutes


def acquire_lock(platform: str) -> bool:
    """
    Try to acquire a lock for a sync platform.
    
    Uses Redis SET NX EX pattern for atomic lock acquisition.
    
    Args:
        platform: Platform name (e.g., 'codeforces', 'leetcode')
    
    Returns:
        True if lock acquired, False if already locked
    """
    key = f"{LOCK_PREFIX}{platform}"
    result = redis_client.set(key, "locked", nx=True, ex=LOCK_TTL)
    return result is True


def release_lock(platform: str) -> None:
    """
    Release the lock for a sync platform.
    
    Args:
        platform: Platform name (e.g., 'codeforces', 'leetcode')
    """
    key = f"{LOCK_PREFIX}{platform}"
    redis_client.delete(key)


def is_locked(platform: str) -> bool:
    """
    Check if a platform is currently locked.
    
    Args:
        platform: Platform name
    
    Returns:
        True if locked, False otherwise
    """
    key = f"{LOCK_PREFIX}{platform}"
    return redis_client.exists(key) > 0


def refresh_lock(platform: str) -> bool:
    """
    Refresh the TTL of an existing lock.
    
    Args:
        platform: Platform name
    
    Returns:
        True if lock refreshed, False if no lock exists
    """
    key = f"{LOCK_PREFIX}{platform}"
    if redis_client.exists(key):
        redis_client.expire(key, LOCK_TTL)
        return True
    return False
