from fastapi import APIRouter, HTTPException
from database import supabase
from functools import lru_cache
from datetime import datetime, timedelta
import time

router = APIRouter(tags=["Analytics"])

_cache = {}
_cache_ttl = 60  # Cache TTL in seconds

def get_cached(key):
    if key in _cache:
        data, timestamp = _cache[key]
        if time.time() - timestamp < _cache_ttl:
            return data
    return None

def set_cached(key, value):
    _cache[key] = (value, time.time())

@router.get("/analytics/department")
def get_department_leaderboard(platform: str = "hackerrank"):
    cache_key = f"dept_{platform}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        if platform.lower() == "leetcode":
            response = supabase.rpc("get_leetcode_analytics", {}).execute()
            data = response.data
        elif platform.lower() == "codeforces":
            response = supabase.rpc("get_codeforces_analytics", {}).execute()
            data = response.data
        elif platform.lower() == "codechef":
            response = supabase.rpc("get_codechef_analytics", {}).execute()
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

@router.get("/analytics/leetcode")
def get_leetcode_analytics():
    cache_key = "leetcode"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_leetcode_analytics", {}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching LeetCode analytics: {str(e)}")

@router.get("/analytics/codeforces")
def get_codeforces_analytics():
    cache_key = "codeforces"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_codeforces_analytics", {}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching Codeforces analytics: {str(e)}")

@router.get("/analytics/codechef")
def get_codechef_analytics():
    cache_key = "codechef"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    try:
        response = supabase.rpc("get_codechef_analytics", {}).execute()
        data = response.data
        set_cached(cache_key, data)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching CodeChef analytics: {str(e)}")

@router.get("/analytics/codeforces/absent")
def get_codeforces_absent_students():
    """
    Returns students who have Codeforces IDs but no stats (haven't been synced).
    """
    try:
        response = supabase.rpc("get_students_with_codeforces", {}).execute()
        students = response.data or []
        
        absent = []
        for student in students:
            stats_resp = supabase.table("codeforces_stats").select("roll_no").eq("roll_no", student["roll_no"]).execute()
            if not stats_resp.data:
                absent.append(student)
        
        return absent
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching Codeforces absent students: {str(e)}")

@router.get("/analytics/codechef/absent")
def get_codechef_absent_students():
    """
    Returns students who have CodeChef IDs but no stats (haven't been synced).
    """
    try:
        response = supabase.rpc("get_students_with_codechef", {}).execute()
        students = response.data or []
        
        absent = []
        for student in students:
            stats_resp = supabase.table("codechef_stats").select("roll_no").eq("roll_no", student["roll_no"]).execute()
            if not stats_resp.data:
                absent.append(student)
        
        return absent
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching CodeChef absent students: {str(e)}")

@router.get("/analytics/leetcode/absent/{contest_type}")
def get_leetcode_absent_students(contest_type: str):
    """
    Returns students who did not participate in a LeetCode contest (weekly or biweekly).
    """
    if contest_type.lower() not in ["weekly", "biweekly"]:
        raise HTTPException(status_code=400, detail="contest_type must be 'weekly' or 'biweekly'")
        
    try:
        response = supabase.rpc("get_leetcode_absent_students", {"p_contest_type": contest_type.lower()}).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching LeetCode absent students: {str(e)}")

@router.get("/analytics/section")
def get_section_leaderboard():
    try:
        response = supabase.rpc("get_section_leaderboard", {}).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/analytics/top-students")
def get_top_students():
    try:
        response = supabase.rpc("get_top_students", {}).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch top students: {str(e)}")

@router.get("/analytics/absent-students/{contest_name}")
def get_absent_students(contest_name: str):
    try:
        response = supabase.rpc("get_absent_students", {"p_contest_name": contest_name}).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch absent students: {str(e)}")

@router.get("/frontend-data")
def get_frontend_data():
    try:
        # Get raw joined data with ranks computed in SQL
        response = supabase.rpc("get_all_raw_data", {}).execute()
        raw_data = response.data

        # We will group by an explicit key to build the structure
        # Key: (year, department, section) -> frontend dictionary
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
                "id": row.get("student_id"), # Added student UUID
                "name": row.get("name"),
                "user-id": username,
                "score": row.get("score"),
                "time": str(row.get("time_taken")),
                "rank": row.get("rank")
            }
            
        return list(grouped_data.values())

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing frontend data: {str(e)}")
