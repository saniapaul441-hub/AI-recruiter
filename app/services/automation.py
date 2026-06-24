import os
import json
import datetime
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from app.models.core import Ranking, Interview, EmailLog, Candidate, Job
from app.config import settings

def send_smtp_email(to_email: str, subject: str, body: str, config_user=None, email_log_id: int = None):
    """Deliver an actual email to recipient using custom recruiter SMTP settings or fallback global settings."""
    from app.models.auth import User
    
    smtp_configured = False
    host, port, user, password, sender = None, 587, None, None, None
    
    # 1. Try recruiter-specific credentials if user is provided
    if config_user and config_user.smtp_host and config_user.smtp_username and config_user.smtp_password:
        host = config_user.smtp_host
        port = config_user.smtp_port or 587
        user = config_user.smtp_username
        password = config_user.smtp_password
        sender = config_user.smtp_from or user
        smtp_configured = True
        print(f"Using recruiter-specific SMTP credentials ({user}) for {to_email}")
    else:
        # Fallback: Query database for first user with custom SMTP credentials configured
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            db_recruiter = db.query(User).filter(
                User.smtp_host.isnot(None),
                User.smtp_username.isnot(None),
                User.smtp_password.isnot(None)
            ).first()
            if db_recruiter:
                host = db_recruiter.smtp_host
                port = db_recruiter.smtp_port or 587
                user = db_recruiter.smtp_username
                password = db_recruiter.smtp_password
                sender = db_recruiter.smtp_from or user
                smtp_configured = True
                print(f"Using database fallback SMTP credentials ({user}) for {to_email}")
            db.close()
        except Exception as db_err:
            print(f"Failed to query database fallback SMTP credentials: {db_err}")

    # 2. Fall back to global configuration if database lookup yielded nothing
    if not smtp_configured:
        host = settings.SMTP_HOST
        port = settings.SMTP_PORT or 587
        user = settings.SMTP_USER
        password = settings.SMTP_PASSWORD
        sender = settings.SMTP_FROM or user
        print(f"Using global SMTP fallback for {to_email}")

    success = False
    try:
        if not host or not user or not password:
            print(f"SMTP not configured. Skipping real email dispatch to {to_email}.")
            raise ValueError("SMTP host, username, or password is not configured.")
        if "your-email" in user or "your-gmail" in password:
            print(f"SMTP is configured with placeholder values. Skipping real email dispatch to {to_email}.")
            raise ValueError("SMTP contains placeholder configuration values.")
            
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(host, port, timeout=10)
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        print(f"SUCCESS: SMTP email delivered to {to_email}")
        success = True
    except Exception as e:
        print(f"ERROR: Failed to deliver SMTP email to {to_email}: {e}")
        success = False

    if email_log_id:
        try:
            from app.database import SessionLocal
            from app.models.core import EmailLog
            db = SessionLocal()
            email_log = db.query(EmailLog).filter(EmailLog.id == email_log_id).first()
            if email_log:
                email_log.status = "sent" if success else "failed"
                db.commit()
            db.close()
        except Exception as db_err:
            print(f"Failed to update EmailLog {email_log_id} status: {db_err}")
            
    return success

def send_smtp_email_async(to_email: str, subject: str, body: str, config_user=None, email_log_id: int = None):
    """Dispatch SMTP email asynchronously on a background thread."""
    thread = threading.Thread(target=send_smtp_email, args=(to_email, subject, body, config_user, email_log_id))
    thread.daemon = True
    thread.start()

SETTINGS_FILE = "automation_settings.json"

def get_automation_mode() -> bool:
    """Read the current autonomous mode setting from persistent store."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                return bool(data.get("autonomous_mode", False))
    except Exception as e:
        print(f"Error loading automation settings: {e}")
    return False

def set_automation_mode(mode: bool):
    """Write the autonomous mode setting to persistent store."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"autonomous_mode": mode}, f)
    except Exception as e:
        print(f"Error saving automation settings: {e}")

def schedule_outreach_email(candidate: Candidate, job: Job, db: Session) -> EmailLog:
    """Schedule and log automated outreach with a custom link to the AI Screening Room."""
    subject = f"AI Recruiter - Interview Screening Invitation for {job.title}"
    
    screening_link = f"/static/screening.html?cand_id={candidate.id}&job_id={job.id}"
    
    body = (
        f"Hi {candidate.name},\n\n"
        f"Thank you for applying to the {job.title} role! We are impressed by your background.\n\n"
        f"As the first step in our recruitment process, we invite you to our AI-driven Conversational "
        f"Screening Portal. The screening will take about 10 minutes, where our conversational recruiter "
        f"will assess your technical, communication, and behavioral alignment.\n\n"
        f"Please click the link below to enter your private screening room:\n"
        f"👉 http://localhost:8000{screening_link}\n\n"
        f"To view your real-time application tracker and feedback dashboard at any time, visit:\n"
        f"👉 http://localhost:8000/static/portal.html?cand_id={candidate.id}\n\n"
        f"Best regards,\n"
        f"Talent Acquisition Team\n"
        f"AI Recruiter Automated Portal"
    )
    
    outreach = EmailLog(
        recipient_email=candidate.email or "candidate@email.com",
        subject=subject,
        body=body,
        email_type="outreach",
        status="queued",  # Queued/sending initially
        sender_user_id=job.recruiter_id,
        sent_at=datetime.datetime.utcnow()
    )
    db.add(outreach)
    db.commit()
    db.refresh(outreach)
    
    # Send actual email if configured
    if candidate.email and "@" in candidate.email and "candidate@email.com" not in candidate.email:
        from app.models.auth import User
        recruiter = None
        if job.recruiter_id:
            recruiter = db.query(User).filter(User.id == job.recruiter_id).first()
        send_smtp_email_async(candidate.email, subject, body, config_user=recruiter, email_log_id=outreach.id)
    else:
        outreach.status = "skipped"
        db.commit()
        
    return outreach

def schedule_rejection_email(candidate: Candidate, job: Job, db: Session) -> EmailLog:
    """Schedule and log automated rejection email with custom, gaps-bridging feedback recommendations."""
    subject = f"Hiring Update: Rejection Feedback for {job.title}"
    body = compile_hyper_personalized_rejection(candidate, job)
    
    rejection = EmailLog(
        recipient_email=candidate.email or "candidate@email.com",
        subject=subject,
        body=body,
        email_type="rejected",
        status="queued",  # Queued/sending initially
        sender_user_id=job.recruiter_id,
        sent_at=datetime.datetime.utcnow()
    )
    db.add(rejection)
    db.commit()
    db.refresh(rejection)
    
    # Send actual email if configured
    if candidate.email and "@" in candidate.email and "candidate@email.com" not in candidate.email:
        from app.models.auth import User
        recruiter = None
        if job.recruiter_id:
            recruiter = db.query(User).filter(User.id == job.recruiter_id).first()
        send_smtp_email_async(candidate.email, subject, body, config_user=recruiter, email_log_id=rejection.id)
    else:
        rejection.status = "skipped"
        db.commit()
        
    return rejection

def compile_hyper_personalized_rejection(candidate: Candidate, job: Job, interview: Interview = None) -> str:
    """Compile highly specific, gaps-bridging rejection feedback referencing technical gaps and study/project links."""
    # Analyze missing technical skills based on Heatmap and JD requirements
    jd_reqs = job.parsed_requirements or {}
    must_skills = [s.lower().strip() for s in jd_reqs.get("must_have_skills", [])]
    cand_skills = [s.lower().strip() for s in (candidate.skills or [])]
    
    missing_skills = [s for s in must_skills if s not in cand_skills]
    
    # Study Links Mapping
    resources = {
        "fastapi": "[FastAPI Official Tutorial & Building Web APIs](https://fastapi.tiangolo.com/tutorial/)",
        "sqlalchemy": "[SQLAlchemy Unified 2.0 ORM Guide](https://docs.sqlalchemy.org/en/20/tutorial/)",
        "python": "[Real Python Developer Learning Paths](https://realpython.com/)",
        "system design": "[The System Design Primer Deep Dive](https://github.com/donnemartin/system-design-primer)",
        "docker": "[Docker Containerization & Dev Environments Academy](https://docs.docker.com/get-started/)",
        "aws": "[AWS Developer Fundamentals Portal](https://aws.amazon.com/developer/learning/)",
        "postgresql": "[SQL Database Exercises & Schema Designs](https://pgexercises.com/)",
        "pinecone": "[Pinecone Vector Indexes Quickstart Academy](https://docs.pinecone.io/docs/quickstart)"
    }
    
    # Find matching resources
    study_recommendations = []
    project_suggestion = "Build a comprehensive web application."
    
    if missing_skills:
        for skill in missing_skills[:2]:
            matched_res = None
            for key, val in resources.items():
                if key in skill:
                    matched_res = val
                    break
            if matched_res:
                study_recommendations.append(f"- **{skill.title()}**: {matched_res}")
            else:
                study_recommendations.append(f"- **{skill.title()}**: [Coursera Software Engineering Learning Paths](https://www.coursera.org/)")
                
        # Propose custom gap-bridging project
        primary_gap = missing_skills[0].title()
        if "docker" in primary_gap.lower() or "fastapi" in primary_gap.lower():
            project_suggestion = (
                "Develop an end-to-end REST API using FastAPI. Pack it inside a Docker container, connect "
                "it to a local PostgreSQL container using Docker Compose, and write integration tests. This will "
                "directly demonstrate backend system design and containerization skills required for this role."
            )
        elif "system design" in primary_gap.lower() or "leadership" in primary_gap.lower():
            project_suggestion = (
                "Design a distributed message queue system on paper, and write a Python implementation using "
                "multiprocessing and message brokers. Document the architecture choices in a README, focusing on scaling, "
                "fault tolerance, and state partitioning."
            )
        else:
            project_suggestion = (
                f"Create a hands-on project incorporating `{primary_gap}`. Build a working Github repository, document the "
                f"architectural structure, and publish a short video demonstrating your engineering design choices."
            )
    else:
        study_recommendations.append("- **General Scaling**: [Google Cloud/AWS Architecture Blueprints](https://aws.amazon.com/architecture/)")
        project_suggestion = (
            "Build high-throughput microservices showing advanced database connection pooling, thread optimizations, "
            "and load balancing configurations."
        )
        
    study_links_str = "\n".join(study_recommendations)
    
    body = (
        f"Hi {candidate.name},\n\n"
        f"Thank you for taking the time to complete the AI-driven screening round for the {job.title} workspace. "
        f"We appreciate your focus and participation.\n\n"
        f"After analyzing your conversational answers, confidence patterns, and technical skills comparison, we are "
        f"unable to advance your application at this time. However, our AI Recruiter has compiled highly specific, "
        f"constructive growth recommendations to help you close your technical gaps:\n\n"
        f"🎯 IDENTIFIED TECHNICAL GAPS & STUDY BRIDGES:\n"
        f"{study_links_str}\n\n"
        f"🛠️ RECOMMENDATION PROJECT FOR YOUR PORTFOLIO:\n"
        f"{project_suggestion}\n\n"
        f"🎯 VIEW YOUR DYNAMIC FEEDBACK & COACHING PORTAL:\n"
        f"👉 http://localhost:8000/static/portal.html?cand_id={candidate.id}\n\n"
        f"We wish you all the best in your career growth and thank you again for your interest in our team!\n\n"
        f"Sincerely,\n"
        f"Talent Acquisition & AI Coaching Team\n"
        f"AI Recruiter Autonomous Portal"
    )
    return body

def evaluate_interview(interview: Interview, db: Session) -> EmailLog:
    """Perform autonomous decision matching, queue corresponding email with a 5-minute safety buffer."""
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    job = db.query(Job).filter(Job.id == interview.job_id).first()
    ranking = db.query(Ranking).filter(Ranking.job_id == interview.job_id, Ranking.candidate_id == interview.candidate_id).first()
    
    if not candidate or not job or not ranking:
        print("Required entities not found. Cannot evaluate interview.")
        return None
        
    # Calculate overall candidate score
    overall_score = round((interview.confidence_score + interview.communication_score + interview.technical_score) / 3.0, 1)
    
    # Make autonomous decision
    decision = "shortlisted" if overall_score >= 65.0 else "rejected"
    
    # Update ranking details in database
    ranking.score = overall_score
    ranking.sub_scores = {
        "experience": interview.technical_score,  # Map metrics
        "skills": interview.communication_score,
        "leadership": interview.confidence_score
    }
    ranking.autonomous_decision = decision
    ranking.status = decision
    ranking.interview_status = "completed"
    
    # 15-second delay interception window for instant live dashboard demo!
    dispatch_delay = datetime.timedelta(seconds=15)
    target_time = datetime.datetime.utcnow() + dispatch_delay
    
    # Compile corresponding email
    if decision == "shortlisted":
        subject = f"Congratulations! Next Steps for the {job.title} role"
        body = (
            f"Hi {candidate.name},\n\n"
            f"We are thrilled to share that you have successfully cleared our AI Conversational Screening round "
            f"for the {job.title} workspace with an overall score of {overall_score}%!\n\n"
            f"Our autonomous recruitment system has logged excellent scores across your profile:\n"
            f" - Confidence & Initiative: {interview.confidence_score}%\n"
            f" - Communication & Conversation: {interview.communication_score}%\n"
            f" - Role Technology Fit: {interview.technical_score}%\n\n"
            f"Our hiring manager will reach out within 24 hours to schedule your deep-dive systems architecture panel.\n\n"
            f"Congratulations on advancing to the next round!\n\n"
            f"Best regards,\n"
            f"Talent Acquisition & Hiring Team"
        )
    else:
        subject = f"Hiring Update: Rejection Feedback for {job.title}"
        body = compile_hyper_personalized_rejection(candidate, job, interview)
        
    # Create the queued EmailLog
    email_log = EmailLog(
        recipient_email=candidate.email or "candidate@email.com",
        subject=subject,
        body=body,
        email_type=decision,
        status="queued",
        sender_user_id=job.recruiter_id,
        sent_at=target_time
    )
    
    db.add(email_log)
    db.commit()
    db.refresh(email_log)
    
    # Store dynamic pros/cons based on interview scores for dashboard visual consistency
    ranking.pros = [
        f"Excelled in screening round with a {interview.communication_score}% communication score.",
        f"Demonstrated high confidence and initiative ({interview.confidence_score}%) during questions.",
        "Possesses clear alignment with requested workflow specifications."
    ]
    ranking.cons = [
        "Needs deep structural practice project implementation.",
        f"Scored {interview.technical_score}% on detailed tech/role questions.",
        "Identified potential learning areas in edge-case system design concepts."
    ]
    
    db.commit()
    return email_log

def trigger_safety_override(ranking_id: int, db: Session) -> bool:
    """Execute Safety Override: Halt queued dispatches and flip status to manual review."""
    ranking = db.query(Ranking).filter(Ranking.id == ranking_id).first()
    if not ranking:
        return False
        
    candidate = db.query(Candidate).filter(Candidate.id == ranking.candidate_id).first()
    if not candidate:
        return False
        
    # Flip database statuses
    ranking.autonomous_decision = "manual_review"
    ranking.status = "pending"
    ranking.interview_status = "completed"
    
    # Intercept and cancel all queued email logs for this candidate
    queued_emails = db.query(EmailLog).filter(
        EmailLog.recipient_email == candidate.email,
        EmailLog.status == "queued"
    ).all()
    
    for email in queued_emails:
        email.status = "intercepted"
        
    db.commit()
    return True

def sweep_queued_emails(db: Session):
    """Scan and dispatch queued emails whose 5-minute buffer has expired."""
    now = datetime.datetime.utcnow()
    expired_emails = db.query(EmailLog).filter(
        EmailLog.status == "queued",
        EmailLog.sent_at <= now
    ).all()
    
    from app.models.auth import User
    for email in expired_emails:
        email.status = "sending"
        recruiter = None
        if email.sender_user_id:
            recruiter = db.query(User).filter(User.id == email.sender_user_id).first()
            
        if email.recipient_email and "@" in email.recipient_email and "candidate@email.com" not in email.recipient_email:
            send_smtp_email_async(email.recipient_email, email.subject, email.body, config_user=recruiter, email_log_id=email.id)
        else:
            email.status = "skipped"
        
    if expired_emails:
        db.commit()
