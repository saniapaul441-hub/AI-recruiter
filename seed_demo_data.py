import os
import json
import datetime
from sqlalchemy.orm import Session
from app.database import engine, Base, SessionLocal
from app.models.auth import User
from app.models.core import Job, Candidate, Ranking, AuditLog
from app.services.llm_router import llm_router
from app.services.vector_db import vector_db
from app.utils.security import get_password_hash

def seed_demo():
    print("Initializing Database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Seed Recruiter & Admin accounts if they don't exist
        print("Checking accounts...")
        recruiter = db.query(User).filter(User.email == "recruiter@recruiter.com").first()
        if not recruiter:
            recruiter = User(
                email="recruiter@recruiter.com",
                password_hash=get_password_hash("recruiter123"),
                role="recruiter"
            )
            db.add(recruiter)
            
        admin = db.query(User).filter(User.email == "admin@admin.com").first()
        if not admin:
            admin = User(
                email="admin@admin.com",
                password_hash=get_password_hash("admin123"),
                role="admin"
            )
            db.add(admin)
        db.commit()
        
        # 2. Add sample Lead Python Engineer Job Description
        print("Creating Sample Job Description...")
        sample_jd = db.query(Job).filter(Job.title == "Lead Backend Engineer (Python & FastAPI)").first()
        if not sample_jd:
            sample_jd = Job(
                title="Lead Backend Engineer (Python & FastAPI)",
                description=(
                    "We are seeking a Lead Backend Engineer to head our microservices architecture team. "
                    "You will design high-performance, robust, and scalable APIs using Python and FastAPI. "
                    "Key Responsibilities:\n"
                    "- Drove system architecture decisions and lead backend design pipelines.\n"
                    "- Mentor junior developers and establish best coding practices.\n"
                    "- Integrate PostgreSQL database services and build optimized SQL schemas.\n"
                    "- Set up search indexing and vector databases (e.g. Pinecone, Elasticsearch) for AI retrieval.\n"
                    "Requirements:\n"
                    "- 5+ years of software development experience.\n"
                    "- Expert knowledge of Python, FastAPI, and SQLAlchemy ORM.\n"
                    "- Proven experience with Docker containers, AWS cloud environments, and CI/CD pipelines.\n"
                    "- Demonstrated technical leadership or engineering mentorship credentials."
                ),
                parsed_requirements={
                    "extracted_title": "Lead Backend Engineer (Python & FastAPI)",
                    "must_have_skills": ["Python", "FastAPI", "SQLAlchemy", "System Design", "Technical Leadership"],
                    "nice_to_have_skills": ["Docker", "PostgreSQL", "AWS", "Vector Databases", "Pinecone"],
                    "experience_level": "5+ years",
                    "role_type": "Full-Time",
                    "summary": "Lead the design, development, and scaling of core backend microservices built with Python and FastAPI."
                }
            )
            db.add(sample_jd)
            db.commit()
            db.refresh(sample_jd)
        
        # 3. Add Mock Candidates
        print("Creating Mock Candidates...")
        
        # Candidate 1: Alice Smith (Excellent Technical Backend Fit)
        alice = db.query(Candidate).filter(Candidate.email == "alice.smith@gmail.com").first()
        if not alice:
            alice = Candidate(
                name="Alice Smith",
                email="alice.smith@gmail.com",
                phone="+1 (555) 019-2834",
                skills=["Python", "FastAPI", "SQLAlchemy", "PostgreSQL", "Docker", "AWS", "Redis", "Git"],
                experience=[
                    {
                        "company": "TechGlobal Solutions",
                        "title": "Senior Backend Engineer",
                        "start_date": "2022",
                        "end_date": "Present",
                        "description": "Architected and maintained 15 high-throughput microservices using FastAPI and python-jose. Designed optimal PostgreSQL queries reducing read latencies by 35%. Mentored 3 junior software engineers."
                    },
                    {
                        "company": "Apex Coders Inc",
                        "title": "Backend Software Developer",
                        "start_date": "2020",
                        "end_date": "2022",
                        "description": "Built REST APIs using Python, Django, and MySQL. Implemented Redis caching layers saving $4,000/month in database cloud hosting costs."
                    }
                ],
                education=[
                    {
                        "institution": "University of Michigan",
                        "degree": "B.S. in Computer Science",
                        "grad_year": "2020"
                    }
                ],
                full_parsed_text="Alice Smith. Senior Backend Engineer at TechGlobal Solutions. Skills: Python, FastAPI, SQLAlchemy, PostgreSQL, Docker, AWS. 6 years experience.",
                embedding_generated=True
            )
            db.add(alice)
            
        # Candidate 2: Diana Prince (Exceptional Leadership & Management Fit)
        diana = db.query(Candidate).filter(Candidate.email == "diana.prince@capitalone.com").first()
        if not diana:
            diana = Candidate(
                name="Diana Prince",
                email="diana.prince@capitalone.com",
                phone="+1 (555) 014-9844",
                skills=["Python", "System Design", "Engineering Leadership", "Agile", "GCP", "PostgreSQL", "Kubernetes"],
                experience=[
                    {
                        "company": "Capital Software Hub",
                        "title": "Engineering Manager & Tech Lead",
                        "start_date": "2021",
                        "end_date": "Present",
                        "description": "Managed a team of 8 backend developers. Owned architectural roadmap for global payment APIs. Led sprint plannings and drove cross-functional system design alignments."
                    },
                    {
                        "company": "InnoSoft Systems",
                        "title": "Lead Software Architect",
                        "start_date": "2017",
                        "end_date": "2021",
                        "description": "Designed cloud systems on GCP using Kubernetes and Python. Spearheaded migration from monolithic databases to microservices with 99.99% uptime compliance."
                    }
                ],
                education=[
                    {
                        "institution": "Stanford University",
                        "degree": "M.S. in Software Engineering",
                        "grad_year": "2017"
                    }
                ],
                full_parsed_text="Diana Prince. Tech Lead & Engineering Manager. Skills: System Design, Technical Leadership, Python, Kubernetes, GCP. 9 years experience.",
                embedding_generated=True
            )
            db.add(diana)
            
        # Candidate 3: Bob Johnson (Data Engineer - Moderate Fit)
        bob = db.query(Candidate).filter(Candidate.email == "bob.johnson@dataops.org").first()
        if not bob:
            bob = Candidate(
                name="Bob Johnson",
                email="bob.johnson@dataops.org",
                phone="+1 (555) 012-7634",
                skills=["Python", "Apache Spark", "Pandas", "SQL", "Hadoop", "Tableau", "Git"],
                experience=[
                    {
                        "company": "DataStream Tech",
                        "title": "Senior Data Analytics Engineer",
                        "start_date": "2022",
                        "end_date": "Present",
                        "description": "Built ingestion pipelines parsing 5TB/day data streams using Python and PySpark. Conducted database query optimizations on analytics platforms."
                    }
                ],
                education=[
                    {
                        "institution": "Georgia Institute of Technology",
                        "degree": "B.S. in Applied Mathematics",
                        "grad_year": "2021"
                    }
                ],
                full_parsed_text="Bob Johnson. Data Analytics Engineer. Skills: Python, Apache Spark, Pandas, SQL, Analytics pipelines. 4 years experience.",
                embedding_generated=True
            )
            db.add(bob)
            
        # Candidate 4: Charlie Brown (Junior Developer - Entry Fit)
        charlie = db.query(Candidate).filter(Candidate.email == "charlie.brown@yahoo.com").first()
        if not charlie:
            charlie = Candidate(
                name="Charlie Brown",
                email="charlie.brown@yahoo.com",
                phone="+1 (555) 018-3647",
                skills=["Python", "Flask", "HTML", "CSS", "JavaScript", "Git", "SQLite"],
                experience=[
                    {
                        "company": "AppCraft Studio",
                        "title": "Junior Backend Developer",
                        "start_date": "2024",
                        "end_date": "Present",
                        "description": "Maintained simple CRUD REST endpoints using Python, Flask, and SQLite. Resolved frontend CSS bugs and documented backend integration manuals."
                    }
                ],
                education=[
                    {
                        "institution": "Austin Community College",
                        "degree": "A.S. in Computer Science",
                        "grad_year": "2024"
                    }
                ],
                full_parsed_text="Charlie Brown. Junior Flask Developer. Skills: Python, Flask, CSS, JavaScript, HTML. 1.5 years experience.",
                embedding_generated=True
            )
            db.add(charlie)
            
        # Candidate 5: Evan Wright (Frontend Specialist - Lower Fit)
        evan = db.query(Candidate).filter(Candidate.email == "evan.wright@creativeweb.io").first()
        if not evan:
            evan = Candidate(
                name="Evan Wright",
                email="evan.wright@creativeweb.io",
                phone="+1 (555) 019-3388",
                skills=["React", "JavaScript", "Next.js", "Tailwind CSS", "HTML5", "UX Design"],
                experience=[
                    {
                        "company": "PixelPerfect UI",
                        "title": "Lead Frontend UI Developer",
                        "start_date": "2021",
                        "end_date": "Present",
                        "description": "Led visual branding redesigns using React, Next.js, and Tailwind CSS. Implemented responsive visual layouts with fluid transitions."
                    }
                ],
                education=[
                    {
                        "institution": "Rhode Island School of Design",
                        "degree": "B.A. in Graphic Design & Web Interfaces",
                        "grad_year": "2021"
                    }
                ],
                full_parsed_text="Evan Wright. Lead Frontend Developer. Skills: React, Next.js, Tailwind CSS, Javascript, UI/UX. 5 years experience.",
                embedding_generated=True
            )
            db.add(evan)
            
        db.commit()
        db.refresh(alice)
        db.refresh(diana)
        db.refresh(bob)
        db.refresh(charlie)
        db.refresh(evan)
        
        # 4. Generate local vector embeddings caches
        print("Registering local vector representations...")
        vector_db.upsert_candidate(alice.id, alice.full_parsed_text)
        vector_db.upsert_candidate(diana.id, diana.full_parsed_text)
        vector_db.upsert_candidate(bob.id, bob.full_parsed_text)
        vector_db.upsert_candidate(charlie.id, charlie.full_parsed_text)
        vector_db.upsert_candidate(evan.id, evan.full_parsed_text)
        
        # 5. Populate pre-computed Deep Rankings to showcase sliders instantly!
        print("Computing mock rankings for Lead Engineer JD...")
        
        # Alice (Rank 1 - Tech Heavy)
        r_alice = db.query(Ranking).filter(Ranking.job_id == sample_jd.id, Ranking.candidate_id == alice.id).first()
        if not r_alice:
            db.add(Ranking(
                job_id=sample_jd.id,
                candidate_id=alice.id,
                score=92.0,
                sub_scores={"experience": 88.0, "skills": 96.0, "leadership": 75.0},
                pros=[
                    "Excellent technical fit with expert Python, FastAPI, and SQLAlchemy credentials.",
                    "Direct microservices design experience reducing system read latency by 35%.",
                    "Strong background in containerization (Docker) and AWS cloud deployments."
                ],
                cons=[
                    "Has slightly less overall years of career experience (6 years) than Diana (9 years).",
                    "No formal engineering manager title in background.",
                    "Familiarity with modern vector databases is not explicitly highlighted."
                ],
                feedback_report={"behavioral_indicators": "Highly diligent, detail-oriented technical expert. Pragmatic developer who focuses on optimization and efficiency metrics."},
                status="pending"
            ))
            
        # Diana (Rank 2 - Leadership Heavy)
        r_diana = db.query(Ranking).filter(Ranking.job_id == sample_jd.id, Ranking.candidate_id == diana.id).first()
        if not r_diana:
            db.add(Ranking(
                job_id=sample_jd.id,
                candidate_id=diana.id,
                score=88.5,
                sub_scores={"experience": 95.0, "skills": 82.0, "leadership": 98.0},
                pros=[
                    "Exceptional leadership background having managed a team of 8 backend engineers.",
                    "Strong system design capability with monolithic to microservices migrations.",
                    "9 years of solid software career experience, bringing architectural maturity."
                ],
                cons=[
                    "Skills are python-focused but lacks explicit references to FastAPI/SQLAlchemy framework specifics.",
                    "Primary cloud background is on GCP rather than the requested AWS cloud stack.",
                    "Technical hands-on coding depth might be slightly lower due to recent management focus."
                ],
                feedback_report={"behavioral_indicators": "Clear strategic visionary and team captain. Highly organized systems-thinker who excels at driving team alignment and architectures."},
                status="pending"
            ))
            
        # Bob (Rank 3 - Moderate Fit)
        r_bob = db.query(Ranking).filter(Ranking.job_id == sample_jd.id, Ranking.candidate_id == bob.id).first()
        if not r_bob:
            db.add(Ranking(
                job_id=sample_jd.id,
                candidate_id=bob.id,
                score=62.5,
                sub_scores={"experience": 65.0, "skills": 68.0, "leadership": 50.0},
                pros=[
                    "Strong background in Python coding and scalable data processing pipelines.",
                    "Familiarity with complex SQL database integrations.",
                    "Solid understanding of data structure architectures and engineering loops."
                ],
                cons=[
                    "Lack of web API framework experience (no FastAPI or Django noted).",
                    "No systems engineering or microservices deployment exposure.",
                    "Minimal technical team leadership or mentoring credentials."
                ],
                feedback_report={"behavioral_indicators": "Analytics-driven engineer. Excels at working with heavy datasets but demonstrates gaps for traditional web platform services."},
                status="pending"
            ))
            
        # Charlie (Rank 4 - Junior Developer)
        r_charlie = db.query(Ranking).filter(Ranking.job_id == sample_jd.id, Ranking.candidate_id == charlie.id).first()
        if not r_charlie:
            db.add(Ranking(
                job_id=sample_jd.id,
                candidate_id=charlie.id,
                score=44.0,
                sub_scores={"experience": 30.0, "skills": 50.0, "leadership": 25.0},
                pros=[
                    "Basic foundational exposure to python programming and Flask APIs.",
                    "Shows high eagerness to build and document CRUD applications.",
                    "Familiar with standard version control systems (Git) and workflows."
                ],
                cons=[
                    "Does not meet the 5+ years seniority requirement (has 1.5 years experience).",
                    "No system design, microservices or distributed systems background.",
                    "Lacks database optimization (PostgreSQL/SQLAlchemy) or cloud deployment skills."
                ],
                feedback_report={"behavioral_indicators": "Eager and enthusiastic junior developer. Excellent candidate for junior mentorship but currently lacks architectural maturity for a Lead role."},
                status="pending"
            ))
            
        # Evan (Rank 5 - Frontend Focus)
        r_evan = db.query(Ranking).filter(Ranking.job_id == sample_jd.id, Ranking.candidate_id == evan.id).first()
        if not r_evan:
            db.add(Ranking(
                job_id=sample_jd.id,
                candidate_id=evan.id,
                score=32.0,
                sub_scores={"experience": 50.0, "skills": 20.0, "leadership": 50.0},
                pros=[
                    "Strong visual UI/UX web systems engineering experience.",
                    "Demonstrated project management and technical lead capabilities (Lead title).",
                    "Familiar with modern web tooling, standard git versions and responsive layouts."
                ],
                cons=[
                    "Lacks backend Python, FastAPI, and SQLAlchemy credentials entirely.",
                    "No system architecture, microservices engineering or cloud ops database design experience.",
                    "Background is purely frontend UI-focused."
                ],
                feedback_report={"behavioral_indicators": "Highly creative and product-oriented frontend engineer. Strong design sensibility but unsuitable for core backend systems architectures."},
                status="pending"
            ))
            
        db.commit()
        print("Demo Database seeded successfully!")
        print("You can now launch 'python app/main.py' and login with recruiter@recruiter.com / recruiter123!")
    except Exception as e:
        print(f"Error seeding demo database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo()
