from fastapi import APIRouter, HTTPException, Response
from schemas import LoginRequest

router = APIRouter(tags=["Auth"])

@router.post("/login")
def login(login_data: LoginRequest, response: Response):
    # Hardcoded admin credentials as requested
    if login_data.username == "admin" and login_data.password == "Admin@123":
        # Set a cookie named 'auth_token' with value 'true'
        # httponly=True protects it from cross-site scripting (XSS)
        # samesite='lax' allows it to be sent with top-level navigations
        response.set_cookie(
            key="auth_token", 
            value="true", 
            httponly=True, 
            samesite="lax",
            max_age=86400 # 1 day expiration
        )
        return {"message": "Login successful", "authenticated": True}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")
