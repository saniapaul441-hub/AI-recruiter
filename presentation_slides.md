# AI Recruiter - Technical Presentation Slides

Use this slide-by-slide guide to build your PowerPoint/Google Slides deck. Convert the final presentation into a PDF for your submission.

---

## 🛝 Slide 1: Title Slide
* **Title**: AI RECRUITER
* **Subtitle**: Intelligent Talent Ingestion & Candidate Alignment System\n\nAutomated Resume Ingestion, Semantic Matching, and Proctor-Secure AI Interviews
* **Presenter**: Sania
* **Event**: India Runs by Redrob AI Hackathon (Hack2Skill)

---

## 🛝 Slide 2: The Core Problem
* **Keyword Matching is Broken**: Traditional recruitment software filters profiles using literal keyword matches, missing highly qualified candidates who describe their skills differently.
* **Inconsistent Evaluations**: Manual resume reviews are slow and subject to recruiter bias, leading to inconsistent evaluations and missed matches.
* **Scale Bottleneck**: Talent acquisition teams spend hours conducting repetitive phone screens and filtering huge stacks of candidates.

---

## 🛝 Slide 3: What We Built - Core System Overview
* **Double-Layer Candidate Screening**:
  - **Layer 1 (Semantic Filtering)**: Matches candidates instantly based on context and meaning, not just keywords.
  - **Layer 2 (Deep LLM Scoring)**: Uses Gemini 2.0 Flash to evaluate candidate fit, list pros/cons, and generate feedback.
* **AI Screening Hub**: An interactive, voice-driven screening interview with built-in behavioral telemetry to flag focus-loss or tab-switching in real-time.
* **Developer & Stack Flexibility**: Built primarily with a high-performance Python FastAPI backend, supported by an alternative Node.js Express/Supabase stack.

---

## 🛝 Slide 4: How It Works - System Architecture & Workflow
* **1. Role Creation**: Recruiter creates a job description, which the Google Gemini LLM parses into structured Must-Have and Nice-to-Have skills, experience level, and role summary.
* **2. Ingestion & Extraction**: Ingests candidate profiles (via CSV/PDF). Cleans and extracts names, emails, phones, and parsed text automatically.
* **3. Vector Matching**: Calculates dense 384-dimensional semantic embeddings. Computes cosine similarity of candidate profiles against the job description requirements.
* **4. Dynamic Weighting**: Recruiter can dynamically adjust sliders (Experience vs. Skills vs. Leadership) to instantly recalculate and rank candidate fit scores.

---

## 🛝 Slide 5: Why We Built It This Way - Semantic Matching & Fallbacks
* **Dense Embeddings Model**: Uses local SentenceTransformers ('all-MiniLM-L6-v2') to compute 384-dimensional dense vectors locally to secure high performance.
* **Zero-Crash Local Fallback**: If remote servers or libraries are missing, the system uses local NumPy vector calculations and an in-memory cache to ensure zero-downtime evaluation.
* **Dynamic Customization**: Features dynamic sliders that allow recruiters to customize candidate rank weighting on-the-fly, bringing total control back to recruiters.

---

## 🛝 Slide 6: How It Works - Deep LLM Evaluation
* **Intelligent Fit Scoring**: Gemini 2.0 Flash performs deep text analysis of candidates' career milestones, project details, and technical expertise to assign realistic fit scores.
* **Constructive Feedback**: Automatically drafts personalized emails, including structured outreach invites for top matches and customized feedback with learning resources for rejected profiles.
* **Outbox Validation Queue**: Queues generated emails in a recruiter outbox for verification, editing, and approval before final transmission via SMTP.

---

## 🛝 Slide 7: What We Built - AI Screening Room & Proctoring
* **Biometrics Simulation**: Local camera feed is rendered inside the chat portal with a live face landmark canvas to simulate focus tracking.
* **Speech Recognition**: Integrated with the Web Speech API (webkitSpeechRecognition) configured for continuous listening and automatic restart, facilitating natural voice responses.
* **Anti-Cheating Telemetry**: Monitors candidate focus, tab-switching, and window blur. Logs warnings immediately to the backend warning API `/api/interviews/proctor/warning/{cand_id}/{job_id}`.

---

## 🛝 Slide 8: Why We Built It This Way - Multi-Tenant Security & Compliance
* **Secure JWT Authentication**: Access is protected using JSON Web Tokens (JWT) encrypted with bcrypt hashing for secure session logins.
* **Recruiter Isolation**: Multi-tenant workspace isolation ensures recruiters only see and manage their own jobs, candidate uploads, and logs.
* **Administrative Compliance**: All critical actions (proctoring warnings, uploads, status updates) write directly to a secure compliance Audit Log database table.

---

## 🛝 Slide 9: Why We Built It This Way - Performance & Cost-Efficiency
* **100% Passed Tests**: All backend diagnostic suites passed: JWT security cryptography, CSV profile ingestion, regex extractors, and workspace isolation.
* **Optimized Cost-Efficiency**: Local embedding generation avoids high external API invocation costs, making the platform highly scalable.
* **Immediate Ranked Output**: Recruiter dashboard features a live 'Export CSV' button, producing the ranked candidate list in one click for instant submission.

---

## 🛝 Slide 10: Conclusion & Future Roadmap
* **Functional Summary**: Delivered a complete, working, multi-role recruitment workflow featuring semantic vector search, LLM analysis, and anti-cheating screening.
* **Future Extensions**:
  - Integrate WhatsApp outreach for faster candidate response times.
  - Add voice biometrics to verify candidate identity and prevent proxy test-taking.
  - Extend multi-lingual interview support using localized Web Speech models.
