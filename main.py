from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import supabase, get_cache_stats, get_selected_provider

from middleware.logging import RequestLoggingMiddleware

app = FastAPI(
    title="HackerRank Analysis API",
    description="API for HackerRank Analysis Backend with Supabase",
    version="1.0.0"
)

origins = [
    "https://hacker-rank-analyzer.vercel.app",
    "http://localhost:3000",
]

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import auth, students, leaderboard, analytics, sync, platforms, chat
from routers import sync_v2

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(leaderboard.router)
app.include_router(analytics.router)
app.include_router(sync.router)
app.include_router(sync_v2.router)
app.include_router(platforms.router)
app.include_router(chat.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to HackerRank Analysis Backend API"}

@app.get("/health")
def health_check():
    return {"status": "ok", "supabase_connected": supabase is not None}

@app.get("/cache/stats")
def cache_stats():
    return get_cache_stats()
