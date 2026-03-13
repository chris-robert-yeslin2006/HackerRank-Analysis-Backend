from fastapi import APIRouter, HTTPException
from database import supabase

router = APIRouter(tags=["Analytics"])

@router.get("/analytics/department")
def get_department_leaderboard():
    try:
        # Calling the RPC function deployed on Supabase
        response = supabase.rpc("get_department_leaderboard").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching data. Did you run the RPC SQL in Supabase? Error: {str(e)}")

@router.get("/analytics/section")
def get_section_leaderboard():
    try:
        response = supabase.rpc("get_section_leaderboard").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/analytics/top-students")
def get_top_students():
    try:
        response = supabase.rpc("get_top_students").execute()
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
        response = supabase.rpc("get_all_raw_data").execute()
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
