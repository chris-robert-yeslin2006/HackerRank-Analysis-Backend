import os
import time
import json
import gzip
import threading
from typing import Any, Optional, Dict, Callable
from dotenv import load_dotenv
from supabase import create_client, Client
from utils.logger import get_logger

load_dotenv()

logger = get_logger("database")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

supabase: Client = create_client(url, key)


UPSTASH_URL = os.environ.get("UPSTASH_URL")
UPSTASH_TOKEN = os.environ.get("UPSTASH_TOKEN")
RAILWAY_REDIS_URL = os.environ.get("RAILWAY_REDIS_URL")

PAYLOAD_SIZE_THRESHOLD = 100 * 1024


class MemoryCache:
    def __init__(self, default_ttl: int = 60):
        self._cache: Dict[str, tuple[Any, float, bool]] = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                data, expiry, is_stale = self._cache[key]
                now = time.time()
                if now < expiry:
                    return data, is_stale
                if now < expiry + 30:
                    return data, True
                del self._cache[key]
        return None
    
    def get_stale(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                data, expiry, is_stale = self._cache[key]
                if time.time() < expiry + 30:
                    return data, is_stale
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            expiry = time.time() + (ttl or self.default_ttl)
            self._cache[key] = (value, expiry, False)
    
    def set_with_stale(self, key: str, value: Any, ttl: Optional[int] = None, is_stale: bool = False) -> None:
        with self._lock:
            expiry = time.time() + (ttl or self.default_ttl)
            self._cache[key] = (value, expiry, is_stale)
    
    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
    
    def stats(self) -> Dict[str, int]:
        with self._lock:
            now = time.time()
            expired = sum(1 for _, exp, _ in self._cache.values() if now >= exp + 30)
            return {"total": len(self._cache), "expired": expired}


memory_cache = MemoryCache(default_ttl=60)


class RedisClient:
    def __init__(self, provider: str, client: Any):
        self.provider = provider
        self.client = client
        self.compression_enabled = True
    
    def get(self, key: str) -> Optional[str]:
        return self.client.get(key)
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        self.client.set(key, value, ex=ex)
    
    def delete(self, key: str) -> None:
        self.client.delete(key)
    
    def keys(self, pattern: str) -> list:
        return self.client.keys(pattern)
    
    def ping(self) -> bool:
        return self.client.ping()


redis_clients: Dict[str, RedisClient] = {}
selected_redis: Optional[RedisClient] = None
redis_provider_stats: Dict[str, Dict[str, float]] = {}


def _benchmark_redis(client: Any, provider: str, iterations: int = 5) -> Dict[str, float]:
    test_key = f"_benchmark_{provider}"
    test_value = json.dumps({"test": "data", "timestamp": time.time()})
    
    get_times = []
    set_times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        client.set(test_key, test_value)
        set_times.append((time.perf_counter() - start) * 1000)
        
        start = time.perf_counter()
        client.get(test_key)
        get_times.append((time.perf_counter() - start) * 1000)
    
    client.delete(test_key)
    
    return {
        "provider": provider,
        "avg_get_ms": round(sum(get_times) / len(get_times), 2),
        "avg_set_ms": round(sum(set_times) / len(set_times), 2),
        "min_get_ms": round(min(get_times), 2),
        "max_get_ms": round(max(get_times), 2),
    }


def init_redis_clients() -> None:
    global redis_clients, selected_redis, redis_provider_stats
    
    if UPSTASH_URL and UPSTASH_TOKEN:
        try:
            from upstash_redis import Redis
            upstash = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)
            if upstash.ping():
                redis_clients["upstash"] = RedisClient("upstash", upstash)
                logger.info("Upstash Redis connected", extra={"event": "redis_connected", "provider": "upstash"})
        except Exception as e:
            logger.warning("Upstash Redis failed", extra={"event": "redis_error", "provider": "upstash", "error": str(e)})
    
    if RAILWAY_REDIS_URL:
        try:
            import redis
            railway = redis.from_url(RAILWAY_REDIS_URL, decode_responses=True)
            if railway.ping():
                redis_clients["railway"] = RedisClient("railway", railway)
                logger.info("Railway Redis connected", extra={"event": "redis_connected", "provider": "railway"})
        except Exception as e:
            logger.warning("Railway Redis failed", extra={"event": "redis_error", "provider": "railway", "error": str(e)})
    
    if not redis_clients:
        logger.warning("No Redis clients available", extra={"event": "redis_not_configured"})
        return
    
    if len(redis_clients) == 1:
        selected_redis = next(iter(redis_clients.values()))
        logger.info("Single Redis provider selected", extra={"event": "redis_selected", "provider": selected_redis.provider})
        return
    
    logger.info("Benchmarking Redis providers...", extra={"event": "redis_benchmark_start", "providers": list(redis_clients.keys())})
    
    best_provider = None
    best_avg_get = float("inf")
    
    for name, client in redis_clients.items():
        stats = _benchmark_redis(client.client, name, iterations=5)
        redis_provider_stats[name] = stats
        
        logger.info(
            "Redis benchmark results",
            extra={
                "event": "redis_benchmark",
                "provider": name,
                "avg_get_ms": stats["avg_get_ms"],
                "avg_set_ms": stats["avg_set_ms"],
                "min_get_ms": stats["min_get_ms"],
                "max_get_ms": stats["max_get_ms"]
            }
        )
        
        if stats["avg_get_ms"] < best_avg_get:
            best_avg_get = stats["avg_get_ms"]
            best_provider = name
    
    selected_redis = redis_clients[best_provider]
    logger.info("Best Redis provider selected", extra={"event": "redis_selected", "provider": best_provider, "avg_get_ms": best_avg_get})


def get_redis() -> Optional[RedisClient]:
    return selected_redis


def get_selected_provider() -> str:
    return selected_redis.provider if selected_redis else "none"


def get_cache_stats() -> Dict[str, Any]:
    stats = {
        "memory": memory_cache.stats(),
        "redis_providers": list(redis_clients.keys()),
        "selected_redis": selected_redis.provider if selected_redis else None,
        "redis_stats": redis_provider_stats
    }
    return stats


def _compress(data: str) -> bytes:
    return gzip.compress(data.encode("utf-8"))


def _decompress(data: bytes) -> str:
    return gzip.decompress(data).decode("utf-8")


def _serialize(value: Any) -> tuple[str, int, bool]:
    json_str = json.dumps(value)
    size = len(json_str.encode("utf-8"))
    
    if size > PAYLOAD_SIZE_THRESHOLD:
        compressed = _compress(json_str)
        return compressed.hex(), len(compressed), True
    
    return json_str, size, False


def _deserialize(data: str | bytes, compressed: bool) -> Any:
    if compressed:
        return json.loads(_decompress(bytes.fromhex(data)))
    return json.loads(data)


class CacheService:
    def __init__(self, namespace: str = "cache", default_ttl: int = 60):
        self.namespace = namespace
        self.default_ttl = default_ttl
        self._locks: Dict[str, threading.Lock] = {}
        self._lock_manager = threading.Lock()
        self._stale_ttl = 30
        self._results: Dict[str, Any] = {}
    
    def _make_key(self, key: str) -> str:
        return f"{self.namespace}:{key}"
    
    def _get_lock(self, full_key: str) -> threading.Lock:
        with self._lock_manager:
            if full_key not in self._locks:
                self._locks[full_key] = threading.Lock()
            return self._locks[full_key]
    
    def _release_lock(self, full_key: str) -> None:
        with self._lock_manager:
            if full_key in self._locks:
                lock = self._locks.pop(full_key)
                try:
                    lock.release()
                except threading.ThreadError:
                    pass
    
    def _wait_for_result(self, full_key: str, timeout: float = 10.0) -> Optional[Any]:
        start = time.perf_counter()
        while time.perf_counter() - start < timeout:
            if full_key in self._results:
                return self._results.pop(full_key, None)
            time.sleep(0.01)
        return None
    
    def get(self, key: str, fetch_func: Optional[Callable] = None, background_refresh: bool = True) -> Optional[Any]:
        full_key = self._make_key(key)
        start_total = time.perf_counter()
        
        mem_result = memory_cache.get(full_key)
        if mem_result is not None:
            data, is_stale = mem_result
            
            if not is_stale:
                parse_start = time.perf_counter()
                result = _deserialize(data, False)
                parse_duration = (time.perf_counter() - parse_start) * 1000
                
                logger.info(
                    "Cache hit (L1)",
                    extra={
                        "event": "cache_hit",
                        "source": "memory",
                        "key": key,
                        "is_stale": False,
                        "duration_ms": round((time.perf_counter() - start_total) * 1000, 2),
                        "parse_ms": round(parse_duration, 2)
                    }
                )
                return result
            
            if fetch_func and background_refresh:
                logger.info(
                    "Cache stale (L1) - background refresh",
                    extra={
                        "event": "cache_stale_served",
                        "source": "memory",
                        "key": key,
                        "duration_ms": round((time.perf_counter() - start_total) * 1000, 2)
                    }
                )
                parse_start = time.perf_counter()
                result = _deserialize(data, False)
                thread = threading.Thread(target=self._background_fetch, args=(key, fetch_func))
                thread.daemon = True
                thread.start()
                return result
        
        redis = get_redis()
        if redis:
            redis_start = time.perf_counter()
            raw_data = redis.get(full_key)
            redis_duration = (time.perf_counter() - redis_start) * 1000
            
            if raw_data:
                try:
                    data_dict = json.loads(raw_data)
                    data = data_dict["data"]
                    compressed = data_dict.get("compressed", False)
                    is_stale = data_dict.get("is_stale", False)
                    
                    parse_start = time.perf_counter()
                    result = _deserialize(data, compressed)
                    parse_duration = (time.perf_counter() - parse_start) * 1000
                    
                    data_size = data_dict.get("size", len(raw_data))
                    
                    if not is_stale:
                        memory_cache.set_with_stale(full_key, (data, compressed), self.default_ttl, False)
                    else:
                        memory_cache.set_with_stale(full_key, (data, compressed), self._stale_ttl, True)
                    
                    if is_stale and fetch_func and background_refresh:
                        logger.info(
                            "Cache stale (L2) - background refresh",
                            extra={
                                "event": "cache_stale_served",
                                "source": "redis",
                                "provider": redis.provider,
                                "key": key,
                                "duration_ms": round((time.perf_counter() - start_total) * 1000, 2)
                            }
                        )
                        thread = threading.Thread(target=self._background_fetch, args=(key, fetch_func))
                        thread.daemon = True
                        thread.start()
                    else:
                        logger.info(
                            "Cache hit (L2)",
                            extra={
                                "event": "cache_hit",
                                "source": "redis",
                                "provider": redis.provider,
                                "key": key,
                                "is_stale": is_stale,
                                "duration_ms": round((time.perf_counter() - start_total) * 1000, 2),
                                "redis_fetch_ms": round(redis_duration, 2),
                                "parse_ms": round(parse_duration, 2),
                                "data_size": data_size,
                                "compressed": compressed
                            }
                        )
                    return result
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Cache data corrupted", extra={"event": "cache_error", "key": key, "error": str(e)})
            
            logger.info(
                "Cache miss",
                extra={
                    "event": "cache_miss",
                    "source": "redis",
                    "provider": redis.provider if redis else "none",
                    "key": key,
                    "redis_fetch_ms": round(redis_duration, 2)
                }
            )
        else:
            logger.info(
                "Cache miss",
                extra={
                    "event": "cache_miss",
                    "source": "none",
                    "key": key
                }
            )
        
        if fetch_func:
            lock = self._get_lock(full_key)
            
            if lock.acquire(blocking=False):
                try:
                    logger.info(
                        "Lock acquired",
                        extra={"event": "cache_lock_acquired", "key": key}
                    )
                    
                    db_start = time.perf_counter()
                    result = fetch_func()
                    db_duration = (time.perf_counter() - db_start) * 1000
                    
                    if result is not None:
                        self.set(key, result)
                        
                        logger.info(
                            "Data fetched from DB",
                            extra={
                                "event": "db_fetch",
                                "key": key,
                                "db_fetch_ms": round(db_duration, 2)
                            }
                        )
                    return result
                finally:
                    self._release_lock(full_key)
            else:
                logger.info(
                    "Waiting for lock",
                    extra={"event": "cache_waiting", "key": key}
                )
                
                result = self._wait_for_result(full_key)
                if result is not None:
                    logger.info(
                        "Got result from another thread",
                        extra={"event": "cache_result_received", "key": key}
                    )
                    return result
                
                db_start = time.perf_counter()
                result = fetch_func()
                db_duration = (time.perf_counter() - db_start) * 1000
                
                if result is not None:
                    self.set(key, result)
                    logger.info(
                        "Data fetched (fallback)",
                        extra={
                            "event": "db_fetch",
                            "key": key,
                            "db_fetch_ms": round(db_duration, 2)
                        }
                    )
                return result
        
        return None
    
    def _background_fetch(self, key: str, fetch_func: Callable) -> None:
        full_key = self._make_key(key)
        lock = self._get_lock(full_key)
        
        if not lock.acquire(blocking=False):
            return
        
        try:
            start = time.perf_counter()
            result = fetch_func()
            duration_ms = (time.perf_counter() - start) * 1000
            
            if result is not None:
                self.set(key, result)
                self._results[full_key] = result
                
                logger.info(
                    "Background refresh complete",
                    extra={
                        "event": "cache_refreshed",
                        "key": key,
                        "duration_ms": round(duration_ms, 2)
                    }
                )
        except Exception as e:
            logger.warning(
                "Background refresh failed",
                extra={
                    "event": "cache_refresh_error",
                    "key": key,
                    "error": str(e)
                }
            )
        finally:
            self._release_lock(full_key)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        full_key = self._make_key(key)
        ttl = ttl or self.default_ttl
        
        data_str, size, compressed = _serialize(value)
        
        if size > PAYLOAD_SIZE_THRESHOLD:
            logger.warning(
                "Large payload cached",
                extra={
                    "event": "large_payload",
                    "key": key,
                    "data_size": size,
                    "compressed": compressed
                }
            )
        
        memory_cache.set(full_key, (data_str, compressed), ttl)
        
        redis = get_redis()
        if redis:
            redis_start = time.perf_counter()
            cache_data = json.dumps({"data": data_str, "compressed": compressed, "size": size, "is_stale": False})
            redis.set(full_key, cache_data, ex=ttl)
            redis_duration = (time.perf_counter() - redis_start) * 1000
            
            logger.info(
                "Cache set",
                extra={
                    "event": "cache_set",
                    "source": "both",
                    "provider": redis.provider,
                    "key": key,
                    "duration_ms": round(redis_duration, 2),
                    "data_size": size,
                    "compressed": compressed
                }
            )
        else:
            logger.info(
                "Cache set",
                extra={
                    "event": "cache_set",
                    "source": "memory",
                    "key": key,
                    "data_size": size
                }
            )
    
    def delete(self, key: str) -> None:
        full_key = self._make_key(key)
        memory_cache.delete(full_key)
        
        redis = get_redis()
        if redis:
            redis.delete(full_key)
        
        logger.info("Cache deleted", extra={"event": "cache_delete", "key": key})
    
    def invalidate(self, pattern: str = None) -> int:
        full_pattern = self._make_key(pattern) if pattern else f"{self.namespace}:*"
        deleted = 0
        
        if pattern:
            memory_cache.delete(full_pattern)
        else:
            memory_cache.clear()
        
        redis = get_redis()
        if redis and pattern:
            keys = redis.keys(full_pattern)
            for k in keys:
                redis.delete(k)
                deleted += 1
        
        logger.info("Cache invalidated", extra={"event": "cache_invalidate", "pattern": pattern, "deleted": deleted})
        return deleted


init_redis_clients()

redis_client = selected_redis.client if selected_redis else None
