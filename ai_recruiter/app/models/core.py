"""
models/auth.py  +  models/core.py  combined for Phase 1
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, JSON, String, Text, Float
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    recruiter = "recruiter"
    admin = "admin"


class CandidateStatus(str, enum.Enum):
    pending = "pending"
    shortlisted = "shortlisted"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name     = Column(String(255), nullable=True)
    role          = Column(Enum(UserRole), default=UserRole.recruiter, nullable=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    audit_logs    = relationship("AuditLog", back_populates="user")


class Job(Base):
    __tablename__ = "jobs"

    id                   = Column(Integer, primary_key=True, index=True)
    title                = Column(String(255), nullable=False)
    description          = Column(Text, nullable=False)
    parsed_requirements  = Column(JSON, nullable=True)
    created_at           = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rankings             = relationship("Ranking", back_populates="job")


class Candidate(Base):
    __tablename__ = "candidates"

    id                   = Column(Integer, primary_key=True, index=True)
    name                 = Column(String(255), nullable=False)
    email                = Column(String(255), index=True, nullable=True)
    phone                = Column(String(50), nullable=True)
    skills               = Column(JSON, default=list)
    experience           = Column(JSON, default=list)
    education            = Column(JSON, default=list)
    full_parsed_text     = Column(Text, nullable=True)
    embedding_generated  = Column(Boolean, default=False)
    created_at           = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rankings             = relationship("Ranking", back_populates="candidate")


class Ranking(Base):
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


class AuditLog(Base):
    __tablename__ = "audit_log"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    action     = Column(String(100), nullable=False)
    target_id  = Column(Integer, nullable=True)
    details    = Column(JSON, default=dict)
    timestamp  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user       = relationship("User", back_populates="audit_logs")