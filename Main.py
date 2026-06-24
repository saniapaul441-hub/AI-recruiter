"""
main.py
-------
The FastAPI application entry point.

To run:
    uvicorn app.main:app --reload

Then open:
    http://localhost:8000/docs   ← interactive API docs
    http://localhost:8000/health ← quick health check
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routes.auth import router as auth_router

# ─── Create all DB tables on startup ─────────────────────────────────────────
# In production you'd use Alembic migrations instead,
# but this is fine for development.
Base.metadata.create_all(bind=engine)

# ─── App instance ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Recruiter API",
    description="Intelligent candidate ranking with semantic fingerprints + LLM deep evaluation",
    version="1.0.0",
)

# ─── CORS (allows the frontend to call the API) ───────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api")
# Phase 2+: app.include_router(jobs_router, prefix="/api")
# Phase 2+: app.include_router(candidates_router, prefix="/api")
# Phase 3+: app.include_router(rankings_router, prefix="/api")


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    """Quick check that the server is running."""
    return {"status": "ok", "message": "AI Recruiter API is live"}


# ─── Serve frontend (Phase 5) ─────────────────────────────────────────────────
# app.mount("/", StaticFiles(directory="static", html=True), name="static")