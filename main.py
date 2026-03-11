from fastapi import FastAPI
import firebase_admin
from firebase_admin import credentials

# Initialize FastAPI app
app = FastAPI(
    title="HackerRank Analysis API",
    description="API for HackerRank Analysis Backend",
    version="1.0.0"
)

# TODO: Initialize Firebase Admin SDK once the db manager provides schema & collections
# cred = credentials.Certificate("path/to/serviceAccountKey.json")
# firebase_admin.initialize_app(cred)

@app.get("/")
def read_root():
    return {"message": "Welcome to HackerRank Analysis Backend API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
