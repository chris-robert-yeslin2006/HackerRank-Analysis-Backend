from fastapi import APIRouter, HTTPException
from database import supabase
import httpx
import json
import os
from pydantic import BaseModel
from typing import List, Optional, Any

router = APIRouter(tags=["Chat"])

# Gemini API Configuration
API_KEY = os.environ.get("GOOGLE_API_KEY")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

class ChatRequest(BaseModel):
    text: str

class ChatResponse(BaseModel):
    query: str
    data: List[Any]
    message: Optional[str] = None

def get_db_schema():
    try:
        with open("database_structure.json", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Schema file not found."

@router.get("/chat/models")
async def list_models():
    """List available models using direct API call."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not found.")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/sql", response_model=ChatResponse)
async def chat_to_sql(request: ChatRequest):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API Key not configured.")

    schema = get_db_schema()
    
    prompt = f"""
    You are a SQL expert. Given the following database schema (JSON), convert the user's natural language request into a valid PostgreSQL SELECT query.
    
    SCHEMA:
    {schema}
    
    RULES:
    1. ONLY return a valid PostgreSQL SELECT query.
    2. Do NOT include any explanations, markdown formatting (like ```sql), or other text.
    3. Ensure the query is read-only (SELECT only).
    4. Use the table and column names exactly as defined in the schema.
    5. For complex analytics, prefer joining tables on roll_no or username as specified.
    6. If the request is not related to the database, return "INVALID".
    
    USER REQUEST:
    {request.text}
    """

    # List of models to try in order of preference
    models_to_try = ['gemini-flash-latest', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    sql_query = None
    last_error = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        for model_name in models_to_try:
            url = f"{BASE_URL}/{model_name}:generateContent?key={API_KEY}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            }
            
            try:
                print(f"DEBUG: Trying model {model_name}...")
                response = await client.post(url, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    # Extract text from Gemini response structure
                    try:
                        sql_query = data['candidates'][0]['content']['parts'][0]['text'].strip()
                        print(f"DEBUG: Successfully used {model_name}")
                        break
                    except (KeyError, IndexError):
                        print(f"DEBUG: Unexpected response structure from {model_name}")
                        continue
                else:
                    last_error = f"Status {response.status_code}: {response.text}"
                    print(f"DEBUG: Model {model_name} failed with {last_error}")
                    continue
                    
            except Exception as e:
                last_error = str(e)
                print(f"DEBUG: Exception with {model_name}: {last_error}")
                continue
    
    if not sql_query:
        raise HTTPException(status_code=500, detail=f"All models failed to generate SQL. Last error: {last_error}")

    # Clean up Gemini output (sometimes it still includes markdown)
    if sql_query.startswith("```"):
        lines = sql_query.split("\n")
        sql_query = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
    
    # Strip whitespace, trailing semicolons, and common SQL comments
    sql_query = sql_query.strip().rstrip(';')
    
    if sql_query == "INVALID":
        raise HTTPException(status_code=400, detail="I couldn't translate that into a database query.")

    try:
        # Execute the query using the Supabase RPC
        db_response = supabase.rpc("execute_read_only_sql", {"p_sql": sql_query}).execute()
        
        return ChatResponse(
            query=sql_query,
            data=db_response.data if db_response.data else [],
            message="Success"
        )

    except Exception as e:
        print(f"Chat Execution Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error executing database query: {str(e)}")
