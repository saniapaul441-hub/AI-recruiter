import os
from app.services.parser import ResumeParserService
from app.services.llm_router import llm_router
from app.utils.security import get_password_hash, verify_password, create_access_token, decode_access_token

def test_security_helpers():
    """Verify password hashing and JWT validation operates securely."""
    password = "super-secret-password-123"
    hashed = get_password_hash(password)
    
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False
    
    # Verify JWT tokens
    subject = "recruiter@recruiter.com"
    token = create_access_token(subject=subject, role="recruiter")
    
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == subject
    assert decoded["role"] == "recruiter"

def test_csv_parser():
    """Verify CSV candidates sheet parsing extracts rows and structures fields correctly."""
    csv_content = (
        "name,email,phone,skills,experience,education\n"
        "John Doe,john.doe@test.com,555-1234,\"Python, FastAPI, AWS\",Senior Dev at Google,BS CS from MIT\n"
        "Jane Smith,jane.smith@test.com,555-5678,\"React, CSS\",Frontend Dev at Meta,BA Design from RISD\n"
    )
    
    parsed = ResumeParserService.parse_csv(csv_content.encode('utf-8'))
    
    assert len(parsed) == 2
    
    assert parsed[0]["name"] == "John Doe"
    assert parsed[0]["email"] == "john.doe@test.com"
    assert parsed[0]["phone"] == "555-1234"
    assert "Python" in parsed[0]["skills"]
    assert "FastAPI" in parsed[0]["skills"]
    assert parsed[0]["experience_raw"] == "Senior Dev at Google"
    
    assert parsed[1]["name"] == "Jane Smith"
    assert "React" in parsed[1]["skills"]

def test_contact_extractor():
    """Verify regex-based contact info extraction from messy resume strings."""
    resume_text = (
        "Curriculum Vitae\n"
        "Alex Mercer\n"
        "Contact: alex.mercer@gmail.com | +1 (555) 123-4567\n"
        "Summary:\n"
        "A senior backend engineer with deep python experience..."
    )
    
    contact = ResumeParserService.extract_contact_info(resume_text)
    
    assert contact["email"] == "alex.mercer@gmail.com"
    assert contact["phone"] == "+1 (555) 123-4567"
    assert contact["name"] == "Alex Mercer"

def test_jd_deconstructor_fallback():
    """Verify JD intent extraction operates reliably with local fallbacks."""
    jd_text = (
        "Lead Python Developer. Requirements: 5 years experience, FastAPI, PostgreSQL, Docker."
    )
    
    reqs = llm_router.deconstruct_jd(jd_text)
    
    assert "must_have_skills" in reqs
    assert "nice_to_have_skills" in reqs
    assert "experience_level" in reqs
    assert isinstance(reqs["must_have_skills"], list)
    assert isinstance(reqs["nice_to_have_skills"], list)

def test_workspace_isolation():
    """Verify that recruiters can only see and manage their own jobs/candidates and email logs."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base, get_db
    from app.main import app
    from app.models.core import Job, Ranking, EmailLog, Candidate
    from app.models.auth import User

    # 1. Setup fresh test DB
    TEST_DB_URL = "sqlite:///./test_recruiter_isolation.db"
    test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        # 2. Register Recruiter A & B
        client.post("/api/auth/register", json={"email": "rec_a@test.com", "password": "password123", "full_name": "Recruiter A", "role": "recruiter"})
        client.post("/api/auth/register", json={"email": "rec_b@test.com", "password": "password123", "full_name": "Recruiter B", "role": "recruiter"})

        # 3. Log in both recruiters
        login_a = client.post("/api/auth/login", json={"email": "rec_a@test.com", "password": "password123"}).json()
        login_b = client.post("/api/auth/login", json={"email": "rec_b@test.com", "password": "password123"}).json()

        token_a = login_a["access_token"]
        token_b = login_b["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 4. Recruiter A creates a job
        job_resp = client.post("/api/jobs", json={"title": "Python Dev", "description": "FastAPI backend"}, headers=headers_a)
        assert job_resp.status_code == 201
        job_id = job_resp.json()["id"]

        # 5. Recruiter B tries to get Recruiter A's job description -> should be 403 Forbidden
        get_resp = client.get(f"/api/jobs/{job_id}", headers=headers_b)
        assert get_resp.status_code == 403

        # 6. Recruiter B tries to delete Recruiter A's job description -> should be 403 Forbidden
        del_resp = client.delete(f"/api/jobs/{job_id}", headers=headers_b)
        assert del_resp.status_code == 403

        # 7. Recruiter B tries to upload candidates for Recruiter A's job workspace -> should be 403 Forbidden
        # Using a dummy CSV text file as resume upload
        import io
        dummy_file = io.BytesIO(b"name,email,phone,skills,experience,education\nJane,jane@test.com,12345,Python,Senior,BS\n")
        upload_resp = client.post(
            "/api/candidates/upload",
            headers={**headers_b, "x-job-id": str(job_id)},
            files=[("files", ("john.csv", dummy_file, "text/csv"))]
        )
        assert upload_resp.status_code == 403

        # 8. Recruiter A uploads a candidate (which links to their own job workspace) -> should be 201 Created
        dummy_file_a = io.BytesIO(b"name,email,phone,skills,experience,education\nJohn,john@test.com,12345,Python,Senior,BS\n")
        upload_resp_a = client.post(
            "/api/candidates/upload",
            headers={**headers_a, "x-job-id": str(job_id)},
            files=[("files", ("john.csv", dummy_file_a, "text/csv"))]
        )
        assert upload_resp_a.status_code == 201
        candidate_id = upload_resp_a.json()[0]["id"]

        # Let's verify recruiter B cannot access this candidate's profile
        cand_resp_b = client.get(f"/api/candidates/{candidate_id}", headers=headers_b)
        assert cand_resp_b.status_code == 403

        # Let's verify recruiter A can access this candidate's profile
        cand_resp_a = client.get(f"/api/candidates/{candidate_id}", headers=headers_a)
        assert cand_resp_a.status_code == 200

        # 9. Recruiter B tries to link this candidate to Recruiter A's job -> should be 403 Forbidden
        link_resp = client.post(f"/api/jobs/{job_id}/link/{candidate_id}", headers=headers_b)
        assert link_resp.status_code == 403

        # Get ranking ID for the candidate
        db = TestSessionLocal()
        ranking = db.query(Ranking).filter(Ranking.job_id == job_id, Ranking.candidate_id == candidate_id).first()
        ranking_id = ranking.id
        db.close()

        # 10. Recruiter B tries to update candidate status -> should be 403 Forbidden
        status_resp = client.put(f"/api/rankings/{ranking_id}/status", json={"status": "shortlisted"}, headers=headers_b)
        assert status_resp.status_code == 403

        # 11. Recruiter B tries to edit candidate feedback -> should be 403 Forbidden
        fb_resp = client.put(f"/api/rankings/{ranking_id}/feedback", json={"skill_gaps": ["Python"]}, headers=headers_b)
        assert fb_resp.status_code == 403

        # 12. Recruiter B tries to send candidate feedback -> should be 403 Forbidden
        fb_send_resp = client.post(f"/api/rankings/{ranking_id}/feedback/send", headers=headers_b)
        assert fb_send_resp.status_code == 403

        # 13. Recruiter B tries to override autonomous decision -> should be 403 Forbidden
        override_resp = client.post(f"/api/interviews/override/{ranking_id}", headers=headers_b)
        assert override_resp.status_code == 403

        # 14. Recruiter B tries to get interview results -> should be 403 Forbidden
        results_resp = client.get(f"/api/interviews/results/{job_id}", headers=headers_b)
        assert results_resp.status_code == 403

        # 15. Verify get_outbox isolates email logs by sender
        # Let's insert a mocked email log for recruiter A (user_id=1) and recruiter B (user_id=2)
        db = TestSessionLocal()
        email_a = EmailLog(recipient_email="test_a@test.com", subject="Sub A", body="Body A", email_type="outreach", sender_user_id=1, status="sent")
        email_b = EmailLog(recipient_email="test_b@test.com", subject="Sub B", body="Body B", email_type="outreach", sender_user_id=2, status="sent")
        db.add(email_a)
        db.add(email_b)
        db.commit()
        db.close()

        # Recruiter A calls get_outbox -> should see email_a, not email_b
        outbox_a = client.get("/api/automation/outbox", headers=headers_a).json()
        assert len(outbox_a) == 1
        assert outbox_a[0]["recipient_email"] == "test_a@test.com"

        # Recruiter B calls get_outbox -> should see email_b, not email_a
        outbox_b = client.get("/api/automation/outbox", headers=headers_b).json()
        assert len(outbox_b) == 1
        assert outbox_b[0]["recipient_email"] == "test_b@test.com"

    finally:
        # Cleanup
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
        if os.path.exists("./test_recruiter_isolation.db"):
            try:
                os.remove("./test_recruiter_isolation.db")
            except Exception as e:
                print(f"Warning: could not remove test db file: {e}")
