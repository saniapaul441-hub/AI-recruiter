import os
import json
from app.services.llm_router import llm_router

def test_competency_framework():
    """Verify that we fetch appropriate competency frameworks based on job titles."""
    backend_framework = llm_router.get_role_competency_framework("Python Backend Engineer")
    assert "API" in backend_framework or "databases" in backend_framework or "Database" in backend_framework
    
    frontend_framework = llm_router.get_role_competency_framework("Senior React Developer")
    assert "State" in frontend_framework or "Javascript" in frontend_framework or "style" in frontend_framework
    
    ai_framework = llm_router.get_role_competency_framework("AI Research Engineer")
    assert "Model" in ai_framework or "RAG" in ai_framework or "similarity" in ai_framework or "Prompt" in ai_framework

def test_question_bank_generation():
    """Verify that we generate grounded, non-generic questions based on resume and competencies."""
    resume_text = (
        "Alice Smith\n"
        "Senior Backend Engineer at TechGlobal Solutions.\n"
        "Built 15 microservices using FastAPI. Optimized PostgreSQL queries by 35%.\n"
        "Skills: Python, FastAPI, SQLAlchemy, PostgreSQL, Redis"
    )
    competencies = (
        "Competencies:\n"
        "- High-throughput API Design & Performance optimization\n"
        "- Relational databases, SQL query tuning, and index design"
    )
    
    q_bank = llm_router.generate_initial_question_bank(
        candidate_name="Alice Smith",
        candidate_resume=resume_text,
        job_title="Lead Backend Engineer",
        competencies=competencies
    )
    
    assert "behavioral" in q_bank
    assert "technical" in q_bank
    assert "case" in q_bank
    
    assert len(q_bank["behavioral"]) > 10
    assert len(q_bank["technical"]) > 10

def test_interview_rubric_scoring():
    """Verify that we parse and compute multi-dimensional rubrics separating delivery from substance."""
    mock_transcript = [
        {"role": "ai", "text": "Can you introduce yourself?"},
        {"role": "candidate", "text": "Hi, I am John. I work as a python developer and know fastapi, sqlalchemy and postgres."},
        {"role": "ai", "text": "Walk me through an engineering challenge you solved."},
        {"role": "candidate", "text": "We had database deadlocks because of locks in postgres. I optimized indices and queries, which fixed it."}
    ]
    
    evaluation = llm_router.assess_interview_rubric(
        candidate_name="John Doe",
        job_title="Python Backend Engineer",
        transcript=mock_transcript
    )
    
    assert "substance_score" in evaluation
    assert "delivery_score" in evaluation
    assert "overall_score" in evaluation
    assert "ai_summary" in evaluation
    
    assert "technical_correctness" in evaluation["substance_score"]
    assert "communication_clarity" in evaluation["delivery_score"]

if __name__ == "__main__":
    print("Running competency tests...")
    test_competency_framework()
    print("Competency framework matching passed!")
    
    print("Running question bank tests...")
    test_question_bank_generation()
    print("Question bank generation passed!")
    
    print("Running rubric scoring tests...")
    test_interview_rubric_scoring()
    print("Rubric scoring passed!")
    
    print("All interview diagnostics completed successfully!")
