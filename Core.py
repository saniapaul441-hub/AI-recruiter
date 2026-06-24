"""
models/auth.py  +  models/core.py  combined for Phase 1
--------------------------------------------------------
Defines all 5 database tables:
  - User         (recruiters and admins)
  - Job          (job descriptions)
  - Candidate    (parsed resume profiles)
  - Ranking      (score, pros, cons, feedback per candidate per job)
  - AuditLog     (every action ever taken)
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, JSON, String, Text, Float
)
from sqlalchemy.orm import relationship

from app.database import Base


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    recruiter = "recruiter"
    admin = "admin"


class CandidateStatus(str, enum.Enum):
    pending = "pending"
    shortlisted = "shortlisted"
    rejected = "rejected"


# ─── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    """
    Stores recruiter and admin accounts.
    Password is stored as a bcrypt hash — never plain text.
    """
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name     = Column(String(255), nullable=True)
    role          = Column(Enum(UserRole), default=UserRole.recruiter, nullable=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit_logs    = relationship("AuditLog", back_populates="user")


# ─── Job ──────────────────────────────────────────────────────────────────────

class Job(Base):
    """
    Stores a job description + the AI-extracted requirements JSON.
    parsed_requirements example:
      {
        "must_have": ["Python", "5 years experience", "FastAPI"],
        "nice_to_have": ["React", "AWS"],
        "seniority": "senior",
        "soft_skills": ["leadership", "communication"]
      }
    """
    __tablename__ = "jobs"

    id                   = Column(Integer, primary_key=True, index=True)
    title                = Column(String(255), nullable=False)
    description          = Column(Text, nullable=False)
    parsed_requirements  = Column(JSON, nullable=True)   # filled by Phase 2
    created_at           = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rankings             = relationship("Ranking", back_populates="job")


# ─── Candidate ────────────────────────────────────────────────────────────────

class Candidate(Base):
    """
    Stores a parsed candidate profile.
    skills / experience / education are JSON so we don't need extra tables.

    skills example:         ["Python", "React", "PostgreSQL"]
    experience example:     [{"company": "Google", "title": "SWE", "years": 3}]
    education example:      [{"degree": "B.Tech CS", "institution": "IIT Delhi"}]
    embedding_generated:    True once their vector fingerprint is in Pinecone (Phase 3)
    """
    __tablename__ = "candidates"

    id                   = Column(Integer, primary_key=True, index=True)
    name                 = Column(String(255), nullable=False)
    email                = Column(String(255), index=True, nullable=True)
    phone                = Column(String(50), nullable=True)
    skills               = Column(JSON, default=list)
    experience           = Column(JSON, default=list)
    education            = Column(JSON, default=list)
    full_parsed_text     = Column(Text, nullable=True)   # raw resume text
    embedding_generated  = Column(Boolean, default=False)
    created_at           = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rankings             = relationship("Ranking", back_populates="candidate")


# ─── Ranking ──────────────────────────────────────────────────────────────────

class Ranking(Base):
    """
    One row per (job, candidate) pair after the AI has evaluated them.

    score:           0–100 match score
    pros:            ["Strong Python", "Led teams"]
    cons:            ["No React", "Only 3 years exp"]
    feedback_report: The personalised rejection report (Phase 4)
    feedback_sent:   Has the report been emailed to the candidate?
    status:          pending → shortlisted or rejected
    """
    __tablename__ = "rankings"

    id               = Column(Integer, primary_key=True, index=True)
    job_id           = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    candidate_id     = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    score            = Column(Float, nullable=True)
    pros             = Column(JSON, default=list)
    cons             = Column(JSON, default=list)
    feedback_report  = Column(JSON, nullable=True)
    feedback_sent    = Column(Boolean, default=False)
    status           = Column(Enum(CandidateStatus), default=CandidateStatus.pending)
    updated_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc))

    job              = relationship("Job", back_populates="rankings")
    candidate        = relationship("Candidate", back_populates="rankings")


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Every important action is recorded here.
    Examples:
      action="candidate_rejected",  target_id=42,  details={"score": 34, "job_id": 7}
      action="feedback_sent",       target_id=42,  details={"email": "john@example.com"}
      action="shortlisted",         target_id=42,  details={"recruiter": "ali@firm.com"}
    """
    __tablename__ = "audit_log"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    action     = Column(String(100), nullable=False)
    target_id  = Column(Integer, nullable=True)    # usually candidate_id or job_id
    details    = Column(JSON, default=dict)
    timestamp  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user       = relationship("User", back_populates="audit_logs")