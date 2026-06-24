from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# Job schemas
class JobCreate(BaseModel):
    title: str
    description: str

class JobResponse(BaseModel):
    id: int
    title: str
    description: str
    parsed_requirements: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}

# Candidate schemas
class CandidateExperience(BaseModel):
    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None

class CandidateEducation(BaseModel):
    institution: str
    degree: str
    grad_year: Optional[str] = None

class CandidateResponse(BaseModel):
    id: int
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    skills: Optional[List[str]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    embedding_generated: bool
    created_at: datetime

    model_config = {"from_attributes": True}

# Ranking schemas
class RankingResponse(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    score: float
    sub_scores: Optional[Dict[str, float]] = None
    pros: Optional[List[str]] = None
    cons: Optional[List[str]] = None
    feedback_report: Optional[Dict[str, Any]] = None
    feedback_sent: bool
    status: str
    updated_at: datetime
    candidate: Optional[CandidateResponse] = None

    model_config = {"from_attributes": True}

class RankingStatusUpdate(BaseModel):
    status: str  # pending, shortlisted, rejected

# AuditLog schemas
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    target_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = {"from_attributes": True}
