import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks, WebSocket, WebSocketDisconnect, Header
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.auth import User
from app.models.core import Job, Candidate, Ranking, AuditLog, Interview, EmailLog
from app.schemas.core import (
    JobCreate, JobResponse, CandidateResponse, RankingResponse, 
    RankingStatusUpdate, AuditLogResponse
)
from app.routes.auth import require_recruiter, require_admin, get_current_user
from app.services.parser import ResumeParserService
from app.services.llm_router import llm_router
from app.services.vector_db import vector_db
from app.services.automation import (
    get_automation_mode, set_automation_mode, schedule_outreach_email, 
    evaluate_interview, trigger_safety_override, sweep_queued_emails,
    schedule_rejection_email
)

router = APIRouter(prefix="/api", tags=["Recruiter Workflow"])

def log_audit(db: Session, user_id: Optional[int], action: str, target_id: Optional[str], details: Optional[dict]):
    """Helper to log compliance and recruiter operations."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        target_id=str(target_id) if target_id else None,
        details=details
    )
    db.add(log)
    db.commit()

# --- JOB ENDPOINTS ---

@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(job_in: JobCreate, db: Session = Depends(get_db), current_user: User = Depends(require_recruiter)):
    """Upload and deconstruct a new Job Description."""
    # AI JD Deconstruction
    parsed_reqs = llm_router.deconstruct_jd(job_in.description)
    
    new_job = Job(
        title=job_in.title,
        description=job_in.description,
        parsed_requirements=parsed_reqs,
        recruiter_id=current_user.id
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    log_audit(db, current_user.id, "job_created", new_job.id, {"title": new_job.title})
    return new_job

@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db), current_user: User = Depends(require_recruiter)):
    """List all available jobs."""
    if current_user.role == "admin":
        return db.query(Job).order_by(Job.created_at.desc()).all()
    return db.query(Job).filter(Job.recruiter_id == current_user.id).order_by(Job.created_at.desc()).all()

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_recruiter)):
    """Get detailed job requirements."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
    return job

@router.delete("/jobs/{job_id}", status_code=status.HTTP_200_OK)
def delete_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_recruiter)):
    """Delete a job and its associated rankings."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
    
    log_audit(db, current_user.id, "job_deleted", job.id, {"title": job.title})
    db.delete(job)
    db.commit()
    return {"detail": "Job successfully deleted"}

# --- CANDIDATE ENDPOINTS ---

@router.post("/candidates/upload", response_model=List[CandidateResponse], status_code=status.HTTP_201_CREATED)
def upload_candidates(
    files: List[UploadFile] = File(...), 
    x_job_id: Optional[str] = Header(None),
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_recruiter)
):
    """Upload resumes in PDF, DOCX, or CSV candidate list format."""
    created_candidates = []
    
    if x_job_id:
        try:
            job_id_int = int(x_job_id)
            job = db.query(Job).filter(Job.id == job_id_int).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job workspace not found")
            if current_user.role != "admin" and job.recruiter_id != current_user.id:
                raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid x-job-id header format")
    
    for file in files:
        filename = file.filename.lower()
        file_bytes = file.file.read()
        
        if filename.endswith(".csv"):
            # Parse CSV sheet
            parsed_profiles = ResumeParserService.parse_csv(file_bytes)
            for profile in parsed_profiles:
                # Normalize email to None if empty/blank
                email_val = profile.get("email")
                if email_val:
                    email_val = email_val.strip()
                if not email_val:
                    email_val = None
                
                # Check for unique email to avoid duplicates
                existing = None
                if email_val:
                    existing = db.query(Candidate).filter(Candidate.email == email_val).first()
                
                if existing:
                    # Update profile
                    existing.skills = profile["skills"]
                    existing.experience = [{"company": "CSV Import", "title": profile["experience_raw"], "description": ""}]
                    existing.full_parsed_text = profile["full_parsed_text"]
                    db.commit()
                    db.refresh(existing)
                    cand = existing
                else:
                    cand = Candidate(
                        name=profile["name"],
                        email=email_val,
                        phone=profile["phone"] or None,
                        skills=profile["skills"],
                        experience=[{"company": "CSV Import", "title": profile["experience_raw"], "description": ""}],
                        education=[{"institution": "CSV Import", "degree": profile["education_raw"]}],
                        full_parsed_text=profile["full_parsed_text"]
                    )
                    db.add(cand)
                    db.commit()
                    db.refresh(cand)
                
                # Push embedding
                vector_db.upsert_candidate(cand.id, cand.full_parsed_text, save_cache=False)
                cand.embedding_generated = True
                db.commit()
                
                # Link candidate to job workspace if x_job_id is provided
                if x_job_id:
                    try:
                        job_id_int = int(x_job_id)
                        existing_rankings = db.query(Ranking).filter(
                            Ranking.job_id == job_id_int,
                            Ranking.candidate_id == cand.id
                        ).all()
                        if len(existing_rankings) > 0:
                            for extra in existing_rankings[1:]:
                                db.delete(extra)
                            db.commit()
                        else:
                            new_ranking = Ranking(
                                job_id=job_id_int,
                                candidate_id=cand.id,
                                score=0.0,
                                status="pending"
                            )
                            db.add(new_ranking)
                            db.commit()
                    except Exception as e:
                        print(f"Error linking candidate to job: {e}")
                        
                created_candidates.append(cand)
                log_audit(db, current_user.id, "candidate_imported", cand.id, {"name": cand.name})
                
        elif filename.endswith(".pdf") or filename.endswith(".docx"):
            # Parse PDF or DOCX file (support PDF splitting if multiple resumes)
            print(f"Uploading file: {filename} ({len(file_bytes)} bytes)")
            if filename.endswith(".pdf"):
                raw_texts = ResumeParserService.split_pdf_resumes(file_bytes)
                print(f"Split PDF into {len(raw_texts)} resumes")
            else:
                raw_texts = ResumeParserService.split_docx_resumes(file_bytes)
                print(f"Split DOCX into {len(raw_texts)} resumes")
                
            for raw_text in raw_texts:
                if not raw_text.strip():
                    continue
                
                # AI Resume Structuring
                profile = llm_router.structure_resume(raw_text)
                
                # Normalize email to None if empty/blank
                email_val = profile.get("email")
                if email_val:
                    email_val = email_val.strip()
                if not email_val:
                    email_val = None
                
                # Check duplicate
                existing = None
                if email_val:
                    existing = db.query(Candidate).filter(Candidate.email == email_val).first()
                    
                if existing:
                    existing.name = profile.get("name", existing.name)
                    existing.phone = profile.get("phone", existing.phone)
                    existing.skills = profile.get("skills", existing.skills)
                    existing.experience = profile.get("experience", existing.experience)
                    existing.education = profile.get("education", existing.education)
                    existing.full_parsed_text = raw_text
                    db.commit()
                    db.refresh(existing)
                    cand = existing
                else:
                    cand = Candidate(
                        name=profile.get("name", "Unknown Candidate"),
                        email=email_val,
                        phone=profile.get("phone") or None,
                        skills=profile.get("skills", []),
                        experience=profile.get("experience", []),
                        education=profile.get("education", []),
                        full_parsed_text=raw_text
                    )
                    db.add(cand)
                    db.commit()
                    db.refresh(cand)
                    
                # Push embedding
                vector_db.upsert_candidate(cand.id, cand.full_parsed_text, save_cache=False)
                cand.embedding_generated = True
                db.commit()
                
                # Link candidate to job workspace if x_job_id is provided
                if x_job_id:
                    try:
                        job_id_int = int(x_job_id)
                        existing_rankings = db.query(Ranking).filter(
                            Ranking.job_id == job_id_int,
                            Ranking.candidate_id == cand.id
                        ).all()
                        if len(existing_rankings) > 0:
                            for extra in existing_rankings[1:]:
                                db.delete(extra)
                            db.commit()
                        else:
                            new_ranking = Ranking(
                                job_id=job_id_int,
                                candidate_id=cand.id,
                                score=0.0,
                                status="pending"
                            )
                            db.add(new_ranking)
                            db.commit()
                    except Exception as e:
                        print(f"Error linking candidate to job: {e}")
                        
                created_candidates.append(cand)
                log_audit(db, current_user.id, "candidate_uploaded", cand.id, {"name": cand.name})
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file.filename}")
            
    # Save local cache once after all batch candidates are processed
    if created_candidates:
        vector_db.save_local_cache()
        
    return created_candidates

@router.get("/candidates", response_model=List[CandidateResponse])
def list_candidates(db: Session = Depends(get_db), current_user: User = Depends(require_recruiter)):
    """List all candidate profiles."""
    if current_user.role == "admin":
        return db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    # Find all job IDs owned by the current recruiter
    user_job_ids = [j.id for j in db.query(Job).filter(Job.recruiter_id == current_user.id).all()]
    return db.query(Candidate).join(Ranking).filter(Ranking.job_id.in_(user_job_ids)).order_by(Candidate.created_at.desc()).all()

@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_recruiter)):
    """Get single candidate detailed profile."""
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    if current_user.role != "admin":
        user_job_ids = [j.id for j in db.query(Job).filter(Job.recruiter_id == current_user.id).all()]
        linked = db.query(Ranking).filter(Ranking.candidate_id == candidate_id, Ranking.job_id.in_(user_job_ids)).first()
        if not linked:
            raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this candidate profile")
            
    return cand

# --- RANKINGS & SEARCH ENDPOINTS ---

@router.post("/rankings/compute/{job_id}", response_model=List[RankingResponse])
def compute_rankings(
    job_id: int, 
    linked_only: bool = Query(False),
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_recruiter)
):
    """Execute hybrid vector similarity and deep LLM ranking pipeline."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
        
    # Get all candidates who are already explicitly linked to this job (e.g. uploaded directly to it)
    linked_rankings = db.query(Ranking).filter(Ranking.job_id == job_id).all()
    linked_cand_ids = {r.candidate_id for r in linked_rankings}
    
    candidate_ids_to_rank = []
    vector_scores = {}
    
    if linked_only:
        if not linked_cand_ids:
            raise HTTPException(status_code=400, detail="No candidates are explicitly uploaded or linked to this job workspace. Please upload resumes first.")
        candidate_ids_to_rank = list(linked_cand_ids)
        vector_scores = {c_id: 0.5 for c_id in linked_cand_ids}
    else:
        # Phase 1: Fast Filter (Vector Similarity query for top 50 candidates)
        # If less than 50 candidates, query all candidates available
        c_count = db.query(Candidate).count()
        if c_count == 0:
            raise HTTPException(status_code=400, detail="No candidates loaded in DB. Please upload candidates first.")
            
        top_matches = vector_db.query_top_candidates(job.description, top_k=min(50, c_count))
        
        # Merge candidates to ensure all explicitly uploaded ones are evaluated
        for c_id, score in top_matches:
            candidate_ids_to_rank.append(c_id)
            vector_scores[c_id] = score
            
        for c_id in linked_cand_ids:
            if c_id not in vector_scores:
                candidate_ids_to_rank.append(c_id)
                vector_scores[c_id] = 0.5  # default similarity score
            
    computed_rankings = []
    
    for candidate_id in candidate_ids_to_rank:
        vector_score = vector_scores[candidate_id]
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            continue
            
        # Check if ranking already exists
        rankings = db.query(Ranking).filter(Ranking.job_id == job_id, Ranking.candidate_id == candidate_id).all()
        if len(rankings) > 1:
            ranking = rankings[0]
            for extra in rankings[1:]:
                db.delete(extra)
            db.commit()
        elif len(rankings) == 1:
            ranking = rankings[0]
        else:
            ranking = None
        
        # Phase 2: Deep LLM Recruiter Evaluation
        # Always re-rank or rank fresh candidates
        try:
            eval_report = llm_router.deep_rank_candidate(
                candidate_profile={
                    "name": candidate.name,
                    "skills": candidate.skills,
                    "experience": candidate.experience,
                    "education": candidate.education
                },
                jd_requirements=job.parsed_requirements or {"extracted_title": job.title, "must_have_skills": [], "nice_to_have_skills": [], "experience_level": "", "summary": job.description}
            )
            
            score = float(eval_report.get("score", 50.0))
            sub_scores = eval_report.get("sub_scores", {"experience": score, "skills": score, "leadership": score})
            pros = eval_report.get("pros", [])
            cons = eval_report.get("cons", [])
            behavioral = eval_report.get("behavioral_indicators", "")
            
            if ranking:
                ranking.score = score
                ranking.sub_scores = sub_scores
                ranking.pros = pros
                ranking.cons = cons
                # Store behavioral inside feedback_report initially or as a separate tag
                fb = ranking.feedback_report or {}
                fb["behavioral_indicators"] = behavioral
                ranking.feedback_report = fb
            else:
                ranking = Ranking(
                    job_id=job_id,
                    candidate_id=candidate_id,
                    score=score,
                    sub_scores=sub_scores,
                    pros=pros,
                    cons=cons,
                    feedback_report={"behavioral_indicators": behavioral},
                    status="pending"
                )
                db.add(ranking)
                
            db.commit()
            db.refresh(ranking)
        except Exception as e:
            print(f"Error computing detailed AI rank for candidate {candidate.name}: {e}")
            # Fallback to standard vector similarity score if Gemini fails
            score = round(float(vector_score) * 100.0, 1)
            if ranking:
                ranking.score = score
            else:
                ranking = Ranking(
                    job_id=job_id,
                    candidate_id=candidate_id,
                    score=score,
                    sub_scores={"experience": score, "skills": score, "leadership": score},
                    pros=["Matches via vector semantics."],
                    cons=["Detailed AI analysis pending."],
                    status="pending"
                )
                db.add(ranking)
            db.commit()
            db.refresh(ranking)
            
        # Trigger autonomous evaluation and outreach email if autonomous mode is enabled
        if get_automation_mode():
            # Make dynamic decision
            decision = "shortlisted" if ranking.score >= 65.0 else "rejected"
            ranking.status = decision
            ranking.autonomous_decision = decision
            
            # Check if we have already queued/sent an outreach or rejection for this candidate to avoid duplicates
            existing_logs = db.query(EmailLog).filter(
                EmailLog.recipient_email == candidate.email,
                EmailLog.email_type.in_(["outreach", "rejected", "shortlisted"]),
                EmailLog.sender_user_id == job.recruiter_id
            ).first()
            
            if not existing_logs:
                if decision == "shortlisted":
                    ranking.interview_status = "scheduled"
                    db.commit()
                    # Dispatch outreach invitation to private screening room
                    schedule_outreach_email(candidate, job, db)
                else:
                    ranking.interview_status = "not_scheduled"
                    # Generate structured coaching report
                    feedback = llm_router.generate_rejection_feedback(
                        candidate_profile={
                            "name": candidate.name,
                            "skills": candidate.skills,
                            "experience": candidate.experience
                        },
                        jd_requirements=job.parsed_requirements or {"extracted_title": job.title, "must_have_skills": [], "summary": job.description}
                    )
                    fb_report = ranking.feedback_report or {}
                    fb_report.update(feedback)
                    ranking.feedback_report = fb_report
                    ranking.feedback_sent = True
                    db.commit()
                    
                    # Dispatch rejection email with gaps & links
                    schedule_rejection_email(candidate, job, db)
                    
        computed_rankings.append(ranking)
                
    log_audit(db, current_user.id, "rankings_computed", job_id, {"candidates_count": len(computed_rankings)})
    return computed_rankings

@router.get("/rankings/{job_id}", response_model=List[RankingResponse])
def get_rankings(
    job_id: int, 
    exp_w: float = Query(1.0, alias="experience_weight"),
    sk_w: float = Query(1.0, alias="skills_weight"),
    ld_w: float = Query(1.0, alias="leadership_weight"),
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_recruiter)
):
    """Retrieve computed candidate rankings for a job description, re-sorting live based on custom weights."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job workspace not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")

    # Sweep and process any expired queued emails
    sweep_queued_emails(db)
    
    rankings = db.query(Ranking).filter(Ranking.job_id == job_id).all()
    
    # Defensive cleanup of duplicate rankings
    seen = set()
    cleaned_rankings = []
    duplicates_to_delete = []
    for r in rankings:
        if r.candidate_id in seen:
            duplicates_to_delete.append(r)
        else:
            seen.add(r.candidate_id)
            cleaned_rankings.append(r)
            
    if duplicates_to_delete:
        for extra in duplicates_to_delete:
            db.delete(extra)
        db.commit()
        
    rankings = cleaned_rankings
    
    if not rankings:
        return []
        
    # Re-calculate dynamic scores live based on slider weights
    total_weight = exp_w + sk_w + ld_w
    if total_weight == 0.0:
        total_weight = 1.0  # Avoid zero division
        
    for r in rankings:
        sub = r.sub_scores or {"experience": r.score, "skills": r.score, "leadership": r.score}
        exp_score = sub.get("experience", r.score)
        sk_score = sub.get("skills", r.score)
        ld_score = sub.get("leadership", r.score)
        
        # Weighted average
        weighted_score = (exp_w * exp_score + sk_w * sk_score + ld_w * ld_score) / total_weight
        r.score = round(weighted_score, 1)
        
    # Sort rankings in memory descending
    sorted_rankings = sorted(rankings, key=lambda x: x.score, reverse=True)
    return sorted_rankings

@router.put("/rankings/{ranking_id}/status", response_model=RankingResponse)
def update_candidate_status(
    ranking_id: int, 
    status_in: RankingStatusUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_recruiter)
):
    """Update candidate hiring status (shortlisted, rejected, pending). Generates feedback for rejections."""
    ranking = db.query(Ranking).filter(Ranking.id == ranking_id).first()
    if not ranking:
        raise HTTPException(status_code=404, detail="Ranking record not found")
        
    job = db.query(Job).filter(Job.id == ranking.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job workspace not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
        
    new_status = status_in.status.lower()
    if new_status not in ["pending", "shortlisted", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be pending, shortlisted, or rejected.")
        
    ranking.status = new_status
    
    # If marked as rejected, automatically trigger personalized Rejection Feedback Report
    if new_status == "rejected" and (not ranking.feedback_report or "skill_gaps" not in ranking.feedback_report):
        candidate = db.query(Candidate).filter(Candidate.id == ranking.candidate_id).first()
        job = db.query(Job).filter(Job.id == ranking.job_id).first()
        
        if candidate and job:
            feedback = llm_router.generate_rejection_feedback(
                candidate_profile={
                    "name": candidate.name,
                    "skills": candidate.skills,
                    "experience": candidate.experience
                },
                jd_requirements=job.parsed_requirements or {"extracted_title": job.title, "must_have_skills": [], "summary": job.description}
            )
            # Retain behavioral indicators if present
            fb_report = ranking.feedback_report or {}
            fb_report.update(feedback)
            ranking.feedback_report = fb_report
            
    db.commit()
    db.refresh(ranking)
    
    log_audit(db, current_user.id, f"candidate_{new_status}", ranking.candidate_id, {"job_id": ranking.job_id})
    return ranking

@router.post("/jobs/{job_id}/link/{candidate_id}", status_code=status.HTTP_200_OK)
def link_candidate_to_job(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Link an existing candidate from the general pool to a specific job workspace."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job workspace not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
        
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
        
    ranking = db.query(Ranking).filter(
        Ranking.job_id == job_id,
        Ranking.candidate_id == candidate_id
    ).first()
    
    if not ranking:
        ranking = Ranking(
            job_id=job_id,
            candidate_id=candidate_id,
            score=0.0,
            status="pending"
        )
        db.add(ranking)
        db.commit()
        db.refresh(ranking)
        log_audit(db, current_user.id, "candidate_linked_to_job", candidate_id, {"job_id": job_id})
        
    return {"status": "success", "detail": f"Candidate {candidate.name} linked successfully to job '{job.title}'"}

# --- FEEDBACK ENDPOINTS ---

@router.get("/feedback/{candidate_id}")
def get_candidate_feedback(candidate_id: int, db: Session = Depends(get_db)):
    """Public candidate-facing feedback page. Requires no credentials to let candidates view their report."""
    ranking = db.query(Ranking).filter(Ranking.candidate_id == candidate_id).order_by(Ranking.updated_at.desc()).first()
    if not ranking:
        raise HTTPException(status_code=404, detail="No feedback report found for this candidate.")
        
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    job = db.query(Job).filter(Job.id == ranking.job_id).first()
    
    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidate or Job record missing.")
        
    fb = ranking.feedback_report or {}
    
    return {
        "candidate_name": candidate.name,
        "role_title": job.title,
        "status": ranking.status,
        "feedback_sent": ranking.feedback_sent,
        "skill_gaps": fb.get("skill_gaps", []),
        "improvement_steps": fb.get("improvement_steps", []),
        "time_to_close": fb.get("time_to_close", [])
    }

@router.get("/candidate/{cand_id}")
def get_public_candidate_portal_data(cand_id: int, db: Session = Depends(get_db)):
    """Public candidate-facing portal endpoint to retrieve structured resume evaluation and coaching details."""
    ranking = db.query(Ranking).filter(Ranking.candidate_id == cand_id).order_by(Ranking.updated_at.desc()).first()
    if not ranking:
        raise HTTPException(status_code=404, detail="This link is invalid or has expired")
        
    candidate = db.query(Candidate).filter(Candidate.id == cand_id).first()
    job = db.query(Job).filter(Job.id == ranking.job_id).first()
    
    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidate or Job record missing.")
        
    fb = ranking.feedback_report or {}
    gaps = fb.get("skill_gaps", [])
    
    MAP_METADATA = {
        "fastapi": {
            "why_it_matters": "Core web framework used to build our high-performance backend microservices.",
            "severity": "Advanced needed",
            "task": "Build a scalable REST API with FastAPI, using OAuth2 JWT authentication and custom route dependencies.",
            "task_time": "~3 days",
            "resource": {
                "name": "FastAPI Official Interactive Tutorial Guide",
                "url": "https://fastapi.tiangolo.com/tutorial/",
                "platform": "Docs",
                "duration": "4 hours"
            }
        },
        "sqlalchemy": {
            "why_it_matters": "Our primary ORM for executing optimized, secure database schemas and queries.",
            "severity": "Intermediate needed",
            "task": "Design a relational database model in SQLAlchemy 2.0 with connection pooling and async queries.",
            "task_time": "~2 days",
            "resource": {
                "name": "SQLAlchemy Unified 2.0 ORM Guide & Docs",
                "url": "https://docs.sqlalchemy.org/en/20/tutorial/",
                "platform": "Docs",
                "duration": "6 hours"
            }
        },
        "docker": {
            "why_it_matters": "Standard container tool used to package, run, and scale services consistently across environments.",
            "severity": "Intermediate needed",
            "task": "Containerize a multi-service FastAPI app connected to PostgreSQL using Docker Compose.",
            "task_time": "~3 days",
            "resource": {
                "name": "Docker Containerization Academy Masterclass",
                "url": "https://docs.docker.com/get-started/",
                "platform": "Docs",
                "duration": "3 hours"
            }
        },
        "system design": {
            "why_it_matters": "Critical for designing decoupled, scalable microservices and distributed queue systems under load.",
            "severity": "Advanced needed",
            "task": "Design a distributed job queue system utilizing message brokers and message-passing protocols.",
            "task_time": "~5 days",
            "resource": {
                "name": "The System Design Primer Deep Dive Labs",
                "url": "https://github.com/donnemartin/system-design-primer",
                "platform": "GitHub",
                "duration": "12 hours"
            }
        },
        "postgresql": {
            "why_it_matters": "Our core relational database holding system configurations and structured transactional logs.",
            "severity": "Intermediate needed",
            "task": "Optimize slow database queries by analyzing query plans and introducing indexing/caching.",
            "task_time": "~2 days",
            "resource": {
                "name": "PostgreSQL Database Exercises & Practical Labs",
                "url": "https://pgexercises.com/",
                "platform": "Docs",
                "duration": "5 hours"
            }
        },
        "pinecone": {
            "why_it_matters": "Enables fast semantic query lookups of resume indices for our AI search matches.",
            "severity": "Beginner needed",
            "task": "Build a vector embedding index with metadata filtering using Pinecone or local search cache.",
            "task_time": "~4 days",
            "resource": {
                "name": "Pinecone Vector Indexes Quickstart Academy Guide",
                "url": "https://docs.pinecone.io/docs/quickstart",
                "platform": "Docs",
                "duration": "2 hours"
            }
        }
    }
    
    skill_gaps_compiled = []
    action_plan_compiled = []
    study_resources_compiled = []
    
    for i, gap in enumerate(gaps):
        gap_lower = gap.lower()
        matched_meta = None
        
        for key, value in MAP_METADATA.items():
            if key in gap_lower:
                matched_meta = value
                break
                
        if matched_meta:
            why_it_matters = matched_meta["why_it_matters"]
            severity = matched_meta["severity"]
            task = matched_meta["task"]
            task_time = matched_meta["task_time"]
            res = matched_meta["resource"]
        else:
            why_it_matters = f"Core expertise required to maintain our high engineering and clean architecture standards."
            severity = "Intermediate needed"
            task = f"Develop an end-to-end sandbox project highlighting your deep practical expertise in `{gap}`."
            task_time = "~3 days"
            res = {
                "name": f"Comprehensive {gap.title()} Developer Guide & Docs",
                "url": "https://www.coursera.org/",
                "platform": "Docs",
                "duration": "4 hours"
            }
            
        skill_gaps_compiled.append({
            "name": gap,
            "why_it_matters": why_it_matters,
            "severity": severity
        })
        
        action_plan_compiled.append({
            "task": task,
            "time": task_time
        })
        
        study_resources_compiled.append({
            "name": res["name"],
            "url": res["url"],
            "platform": res["platform"],
            "duration": res["duration"],
            "relevance": gap
        })
        
    if not gaps:
        skill_gaps_compiled = []
        action_plan_compiled = []
        study_resources_compiled = []
        
    return {
        "name": candidate.name,
        "email": candidate.email or "candidate@email.com",
        "role_applied": job.title,
        "fit_score": ranking.score,
        "skill_gaps": skill_gaps_compiled,
        "action_plan": action_plan_compiled,
        "study_resources": study_resources_compiled,
        "rejection_feedback": fb.get("behavioral_indicators", "Demonstrates strong technical capabilities and excellent communication skills."),
        "company_name": "AI Recruiter Workspace Hub",
        "status": ranking.status,
        "date_applied": candidate.created_at.strftime("%B %d, %Y") if candidate.created_at else "May 31, 2026"
    }

@router.put("/rankings/{ranking_id}/feedback", response_model=RankingResponse)
def edit_rejection_feedback(
    ranking_id: int, 
    feedback_in: Dict[str, Any], 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_recruiter)
):
    """Allow recruiter to customize/edit the AI rejection feedback report before dispatching."""
    ranking = db.query(Ranking).filter(Ranking.id == ranking_id).first()
    if not ranking:
        raise HTTPException(status_code=404, detail="Ranking record not found")
        
    job = db.query(Job).filter(Job.id == ranking.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job workspace not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
        
    fb = ranking.feedback_report or {}
    fb["skill_gaps"] = feedback_in.get("skill_gaps", fb.get("skill_gaps", []))
    fb["improvement_steps"] = feedback_in.get("improvement_steps", fb.get("improvement_steps", []))
    fb["time_to_close"] = feedback_in.get("time_to_close", fb.get("time_to_close", []))
    
    ranking.feedback_report = fb
    db.commit()
    db.refresh(ranking)
    
    log_audit(db, current_user.id, "feedback_report_edited", ranking.candidate_id, {"job_id": ranking.job_id})
    return ranking

@router.post("/rankings/{ranking_id}/feedback/send")
def send_rejection_feedback(ranking_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_recruiter)):
    """Mark rejection feedback report as officially sent (e.g. dispatched by email/link)."""
    ranking = db.query(Ranking).filter(Ranking.id == ranking_id).first()
    if not ranking:
        raise HTTPException(status_code=404, detail="Ranking record not found")
        
    job = db.query(Job).filter(Job.id == ranking.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job workspace not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
        
    ranking.feedback_sent = True
    db.commit()
    
    log_audit(db, current_user.id, "feedback_report_sent", ranking.candidate_id, {"job_id": ranking.job_id})
    return {"detail": "Feedback marked as sent."}

# --- AUDIT ENDPOINT ---

@router.get("/audit", response_model=List[AuditLogResponse])
def get_audit_logs(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Retrieve compliance audit logs (restricted to ADMINS only)."""
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()

# --- AUTOMATION & SCREENING ENDPOINTS ---

@router.get("/automation/settings")
def get_settings(current_user: User = Depends(require_recruiter)):
    """Retrieve the current autonomous recruitment mode setting."""
    return {"autonomous_mode": get_automation_mode()}

@router.post("/automation/toggle")
def toggle_settings(
    payload: Dict[str, bool], 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Toggle the master autonomous recruitment flow setting."""
    mode = payload.get("autonomous_mode", False)
    set_automation_mode(mode)
    
    if mode:
        # Retroactively evaluate any pending candidate rankings
        if current_user.role == "admin":
            pending_rankings = db.query(Ranking).filter(Ranking.status == "pending").all()
        else:
            user_job_ids = [j.id for j in db.query(Job).filter(Job.recruiter_id == current_user.id).all()]
            pending_rankings = db.query(Ranking).filter(
                Ranking.status == "pending",
                Ranking.job_id.in_(user_job_ids)
            ).all()
            
        for ranking in pending_rankings:
            candidate = db.query(Candidate).filter(Candidate.id == ranking.candidate_id).first()
            job = db.query(Job).filter(Job.id == ranking.job_id).first()
            if candidate and job:
                # Make dynamic decision
                decision = "shortlisted" if ranking.score >= 65.0 else "rejected"
                ranking.status = decision
                ranking.autonomous_decision = decision
                
                # Check if we have already queued/sent an outreach or rejection for this candidate to avoid duplicates
                existing_logs = db.query(EmailLog).filter(
                    EmailLog.recipient_email == candidate.email,
                    EmailLog.email_type.in_(["outreach", "rejected", "shortlisted"]),
                    EmailLog.sender_user_id == job.recruiter_id
                ).first()
                
                if not existing_logs:
                    if decision == "shortlisted":
                        ranking.interview_status = "scheduled"
                        db.commit()
                        # Dispatch outreach invitation to private screening room
                        schedule_outreach_email(candidate, job, db)
                    else:
                        ranking.interview_status = "not_scheduled"
                        # Generate structured coaching report
                        try:
                            feedback = llm_router.generate_rejection_feedback(
                                candidate_profile={
                                    "name": candidate.name,
                                    "skills": candidate.skills,
                                    "experience": candidate.experience
                                },
                                jd_requirements=job.parsed_requirements or {"extracted_title": job.title, "must_have_skills": [], "summary": job.description}
                            )
                            fb_report = ranking.feedback_report or {}
                            fb_report.update(feedback)
                            ranking.feedback_report = fb_report
                            ranking.feedback_sent = True
                        except Exception as e:
                            print(f"Error generating fallback feedback: {e}")
                        db.commit()
                        
                        # Dispatch rejection email with gaps & links
                        schedule_rejection_email(candidate, job, db)
    return {"autonomous_mode": mode}

@router.get("/automation/outbox")
def get_outbox(db: Session = Depends(get_db), current_user: User = Depends(require_recruiter)):
    """Retrieve all simulated email log dispatch history for outbox visualization."""
    # Run a quick sweep to keep timeline records accurate
    sweep_queued_emails(db)
    if current_user.role == "admin":
        return db.query(EmailLog).order_by(EmailLog.created_at.desc()).all()
    return db.query(EmailLog).filter(EmailLog.sender_user_id == current_user.id).order_by(EmailLog.created_at.desc()).all()

@router.post("/interviews/override/{ranking_id}")
def override_autonomous_decision(
    ranking_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_recruiter)
):
    """Safety Intercept Override: Halt email dispatch and flag candidate for manual review."""
    ranking = db.query(Ranking).filter(Ranking.id == ranking_id).first()
    if not ranking:
        raise HTTPException(status_code=404, detail="Ranking record not found")
        
    job = db.query(Job).filter(Job.id == ranking.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job workspace not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")

    success = trigger_safety_override(ranking_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Ranking or candidate record not found")
    
    log_audit(db, current_user.id, "safety_override_triggered", ranking_id, {"status": "manual_review"})
    return {"status": "success", "message": "Autonomous decision overridden. Email dispatch cancelled."}

@router.get("/interviews/results/{job_id}")
def get_interviews_results(
    job_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_recruiter)
):
    """Retrieve completed interview transcripts and detailed AI scoring metrics for recruiters."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job workspace not found")
    if current_user.role != "admin" and job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this job workspace")
        
    return db.query(Interview).filter(Interview.job_id == job_id).all()

# --- CONVERSATIONAL AI INTERVIEW SCREENING WEBSOCKET ---

def is_valid_introduction(text: str) -> bool:
    """Helper to check if the candidate's introduction response is proper or too short/simple greeting."""
    cleaned = text.strip().lower()
    # If the response is extremely short (e.g. less than 40 chars) or only contains basic greeting words
    if len(cleaned) < 40:
        return False
    greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yes", "ok", "okay", "test", "hi sir", "hello sir", "hello there"}
    if cleaned in greetings:
        return False
    return True

@router.websocket("/interviews/chat/{cand_id}/{job_id}")
async def conversational_screening_websocket(websocket: WebSocket, cand_id: int, job_id: int):
    """Real-time candidate screening interview room via WebSockets with character-by-character streaming."""
    await websocket.accept()
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter(Candidate.id == cand_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not candidate or not job:
            await websocket.send_json({"error": "Candidate or Job Workspace not found"})
            await websocket.close()
            return
            
        # Get or create interview record
        interview = db.query(Interview).filter(
            Interview.candidate_id == cand_id, 
            Interview.job_id == job_id
        ).first()
        
        if not interview:
            interview = Interview(
                candidate_id=cand_id,
                job_id=job_id,
                status="scheduled",
                transcript=[]
            )
            db.add(interview)
            db.commit()
            db.refresh(interview)
            
        ranking = db.query(Ranking).filter(
            Ranking.job_id == job_id, 
            Ranking.candidate_id == cand_id
        ).first()
        
        if ranking:
            ranking.interview_status = "in_progress"
            db.commit()
            
        # 1. STEP 1: INTRO
        intro_q = llm_router.generate_interview_response(
            candidate_name=candidate.name,
            job_title=job.title,
            step=1,
            conversation_history=[],
            candidate_answer=""
        )
        # Stream intro question
        await websocket.send_json({"step": 1, "sender": "ai", "stream_start": True})
        for char in intro_q:
            await websocket.send_json({"char": char})
            await asyncio.sleep(0.01)
        await websocket.send_json({"stream_end": True})
        
        # Wait for candidate response
        cand_resp1 = await websocket.receive_text()
        
        # Enforce all 7 items of the introduction loop
        accumulated_intro_text = cand_resp1
        current_intro_q = intro_q
        
        analysis = llm_router.analyze_introduction(candidate.name, job.title, accumulated_intro_text)
        
        while not analysis.get("completed", False):
            followup_q = analysis.get("next_question", "Please provide more details on the remaining items.")
            
            # Stream the follow-up request
            await websocket.send_json({"step": 1, "sender": "ai", "stream_start": True})
            for char in followup_q:
                await websocket.send_json({"char": char})
                await asyncio.sleep(0.01)
            await websocket.send_json({"stream_end": True})
            
            # Record the intermediate attempt in the transcript
            tx = list(interview.transcript or [])
            tx.append({"role": "ai", "text": current_intro_q})
            tx.append({"role": "candidate", "text": cand_resp1})
            interview.transcript = tx
            db.commit()
            
            current_intro_q = followup_q
            # Wait for next response
            cand_resp1 = await websocket.receive_text()
            accumulated_intro_text += "\n" + cand_resp1
            
            # Re-analyze with the accumulated text
            analysis = llm_router.analyze_introduction(candidate.name, job.title, accumulated_intro_text)
            
        tx = list(interview.transcript or [])
        tx.append({"role": "ai", "text": current_intro_q})
        tx.append({"role": "candidate", "text": cand_resp1})
        interview.transcript = tx
        db.commit()
        
        # Overwrite cand_resp1 to be the full accumulated introduction so the rest of the pipeline gets all details
        cand_resp1 = accumulated_intro_text

        # 2. STEP 2: BEHAVIORAL
        behave_q = llm_router.generate_interview_response(
            candidate_name=candidate.name,
            job_title=job.title,
            step=2,
            conversation_history=[{"role": "ai", "text": intro_q}],
            candidate_answer=cand_resp1
        )
        # Stream behavioral question
        await websocket.send_json({"step": 2, "sender": "ai", "stream_start": True})
        for char in behave_q:
            await websocket.send_json({"char": char})
            await asyncio.sleep(0.01)
        await websocket.send_json({"stream_end": True})
        
        # Wait for candidate response
        cand_resp2 = await websocket.receive_text()
        tx = list(interview.transcript or [])
        tx.append({"role": "ai", "text": behave_q})
        tx.append({"role": "candidate", "text": cand_resp2})
        interview.transcript = tx
        db.commit()
        
        # 3. STEP 3: TECHNICAL
        tech_q = llm_router.generate_interview_response(
            candidate_name=candidate.name,
            job_title=job.title,
            step=3,
            conversation_history=[
                {"role": "ai", "text": intro_q},
                {"role": "candidate", "text": cand_resp1},
                {"role": "ai", "text": behave_q}
            ],
            candidate_answer=cand_resp2
        )
        # Stream technical question
        await websocket.send_json({"step": 3, "sender": "ai", "stream_start": True})
        for char in tech_q:
            await websocket.send_json({"char": char})
            await asyncio.sleep(0.01)
        await websocket.send_json({"stream_end": True})
        
        # Wait for candidate response
        cand_resp3 = await websocket.receive_text()
        tx = list(interview.transcript or [])
        tx.append({"role": "ai", "text": tech_q})
        tx.append({"role": "candidate", "text": cand_resp3})
        interview.transcript = tx
        db.commit()
        
        # 4. WRAP-UP & ASSESS
        closing = llm_router.generate_interview_response(
            candidate_name=candidate.name,
            job_title=job.title,
            step=4,
            conversation_history=[
                {"role": "ai", "text": intro_q},
                {"role": "candidate", "text": cand_resp1},
                {"role": "ai", "text": behave_q},
                {"role": "candidate", "text": cand_resp2},
                {"role": "ai", "text": tech_q}
            ],
            candidate_answer=cand_resp3
        )
        # Stream closing message
        await websocket.send_json({"step": 4, "sender": "ai", "stream_start": True})
        for char in closing:
            await websocket.send_json({"char": char})
            await asyncio.sleep(0.01)
        await websocket.send_json({"stream_end": True})
        
        # Calculate AI metrics dynamically based on vocabulary depth and proctoring logs
        total_chars = len(cand_resp1) + len(cand_resp2) + len(cand_resp3)
        avg_resp_len = total_chars / 3.0
        
        # 1. Confidence Evaluation based on professional vocabulary
        confident_keywords = ["designed", "resolved", "optimized", "implemented", "scaled", "led", "architecture", "built", "debugged", "fixed", "responsible", "created"]
        hesitant_keywords = ["don't know", "unsure", "maybe", "probably", "i think", "not sure", "guess"]
        
        all_resps_lower = (cand_resp1 + " " + cand_resp2 + " " + cand_resp3).lower()
        conf_matches = sum(3.0 for kw in confident_keywords if kw in all_resps_lower)
        hes_penalty = sum(4.0 for kw in hesitant_keywords if kw in all_resps_lower)
        
        confidence_score = min(max(60.0 + conf_matches - hes_penalty + (total_chars / 35.0), 40.0), 99.0)
        
        # Proctoring warning penalty: reduce confidence score slightly for multiple cheating signs/tab switches
        proctoring_count = len(interview.proctoring_alerts or [])
        if proctoring_count > 0:
            confidence_score = max(confidence_score - (proctoring_count * 5.0), 30.0)
            
        # 2. Communication Evaluation based on responsiveness depth
        communication_score = min(max(50.0 + (avg_resp_len / 5.0), 35.0), 98.0)
        
        # 3. Technical Evaluation based on relevant technology keywords
        tech_keywords = ["fastapi", "sqlalchemy", "python", "postgres", "docker", "aws", "scale", "query", "cache", "index", "async", "await", "concurrency", "lock", "redis", "celery", "migration", "orm"]
        tech_matches = sum(3.5 for kw in tech_keywords if kw in all_resps_lower)
        technical_score = min(max(45.0 + tech_matches, 30.0), 99.0)
        
        interview.status = "completed"
        interview.confidence_score = round(confidence_score, 1)
        interview.communication_score = round(communication_score, 1)
        interview.technical_score = round(technical_score, 1)
        interview.completed_at = datetime.utcnow()
        
        # Formulate AI summary showing proctoring status
        proctor_text = "Clean proctoring log with no active flags."
        if interview.cheating_suspected:
            proctor_text = f"WARNING: Proctoring flag active ({proctoring_count} tab/window switches detected during proctored session)."
            
        interview.ai_summary = (
            f"The candidate exhibited dynamic communication proficiency ({round(communication_score, 1)}%) "
            f"and technical capability score of {round(technical_score, 1)}%. Confidence verified at {round(confidence_score, 1)}%. "
            f"Proctoring Status: {proctor_text}"
        )
        db.commit()
        
        # Execute decision maker & queue email notifications automatically with 5-minute buffer!
        evaluate_interview(interview, db)
        
    except WebSocketDisconnect:
        print(f"Candidate {cand_id} disconnected from screening interview room.")
    except Exception as e:
        print(f"Error during WebSocket conversational interview session: {e}")
        try:
            await websocket.send_json({"error": "An internal server error occurred."})
        except:
            pass
    finally:
        db.close()


@router.post("/interviews/proctor/warning/{cand_id}/{job_id}")
def record_proctoring_warning(
    cand_id: int,
    job_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Record a browser tab switch or focus loss warning in the interview session logs."""
    interview = db.query(Interview).filter(
        Interview.candidate_id == cand_id,
        Interview.job_id == job_id
    ).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found")
        
    warning_type = payload.get("type", "tab_switch")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    alerts = list(interview.proctoring_alerts or [])
    alerts.append({"type": warning_type, "timestamp": timestamp})
    
    interview.proctoring_alerts = alerts
    interview.cheating_suspected = True
    
    db.commit()
    return {"status": "success", "warnings_count": len(alerts)}
