import httpx
import asyncio
import os
import sys
from datetime import datetime

BASE_URL = os.getenv("CRON_BASE_URL", "https://hackerrank-analysis-backend.onrender.com")

async def call_sync_endpoint(client: httpx.AsyncClient, endpoint: str):
    """Call a sync endpoint and handle the response."""
    url = f"{BASE_URL}{endpoint}"
    try:
        print(f"[{datetime.now()}] Calling {url}")
        response = await client.post(url, timeout=300.0)
        response.raise_for_status()
        data = response.json()
        print(f"[{datetime.now()}] {endpoint}: {data.get('message', 'OK')}")
        return True
    except httpx.HTTPStatusError as e:
        print(f"[{datetime.now()}] {endpoint} HTTP error: {e.response.status_code}")
        return False
    except Exception as e:
        print(f"[{datetime.now()}] {endpoint} error: {str(e)}")
        return False

async def main():
    """Run all sync jobs."""
    print(f"[{datetime.now()}] Starting sync cron job...")
    
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
    print(f"[{datetime.now()}] Sync completed: {success_count}/{len(endpoints)} successful")
    
    if success_count < len(endpoints):
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
