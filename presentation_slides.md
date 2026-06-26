# AI Recruiter - Technical Presentation Slides

This presentation is designed specifically to align with the **Redrob Idea Submission Template**.

---

## 🛝 Slide 1: Title Slide
* **Title**: AI RECRUITER
* **Subtitle**: Intelligent Talent Ingestion & Candidate Alignment System
* **Team Details**:
  - **Team Name**: Sania
  - **Problem Statement**: Talent Ingestion & Candidate Alignment
  - **Team Leader Name**: Sania
* **Event**: India Runs by Redrob AI Hackathon (Hack2Skill)

---

## 🛝 Slide 2: Solution Overview
* **Proposed Solution**: 
  - An AI-native recruiting suite featuring automated job description parsing, local semantic candidate matching, and dynamic multi-signal alignment ranking.
  - Integrates a secure proctor-secure AI voice screening room with built-in telemetry to automatically verify candidate integrity.
* **What Differentiates Our Approach**:
  - Traditional keyword matching misses qualified candidates due to literal terminology limits.
  - Our platform uses dense 384-dimensional vector embeddings to understand the semantic intent of experiences, coupled with an LLM evaluation layer for verification.

---

## 🛝 Slide 3: JD Understanding & Candidate Evaluation
* **JD Requirement Extraction**:
  - Google Gemini 2.0 Flash parses unstructured job descriptions into structured criteria: Must-Have skills, Nice-to-Have skills, experience limits, and role scope.
  - Automatically generates weighted skill components based on JD semantics.
* **Candidate Core Signals & Evaluation**:
  - Evaluates semantic relevance (vector similarity), years of experience against target range, dynamic recruiter weighting factors, and biometric/focus telemetry during screening.
  - Allows recruiters to adjust sliders to dynamically recalculate fit scores on the fly.

---

## 🛝 Slide 4: Ranking Methodology
* **1. Retrieval**: Uses local SentenceTransformers ('all-MiniLM-L6-v2') to calculate 384-dimensional dense vector representations of JDs and resumes locally.
* **2. Scoring**: Computes Cosine Similarity between JD skills and candidate text vectors, and computes experience matches based on chronological milestones.
* **3. Dynamic Ranking**: Combines vector scores, experience fit, and recruiter slider preferences dynamically: 
  $$\text{Score} = (W_{\text{skills}} \times S_{\text{vector}}) + (W_{\text{exp}} \times S_{\text{exp}})$$

---

## 🛝 Slide 5: Explainability & Data Validation
* **Ranking Explainability**: Gemini 2.0 Flash produces a detailed fit analysis detailing explicit pros, cons, and a qualitative alignment summary for the recruiter.
* **Hallucination Prevention**: Rigid system prompt instructions force the LLM to ground justifications strictly on text present in the candidate's resume.
* **Anomalies & Telemetry**: Validates formats (email, phone, dates) via regex, and monitors tab focus/blur events during screens to flag anomalous behavior.

---

## 🛝 Slide 6: End-to-End Workflow
* **1. Job & Resume Ingestion**: Recruiter creates job details. Ingests candidate resumes (PDF/CSV). Cleans and indexes profile text.
* **2. Vector Indexing & Ranking**: Extracts features, computes embeddings, and populates the recruiter's dynamic ranking list.
* **3. Secure AI Screening**: Top candidates undergo voice screening interviews with biometric and focus proctoring tracking.
* **4. Review & Outreach**: Recruiter verifies proctoring flags, ranks, edits auto-drafted candidate emails, and sends them.

---

## 🛝 Slide 7: System Architecture
* **FastAPI Backend Layer**: Python FastAPI acts as the ML server, generating sentence embeddings, computing cosine similarity, and serving API routes.
* **Node.js & Supabase Stack**: Alternative Express backend supporting high-speed database integrations, web socket loops, and JWT security keys.
* **Frontend User Interface**: Clean HTML5, CSS3, and JavaScript dashboard featuring a Web Speech continuous listening engine for interviews.

---

## 🛝 Slide 8: Results & Performance
* **Quality & Insights**:
  - Ensures 100% local embedding generation speed (<5ms) with zero cloud vector database dependency costs.
  - Recruiter can export ranked candidate lists to CSV in one click.
* **Compute Constraints**: System runs entirely locally on CPU, with memory-based fallbacks to guarantee uptime even if external database connections fail.

---

## 🛝 Slide 9: Technologies Used
* **AI & NLP Engines**: Google Gemini 2.0 Flash, SentenceTransformers ('all-MiniLM-L6-v2'), PyTorch, NumPy vector math.
* **Server Frameworks**: FastAPI (Python), Node.js / Express, SQLite, Supabase SQL database schema.
* **Web & Audio Services**: Web Speech API (webkitSpeechRecognition) with auto-recovering listening states, HTML5 Canvas.

---

## 🛝 Slide 10: Submission Assets
* **Submission Links**:
  - GitHub Code: https://github.com/saniapaul441-hub/AI-recruiter
  - Ranked Output: `ranked_candidates_sample.csv` in workspace
  - Presentation Deck: `AI_Recruiter_Presentation.pdf`
* **Asset Notes**:
  - Repository cleaned of all temporary copy folders.
  - Zero API credentials committed (managed in local `.env`).
  - Complete test suite verified passing locally.
