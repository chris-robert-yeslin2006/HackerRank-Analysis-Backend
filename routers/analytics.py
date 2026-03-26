from fastapi import APIRouter, HTTPException
from database import CacheService, supabase
from utils.logger import get_logger

logger = get_logger("routers.analytics")

router = APIRouter(tags=["Analytics"])

cache = CacheService(namespace="analytics", default_ttl=60)


def fetch_all_with_pagination(rpc_name: str, page_size: int = 1000):
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


@router.get("/analytics/department")
def get_department_leaderboard(platform: str = "hackerrank"):
    cache_key = f"dept_{platform}"
    
    def fetch():
        if platform.lower() == "leetcode":
            response = supabase.rpc("get_leetcode_analytics", {"p_limit": 10000, "p_offset": 0}).execute()
        elif platform.lower() == "codeforces":
            response = supabase.rpc("get_codeforces_analytics", {"p_limit": 10000, "p_offset": 0}).execute()
        elif platform.lower() == "codechef":
            response = supabase.rpc("get_codechef_analytics", {"p_limit": 10000, "p_offset": 0}).execute()
        else:
            response = supabase.rpc("get_platform_department_leaderboard", {"p_platform": platform.lower()}).execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.get("/analytics/platform-department")
def get_platform_department_leaderboard(platform: str = "hackerrank"):
    cache_key = f"platform_dept_{platform}"
    
    def fetch():
        if platform.lower() == "codeforces":
            response = supabase.rpc("get_codeforces_department_leaderboard", {}).execute()
        elif platform.lower() == "codechef":
            response = supabase.rpc("get_codechef_department_leaderboard", {}).execute()
        else:
            response = supabase.rpc("get_department_leaderboard", {}).execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.get("/analytics/leetcode")
def get_leetcode_analytics():
    cache_key = "leetcode_analytics"
    return cache.get(cache_key, fetch_func=lambda: fetch_all_with_pagination("get_leetcode_analytics"))


@router.get("/analytics/codeforces")
def get_codeforces_analytics():
    cache_key = "codeforces_analytics"
    return cache.get(cache_key, fetch_func=lambda: fetch_all_with_pagination("get_codeforces_analytics"))


@router.get("/analytics/codechef")
def get_codechef_analytics():
    cache_key = "codechef_analytics"
    return cache.get(cache_key, fetch_func=lambda: fetch_all_with_pagination("get_codechef_analytics"))


@router.get("/analytics/codeforces/absent/{contest_name}")
def get_codeforces_absent_students(contest_name: str):
    cache_key = f"cf_absent_{contest_name}"
    
    def fetch():
        response = supabase.rpc("get_codeforces_absent_students", {"p_contest_name": contest_name}).execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.get("/analytics/codechef/absent")
def get_codechef_absent_students():
    cache_key = "cc_absent"
    
    def fetch():
        response = supabase.rpc("get_codechef_absent_students", {}).execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.get("/analytics/codeforces/absent")
def get_codeforces_all_absent():
    cache_key = "cf_absent_all"
    
    def fetch():
        response = supabase.rpc("get_all_codeforces_absent", {}).execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


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
    
    def fetch():
        response = supabase.rpc("get_section_leaderboard", {}).execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.get("/analytics/top-students")
def get_top_students():
    cache_key = "top_students"
    
    def fetch():
        response = supabase.rpc("get_top_students", {}).execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.get("/analytics/absent-students/{contest_name}")
def get_absent_students(contest_name: str):
    cache_key = f"absent_{contest_name}"
    
    def fetch():
        response = supabase.rpc("get_absent_students", {"p_contest_name": contest_name}).execute()
        return response.data
    
    return cache.get(cache_key, fetch_func=fetch)


@router.get("/frontend-data")
def get_frontend_data():
    cache_key = "frontend_data"
    
    def fetch():
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
        
        return list(grouped_data.values())
    
    return cache.get(cache_key, fetch_func=fetch)
