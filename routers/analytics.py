from fastapi import APIRouter, HTTPException
from database import supabase, redis_client
import json
import time

router = APIRouter(tags=["Analytics"])

_cache = {}
_cache_ttl = 60

def get_cached(key):
    # Try Redis first
    if redis_client:
        try:
            data = redis_client.get(f"cache:{key}")
            if data:
                print(f"🔵 Redis HIT: {key}")
                return json.loads(data)
            print(f"🔴 Redis MISS: {key}")
        except Exception as e:
            print(f"⚠️ Redis error: {e}")
    
    # Fallback to in-memory
    if key in _cache:
        data, timestamp = _cache[key]
        if time.time() - timestamp < _cache_ttl:
            print(f"🔵 Memory HIT: {key}")
            return data
    return None

def set_cached(key, value):
    # Try Redis first
    if redis_client:
        try:
            redis_client.set(f"cache:{key}", json.dumps(value), ex=60)
            print(f"✅ Redis SET: {key}")
            return
        except Exception as e:
            print(f"⚠️ Redis set error: {e}")
    
    # Fallback to in-memory
    _cache[key] = (value, time.time())
    print(f"✅ Memory SET: {key}")

@router.get("/analytics/department")
def get_department_leaderboard(platform: str = "hackerrank"):
    cache_key = f"dept_{platform}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        if platform.lower() == "leetcode":
            response = supabase.rpc("get_leetcode_analytics", {"p_limit": 10000, "p_offset": 0}).execute()
            data = response.data
        elif platform.lower() == "codeforces":
            response = supabase.rpc("get_codeforces_analytics", {"p_limit": 10000, "p_offset": 0}).execute()
            data = response.data
        elif platform.lower() == "codechef":
            response = supabase.rpc("get_codechef_analytics", {"p_limit": 10000, "p_offset": 0}).execute()
            data = response.data
        else:
            response = supabase.rpc("get_platform_department_leaderboard", {"p_platform": platform.lower()}).execute()
            data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching data: {str(e)}")

@router.get("/analytics/platform-department")
def get_platform_department_leaderboard(platform: str = "hackerrank"):
    cache_key = f"platform_dept_{platform}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        if platform.lower() == "codeforces":
            response = supabase.rpc("get_codeforces_department_leaderboard", {}).execute()
        elif platform.lower() == "codechef":
            response = supabase.rpc("get_codechef_department_leaderboard", {}).execute()
        else:
            response = supabase.rpc("get_department_leaderboard", {}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching department leaderboard: {str(e)}")

def fetch_all_with_pagination(rpc_name: str, page_size: int = 1000):
    """Fetch all data from an RPC using pagination."""
    all_data = []
    offset = 0
    
    while True:
        try:
            response = supabase.rpc(rpc_name, {"p_limit": page_size, "p_offset": offset}).execute()
            data = response.data if response.data else []
            all_data.extend(data)
            
            if len(data) < page_size:
                break
            offset += page_size
        except Exception as e:
            raise e
    
    return all_data


@router.get("/analytics/leetcode")
def get_leetcode_analytics():
    cache_key = "leetcode_analytics"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        data = fetch_all_with_pagination("get_leetcode_analytics")
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching LeetCode analytics: {str(e)}")

@router.get("/analytics/codeforces")
def get_codeforces_analytics():
    cache_key = "codeforces_analytics"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        data = fetch_all_with_pagination("get_codeforces_analytics")
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching Codeforces analytics: {str(e)}")

@router.get("/analytics/codechef")
def get_codechef_analytics():
    cache_key = "codechef_analytics"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        data = fetch_all_with_pagination("get_codechef_analytics")
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching CodeChef analytics: {str(e)}")

@router.get("/analytics/codeforces/absent/{contest_name}")
def get_codeforces_absent_students(contest_name: str):
    cache_key = f"cf_absent_{contest_name}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_codeforces_absent_students", {"p_contest_name": contest_name}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching Codeforces absent students: {str(e)}")

@router.get("/analytics/codechef/absent")
def get_codechef_absent_students():
    cache_key = "cc_absent"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_codechef_absent_students", {}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching CodeChef absent students: {str(e)}")

@router.get("/analytics/codeforces/absent")
def get_codeforces_all_absent():
    cache_key = "cf_absent_all"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_all_codeforces_absent", {}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching Codeforces absent students: {str(e)}")

@router.get("/analytics/leetcode/absent/{contest_type}")
def get_leetcode_absent_students(contest_type: str):
    if contest_type.lower() not in ["weekly", "biweekly"]:
        raise HTTPException(status_code=400, detail="contest_type must be 'weekly' or 'biweekly'")
        
    try:
        response = supabase.rpc("get_leetcode_absent_students", {"p_contest_type": contest_type.lower()}).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching LeetCode absent students: {str(e)}")

@router.get("/analytics/section")
def get_section_leaderboard():
    cache_key = "section_leaderboard"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_section_leaderboard", {}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/analytics/top-students")
def get_top_students():
    cache_key = "top_students"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_top_students", {}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch top students: {str(e)}")

@router.get("/analytics/absent-students/{contest_name}")
def get_absent_students(contest_name: str):
    cache_key = f"absent_{contest_name}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_absent_students", {"p_contest_name": contest_name}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch absent students: {str(e)}")

@router.get("/frontend-data")
def get_frontend_data():
    cache_key = "frontend_data"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_all_raw_data", {}).execute()
        raw_data = response.data

        grouped_data = {}

        for row in raw_data:
            year_int = row.get("year", 1)
            year_str = "I" if year_int == 1 else "II" if year_int == 2 else "III" if year_int == 3 else "IV" if year_int == 4 else str(year_int)
            dept = row.get("department", "Unknown")
            sec = row.get("section", "Unknown")
            
            group_key = f"{year_str}-{dept}-{sec}"
            
            if group_key not in grouped_data:
                grouped_data[group_key] = {
                    "year": year_str,
                    "dept": dept,
                    "section": sec,
                    "contests": {}
                }
                
            contest_name = row.get("contest_name", "Unknown")
            if contest_name not in grouped_data[group_key]["contests"]:
                grouped_data[group_key]["contests"][contest_name] = {}
                
            username = row.get("username")
            grouped_data[group_key]["contests"][contest_name][username] = {
                "id": row.get("student_id"),
                "name": row.get("name"),
                "user-id": username,
                "score": row.get("score"),
                "time": str(row.get("time_taken")),
                "rank": row.get("rank")
            }
        
        data = list(grouped_data.values())
        set_cached(cache_key, data)
        return data

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing frontend data: {str(e)}")