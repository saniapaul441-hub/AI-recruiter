# AI Recruiter - Technical Presentation Slides

Use this slide-by-slide guide to build your PowerPoint/Google Slides deck. Convert the final presentation into a PDF for your submission.

---

## 🛝 Slide 1: Title Slide
* **Title**: AI Recruiter: Intelligent Talent Ingestion & Candidate Alignment System
* **Subtitle**: Automated Resume Screening, Semantic Matching, and Proctor-Secure AI Interviews
* **Presenter**: Sania
* **Event**: India Runs by Redrob AI Hackathon (Hack2Skill)

---

## 🛝 Slide 2: The Core Problem
* **Keyword Matching is Broken**: Traditional tools search for exact word matches, missing qualified candidates who describe skills differently (semantic gap).
* **Bias & Human Error**: Inconsistent evaluations lead to missing top fits or hiring based on subjective bias.
* **Scale Bottleneck**: HR teams spend hundreds of hours filtering resumes and conducting repetitive introductory phone screens.

---

## 🛝 Slide 3: Our Solution Overview
* **Double-Layer Candidate Screening**:
  1. **Layer 1 (Semantic Similarity)**: Uses local vector embeddings to filter matches instantly based on context, not keywords.
  2. **Layer 2 (Deep LLM Scoring)**: Uses Google Gemini 2.0 Flash to evaluate candidate fit, list specific pros/cons, and generate feedback.
* **Conversational AI Screening Hub**: An interactive, voice-driven screening interview with built-in behavioral telemetry to flag cheating/proctoring issues.
* **Developer Flexibility**: Flexible Python FastAPI backend paired with a seamless HTML5/Vanilla CSS frontend, with Node.js/Supabase as an alternative.

---

## 🛝 Slide 4: System Architecture & Workflow
* **Ingestion**: Upload Job Descriptions and candidate resumes (CSV/PDF).
* **AI Analysis**: 
  - Gemini parses JDs into structured *Must-Have* and *Nice-To-Have* requirements.
  - Embeddings are generated using the `all-MiniLM-L6-v2` SentenceTransformer model.
* **Matching**: High-speed cosine similarity calculates base candidate fit scores.
* **Workspace**: Recruiters modify search weights (Experience vs. Skills vs. Leadership) in real-time, instantly updating the shortlist.

---

## 🛝 Slide 5: Layer 1 - Semantic Search & Weighting
* **Dense Vector Embeddings**: We convert resumes and JDs into 384-dimensional dense vectors to calculate similarity.
* **Zero-Crash Fallback**: Uses local **NumPy** matrix calculations and an in-memory vector cache (`local_vector_cache.json`) when external vector databases are offline.
* **Dynamic Adjustment Sliders**: Recruiter can shift search weights on-the-fly, giving them absolute control over which candidate profiles float to the top.

---

## 🛝 Slide 6: Layer 2 - Deep LLM Evaluation & Feedback
* **Intelligent Scoring**: Deep scoring beyond vector math. We analyze the candidate's exact experience milestones, title progression, and project depth.
* **Automated Feedback Loop**: The system automatically drafts:
  * Customized outreach emails for top fits.
  * Constructive rejection emails with personalized skill gaps and learning resources for candidates who do not match.
* **recruiter Outbox Validation**: A validation queue allows recruiters to verify and edit emails before final dispatch.

---

## 🛝 Slide 7: Interactive AI Screening & Proctoring
* **Webcam & Mic Integration**: Accesses user webcam and mic streams locally using WebRTC media streams.
* **Dynamic Face Overlay**: Draws an animated biometric feature map on top of the webcam feed to visualizes live focus telemetry.
* **Strict Proctoring Engine**: Monitors tab switching and window blur. If a candidate leaves the tab to copy answers, the screen logs proctoring alerts and notifies the backend database.
* **Continuous Speech Recognition**: Optimized Web Speech API (`webkitSpeechRecognition`) that continues listening even through pauses and stops gracefully on network errors.

---

## 🛝 Slide 8: Workspace Isolation & Security
* **JWT Token Security**: Secured by industry-standard JWT auth tokens with bcrypt password hashing.
* **Workspace Access Isolation**: Multi-tenant isolation. Recruiters can only access, view, and interact with the jobs, candidates, and logs they created.
* **Compliance Audit Logs**: Every action (candidate upload, status switch, proctoring alert) is recorded in a secure Audit Log table for administrative compliance.

---

## 🛝 Slide 9: Impact & Results
* **Diagnostic Integrity**: Passed 100% of the backend diagnostics suite (JWT auth security, CSV parser, vector fallbacks, workspace isolation).
* **Massive Cost Savings**: Running local embedding models eliminates high API costs for Layer 1 screening.
* **Immediate Export**: Recruiter dashboard now features a live **"Export CSV"** button, creating the required ranked output shortlist in a single click.

---

## 🛝 Slide 10: Conclusion & Future Roadmap
* **Hackathon Goal Achieved**: Delivered a complete, end-to-end, working, clean, and proctor-secure hiring portal.
* **Future Scaling**:
  - Integration with WhatsApp / SMS API for outreach.
  - Multi-lingual interview support using localized Web Speech models.
  - Advanced voice biometrics to prevent candidate identity spoofing.
