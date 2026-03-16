from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import supabase

# Import routers
from routers import auth, students, leaderboard, analytics, sync

# Initialize FastAPI app
app = FastAPI(
    title="HackerRank Analysis API",
    description="API for HackerRank Analysis Backend with Supabase",
    version="1.0.0"
)

# CORS setup for future frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(leaderboard.router)
app.include_router(analytics.router)
app.include_router(sync.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to HackerRank Analysis Backend API"}

@app.get("/health")
def health_check():
    return {"status": "ok", "supabase_connected": supabase is not None}
