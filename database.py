import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

supabase: Client = create_client(url, key)

# Redis configuration (Upstash)
UPSTASH_URL = os.environ.get("UPSTASH_URL")
UPSTASH_TOKEN = os.environ.get("UPSTASH_TOKEN")

redis_client = None
if UPSTASH_URL and UPSTASH_TOKEN:
    try:
        from upstash_redis import Redis
        redis_client = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)
        redis_client.ping()
        print("✅ Redis connected successfully")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
else:
    print("⚠️ Redis not configured")
