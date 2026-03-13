from pydantic import BaseModel
from typing import Optional
from datetime import date

class StudentBase(BaseModel):
    roll_no: str
    name: str
    department: str
    section: str
    year: int
    hackerrank_username: str

class StudentCreate(StudentBase):
    pass

class Student(StudentBase):
    id: str # UUID as string

class StudentUpdate(BaseModel):
    roll_no: Optional[str] = None
    name: Optional[str] = None
    department: Optional[str] = None
    section: Optional[str] = None
    year: Optional[int] = None
    hackerrank_username: Optional[str] = None

class LeaderboardEntryCreate(BaseModel):
    contest_name: str
    contest_date: Optional[date] = None
    username: str
    score: int
    time_taken: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str
