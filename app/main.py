import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models.auth import User
from app.utils.security import get_password_hash
from app.routes import auth, core

# Initialize database tables on startup
Base.metadata.create_all(bind=engine)

# Seed default credentials if database is empty
def seed_default_users():
    db = SessionLocal()
    try:
        # Check if users table is empty
        if db.query(User).count() == 0:
            print("Seeding default credentials...")
            
            # Default Recruiter
            recruiter = User(
                email="recruiter@recruiter.com",
                password_hash=get_password_hash("recruiter123"),
                role="recruiter"
            )
            # Default Admin
            admin = User(
                email="admin@admin.com",
                password_hash=get_password_hash("admin123"),
                role="admin"
            )
            db.add(recruiter)
            db.add(admin)
            db.commit()
            print("Successfully seeded credentials:")
            print(" -> Recruiter: recruiter@recruiter.com / recruiter123")
            print(" -> Admin: admin@admin.com / admin123")
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        db.close()

seed_default_users()

app = FastAPI(
    title="AI Recruiter - Intelligent Candidate Ranking System",
    description="A multi-dimensional candidate search, rank, and structured feedback extraction API.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(core.router)

# Mount frontend files served from static directory
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def redirect_to_dashboard():
    """Redirect root path to static dashboard index."""
    return RedirectResponse(url="/static/index.html")
