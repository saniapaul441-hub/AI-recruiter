# AI-recruiter
# 🤖 AI-Powered Automated Talent Acquisition & Candidate Evaluation System

> Built for **India Runs by Redrob AI** Hackathon on Hack2Skill

> [!IMPORTANT]
> **Primary LLM Engine**: This project is built primarily on the **Google Gemini API** (using the Python FastAPI backend) for resume parsing, candidate scoring, and the conversational AI screening portal. Make sure to obtain a Gemini API key from [Google AI Studio](https://aistudio.google.com/) and configure it as `GEMINI_API_KEY` in your `.env` file to enable all AI functionalities.

Traditional hiring is slow, biased, and expensive. This system automates the entire recruitment pipeline — from resume screening to AI-powered interviews — giving recruiters instant, data-driven candidate evaluations.

---

## 🚀 What It Does

This system is an intelligent candidate evaluation suite featuring:
- **Two-Backend Flexibility**: Run either a modular Python FastAPI backend or an alternative Node.js Express backend.
- **Intelligent Candidate Search**: High-performance semantic similarity matching using vector embeddings (via Pinecone or local NumPy fallback).
- **Proctored AI Interviews**: An automated chat portal where candidates take an AI-conducted interview, featuring real-time tab-switching and visibility proctoring telemetry.
- **Personalized Feedback & Roadmaps**: AI-generated reports outlining skill gaps, recommended actions, and personalized roadmaps for candidate improvement.

---

## ✨ Key Features

- **Double-Layer Candidate Screening**
  - **Layer 1 (Semantic Filtering)**: Vector search using `all-MiniLM-L6-v2` embeddings for fast semantic filtering against job descriptions (stored online in **Pinecone** or cached locally using **NumPy**).
  - **Layer 2 (Deep Evaluation)**: LLM analysis using **Google Gemini 2.0 Flash** (Python backend) or **Anthropic Claude 3.5 Sonnet** (Node.js backend) for deep candidate scoring, pros/cons, and structured feedback.
- **Proctored AI Interviews**
  - Dynamic chat screening interview tailored automatically to the job description.
  - Proctoring detection tracking focus loss, window blur, and tab switching.
- **Dynamic Recruiter Weighting**
  - Recruiters adjust weights on the fly via sliders (Experience, Skills, and Leadership) to dynamically recalculate candidate fit scores.
- **Recruiter Workspace Isolation**
  - Secure role-based access control ensuring recruiters can only see and manage their own jobs, candidates, and outbox logs.
- **Validation Outbox**
  - Automated emails (outreach/rejections) are queued in an outbox for recruiters to review, customize, or dispatch.

---

## 🛠️ Tech Stack

| Layer | Python Backend (Primary) | Node.js Backend (Alternative) |
|-------|--------------------------|--------------------------------|
| **Core Framework** | FastAPI | Express.js |
| **Database** | SQLAlchemy ORM + SQLite | Supabase (PostgreSQL) |
| **AI / LLM** | Google Gemini 2.0 Flash | Anthropic Claude 3.5 Sonnet |
| **Vector Search** | Local NumPy / Pinecone | — |
| **Embeddings** | `all-MiniLM-L6-v2` | — |
| **Frontend** | HTML5, CSS3, Vanilla JS | HTML5, CSS3, Vanilla JS |
| **Security** | JWT Auth + Bcrypt | JWT Auth + Bcryptjs |

---

## 📁 Project Structure

```text
AI-recruiter/
├── app/                        # FastAPI Backend Codebase
│   ├── config.py               # App settings & dotenv configuration
│   ├── database.py             # Database engine & session generator
│   ├── main.py                 # FastAPI app setup & static route mounts
│   ├── models/                 # SQLAlchemy Database models (User, Job, etc.)
│   ├── routes/                 # Route endpoint handlers (auth, core)
│   ├── services/               # Business logic (automation, llm_router, vector_db)
│   └── utils/                  # Security helper utilities (JWT validation)
├── static/                     # Web Portal Frontend Files
│   ├── index.html & app.js     # Recruiter login page & auth flow
│   ├── portal.html & portal.js # Recruiter workspace dashboard
│   ├── screening.html & js     # Candidate AI chat interview with proctoring
│   └── style.css               # Custom stylesheet
├── tests/                      # Diagnostic Test Suite
│   └── test_parser.py          # Unit tests (security, CSV parser, isolation)
├── .env                        # Configuration environment variables template
├── run_tests.py                # Test suite runner
├── server.js                   # Alternative Node.js Express server
└── package.json                # Node.js dependencies configuration
```

## ⚙️ Codebase Map by Feature

Here is how the project's code files map directly to the system's core capabilities:

| Feature Area | Backend API Endpoints | Core Processing Logic | Frontend Pages |
| :--- | :--- | :--- | :--- |
| **Recruiter Access & Auth** | `app/routes/auth.py` | `app/utils/security.py` | `static/index.html` |
| **Job Description Parsing** | `POST /api/jobs` (`core.py`) | `llm_router.py` (Gemini API) | `static/portal.html` |
| **Resume Extraction** | `POST /api/candidates/upload` | `parser.py` (CSV / Regex) | `static/portal.html` |
| **Vector Search Matching** | `POST /api/rankings/compute` | `vector_db.py` (Local NumPy / Pinecone) | `static/portal.html` |
| **AI Screening Interview** | `/api/interviews/results` | `llm_router.py` (Gemini) | `static/screening.html` |
| **Cheating & Proctoring** | `POST /api/interviews/proctor` | `core.py` (Alert logger) | `static/screening.js` |
| **Outbox & Email Delivery** | `GET /api/automation/outbox` | `automation.py` (SMTP delivery) | `static/portal.html` |



---

## 🏆 Hackathon Candidate Ranking (rank.py)

For the Redrob Hackathon Stage 3 code reproduction, you can run the candidate ranker script end-to-end using the Python Standard Library (no external dependencies are required to run `rank.py`).

### Reproduction Command

Run the following command from the repository root to process the candidate profiles and generate the top 100 rankings in CSV format:

```bash
python rank.py --candidates ./ai_recruiter/hacathon_data/candidates.jsonl --out ./submission.csv
```

### Parameters
* `--candidates`: Path to the candidate profile dataset (e.g., `candidates.jsonl` or `.json` or `.jsonl.gz`). If omitted, it will automatically search in `./ai_recruiter/hacathon_data/` for `candidates.jsonl`, `candidates.jsonl.gz`, or `sample_candidates.json`.
* `--out`: Path to write the output ranked CSV file (defaults to `submission.csv`).

The script automatically filters out honeypot profiles, scores each valid candidate across career relevance, skill sets, and behavioral signals, and exports the top 100 results strictly matching the submission specification.

### 🚀 Interactive Google Colab Sandboxes

You can run a demo of the candidate ranker directly in your browser on Google Colab:

* **[AI_Recruiter_Sandbox.ipynb](AI_Recruiter_Sandbox.ipynb)**: Downloads the candidate dataset directly from GitHub and runs the full ranker logic.
  [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/saniapaul441-hub/AI-recruiter/blob/main/AI_Recruiter_Sandbox.ipynb)
* **[mini_rank_sandbox.ipynb](mini_rank_sandbox.ipynb) (Fully Offline / Simple)**: Runs a mini version of the ranking engine without any API or network calls. It contains an embedded subset of candidate profiles for instant testing, and supports uploading custom candidate files.
  [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/saniapaul441-hub/AI-recruiter/blob/main/mini_rank_sandbox.ipynb)

---

## ⚙️ How to Run

### Option A: Python FastAPI Backend (Primary)

#### 1. Clone the repository
```bash
git clone https://github.com/saniapaul441-hub/AI-recruiter.git
cd AI-recruiter
```

#### 2. Create and activate a virtual environment
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

#### 3. Install dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment Variables
Create a `.env` file in the root directory:
```env
DATABASE_URL=sqlite:///./recruiter.db
SECRET_KEY=your_jwt_secret_key
GEMINI_API_KEY=your_google_gemini_api_key

# Optional: Add Pinecone credentials to use cloud vector search.
# Otherwise, the system automatically falls back to local NumPy search.
PINECONE_API_KEY=
PINECONE_ENV=us-east-1
PINECONE_INDEX=recruiter-fingerprints
```

#### 5. Run the application
Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

### Option B: Node.js + Supabase Backend (Alternative)

#### 1. Install Node dependencies
```bash
npm install
```

#### 2. Configure Environment Variables
Add these to your `.env` file:
```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
ANTHROPIC_API_KEY=your_anthropic_claude_api_key
JWT_SECRET=your_jwt_secret_key
PORT=8000
```

#### 3. Run the application
```bash
npm start
```

---

### 🧪 Running Diagnostics & Tests
Verify system integrity (auth security, parser robustness, database isolation) by running:
```bash
python run_tests.py
```

---

### 👩‍💻 Built By
* **Sania Paul** — First-year student, B.Tech IoT with Blockchain & Cybersecurity
  * Chandigarh Group of Colleges, Landran (2025–2029)

### 📄 License
This project is submitted as part of the Hack2Skill Hackathon — **India Runs by Redrob AI**. All rights reserved.





