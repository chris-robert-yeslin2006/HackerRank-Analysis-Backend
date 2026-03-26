import httpx
import asyncio
import os
import sys
from datetime import datetime
from utils.logger import get_logger

logger = get_logger("cron.sync")

BASE_URL = os.getenv("CRON_BASE_URL", "https://hackerrank-analysis-backend.onrender.com")

async def call_sync_endpoint(client: httpx.AsyncClient, endpoint: str):
    url = f"{BASE_URL}{endpoint}"
    try:
        logger.info("Calling sync endpoint", extra={"event": "cron_call", "endpoint": endpoint})
        response = await client.post(url, timeout=300.0)
        response.raise_for_status()
        data = response.json()
        logger.info("Sync completed", extra={"event": "cron_complete", "endpoint": endpoint, "message": data.get('message', 'OK')})
        return True
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error", extra={"event": "cron_error", "endpoint": endpoint, "status_code": e.response.status_code})
        return False
    except Exception as e:
        logger.error("Endpoint error", extra={"event": "cron_error", "endpoint": endpoint, "error": str(e)})
        return False

async def main():
    logger.info("Starting sync cron job", extra={"event": "cron_started"})
    
    endpoints = [
        "/sync/codeforces",
        "/sync/codechef",
        "/sync/leetcode",
    ]
    
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[call_sync_endpoint(client, endpoint) for endpoint in endpoints]
        )
    
    success_count = sum(1 for r in results if r)
    logger.info(
        "Cron completed",
        extra={"event": "cron_finished", "success_count": success_count, "total": len(endpoints)}
    )
    
    if success_count < len(endpoints):
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
