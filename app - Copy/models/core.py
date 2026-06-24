import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    parsed_requirements = Column(JSON, nullable=True)  # must-have, nice-to-have, experience_level
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    rankings = relationship("Ranking", back_populates="job", cascade="all, delete-orphan")

class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, nullable=True)
    skills = Column(JSON, nullable=True)  # List of skills
    experience = Column(JSON, nullable=True)  # List of work experiences
    education = Column(JSON, nullable=True)  # List of education records
    full_parsed_text = Column(Text, nullable=True)
    embedding_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    rankings = relationship("Ranking", back_populates="candidate", cascade="all, delete-orphan")

class Ranking(Base):
    __tablename__ = "rankings"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, default=0.0)
    sub_scores = Column(JSON, nullable=True)  # {"experience": 80.0, "skills": 90.0, "leadership": 70.0}
    pros = Column(JSON, nullable=True)  # List of matching points
    cons = Column(JSON, nullable=True)  # List of missing points
    feedback_report = Column(JSON, nullable=True)  # 3 skill gaps, 3 actions, time-to-close
    feedback_sent = Column(Boolean, default=False)
    status = Column(String, default="pending")  # pending, shortlisted, rejected
    interview_status = Column(String, default="not_scheduled")  # not_scheduled, scheduled, in_progress, completed
    autonomous_decision = Column(String, default="pending")  # pending, shortlisted, rejected, manual_review
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    job = relationship("Job", back_populates="rankings")
    candidate = relationship("Candidate", back_populates="rankings")

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="scheduled")  # scheduled, completed
    transcript = Column(JSON, nullable=True)  # List of message dicts: [{"role": "ai"/"candidate", "text": "..."}]
    confidence_score = Column(Float, default=0.0)
    communication_score = Column(Float, default=0.0)
    technical_score = Column(Float, default=0.0)
    ai_summary = Column(Text, nullable=True)
    proctoring_alerts = Column(JSON, nullable=True, default=list)  # [{"type": "tab_switch", "timestamp": "..."}]
    cheating_suspected = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EmailLog(Base):
    __tablename__ = "email_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    recipient_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    email_type = Column(String, nullable=False)  # outreach, congratulations, rejection
    status = Column(String, default="queued")  # queued, sent, intercepted
    sent_at = Column(DateTime, nullable=True)  # Target dispatch time or actual send time
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # Reference to user.id if logged in, or null
    action = Column(String, nullable=False)  # "ranking_computed", "candidate_shortlisted", "rejection_sent", etc.
    target_id = Column(String, nullable=True)  # Candidate or Job ID
    details = Column(JSON, nullable=True)  # Extra metadata
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
