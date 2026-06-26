import collections
import collections.abc
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

def create_presentation():
    prs = Presentation()
    
    # Set to widescreen 16:9 aspect ratio
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    # Define premium colors (dark dashboard theme)
    bg_color = RGBColor(15, 15, 27)      # Deep dark blue-black
    title_color = RGBColor(0, 223, 216)   # Neon Cyan
    body_color = RGBColor(255, 255, 255)  # Crisp White
    muted_color = RGBColor(160, 160, 176) # Slate Grey
    
    blank_layout = prs.slide_layouts[6]
    
    slides_data = [
        {
            "is_title_slide": True,
            "title": "AI Recruiter",
            "subtitle": "Intelligent Talent Ingestion & Candidate Alignment System\n\nAutomated Resume Ingestion, Semantic Matching, and Proctor-Secure AI Interviews",
            "meta": "Presenter: Sania\nChandigarh Group of Colleges, Landran\nSubmitted for India Runs by Redrob AI Hackathon (Hack2Skill)"
        },
        {
            "title": "The Core Problem in Recruitment",
            "points": [
                ("Keyword Matching is Broken", "Traditional recruitment software filters profiles using literal keyword matches, missing highly qualified candidates who describe their skills differently."),
                ("Inconsistent Evaluations", "Manual resume reviews are slow and subject to recruiter bias, leading to inconsistent evaluations and missed matches."),
                ("Scale Bottleneck", "Talent acquisition teams spend hours conducting repetitive phone screens and filtering huge stacks of candidates.")
            ]
        },
        {
            "title": "Our Solution Overview",
            "points": [
                ("Double-Layer Candidate Screening", "• Layer 1 (Semantic Similarity): Filter matches instantly based on context and meaning, not just keywords.\n• Layer 2 (Deep LLM Scoring): Uses Google Gemini 2.0 Flash to evaluate candidate fit, list pros/cons, and write feedback."),
                ("Conversational AI Screening Hub", "Interactive, voice-driven screening interview with built-in behavioral telemetry to flag cheating or tab-switching in real-time."),
                ("Developer & Stack Flexibility", "Built primarily with a high-performance Python FastAPI backend, supported by an alternative Node.js Express/Supabase stack.")
            ]
        },
        {
            "title": "System Architecture & Workflow",
            "points": [
                ("1. Role Creation", "Recruiter creates a job description, which the Google Gemini LLM parses into structured Must-Have and Nice-to-Have skills, experience level, and role summary."),
                ("2. Resume Upload & Processing", "Ingests candidate profiles (via CSV/PDF). Cleans and extracts names, emails, phones, and parsed text automatically."),
                ("3. Vector Similarity matching", "Calculates dense 384-dimensional semantic embeddings. Computes cosine similarity of candidate profiles against the job description requirements."),
                ("4. Weight Adjustments", "Recruiter can dynamically adjust sliders (Experience vs. Skills vs. Leadership) to instantly recalculate and rank candidate fit scores.")
            ]
        },
        {
            "title": "Layer 1: Semantic Search & Weighting",
            "points": [
                ("Dense Embeddings Model", "Uses local SentenceTransformers ('all-MiniLM-L6-v2') to compute 384-dimensional dense vectors locally to secure high performance."),
                ("Zero-Crash Local Fallback", "If remote servers or libraries are missing, the system uses local NumPy vector calculations and an in-memory cache to ensure zero-downtime evaluation."),
                ("Dynamic Shortlist Customization", "Features dynamic sliders that allow recruiters to customize candidate rank weighting on-the-fly, bringing total control back to recruiters.")
            ]
        },
        {
            "title": "Layer 2: Deep LLM Evaluation",
            "points": [
                ("Intelligent Fit Scoring", "Gemini 2.0 Flash performs deep text analysis of candidates' career milestones, project details, and technical expertise to assign realistic fit scores."),
                ("Constructive Feedback Loop", "Automatically drafts personalized emails, including structured outreach invites for top matches and customized feedback with learning resources for rejected profiles."),
                ("Outbox Validation Queue", "Queues generated emails in a recruiter outbox for verification, editing, and approval before final transmission via SMTP.")
            ]
        },
        {
            "title": "AI Screening Room & Proctoring",
            "points": [
                ("WebRTC Biometrics Simulation", "Local camera feed is rendered inside the chat portal with a live face landmark canvas to simulate focus tracking."),
                ("Continuous Speech Recognition", "Integrated with the Web Speech API (webkitSpeechRecognition) configured for continuous listening and automatic restart, facilitating natural voice responses."),
                ("Anti-Cheating Telemetry", "Monitors candidate focus, tab-switching, and window blur. Logs warnings immediately to the backend warning API '/api/interviews/proctor/warning/{cand_id}/{job_id}'.")
            ]
        },
        {
            "title": "Workspace Isolation & Compliance Audit",
            "points": [
                ("Secure JWT Authentication", "Access is protected using JSON Web Tokens (JWT) encrypted with bcrypt hashing for secure session logins."),
                ("Recruiter Isolation", "Multi-tenant workspace isolation ensures recruiters only see and manage their own jobs, candidate uploads, and logs."),
                ("Administrative Compliance", "All critical actions (proctoring warnings, uploads, status updates) write directly to a secure compliance Audit Log database table.")
            ]
        },
        {
            "title": "Diagnostic Integrity & Impact",
            "points": [
                ("100% Passed Tests", "All backend diagnostic suites passed: JWT security cryptography, CSV profile ingestion, regex extractors, and workspace isolation."),
                ("Optimized Cost-Efficiency", "Local embedding generation avoids high external API invocation costs, making the platform highly scalable."),
                ("Immediate Ranked Output", "Recruiter dashboard features a live 'Export CSV' button, producing the ranked candidate list in one click for instant submission.")
            ]
        },
        {
            "title": "Conclusion & Future Roadmap",
            "points": [
                ("Functional Summary", "Delivered a complete, working, multi-role recruitment workflow featuring semantic vector search, LLM analysis, and anti-cheating screening."),
                ("Future Extensions", [
                    "Integrate WhatsApp outreach for faster candidate response times.",
                    "Add voice biometrics to verify candidate identity and prevent proxy test-taking.",
                    "Extend multi-lingual interview support using localized Web Speech models."
                ])
            ]
        }
    ]
    
    for s_data in slides_data:
        slide = prs.slides.add_slide(blank_layout)
        
        # Set dark background
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = bg_color
        
        if s_data.get("is_title_slide"):
            # Title slide layout
            title_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.5), Inches(11.3), Inches(1.5))
            tf = title_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = s_data["title"]
            p.font.size = Pt(56)
            p.font.bold = True
            p.font.color.rgb = title_color
            p.font.name = "Segoe UI"
            
            sub_box = slide.shapes.add_textbox(Inches(1.0), Inches(3.0), Inches(11.3), Inches(2.0))
            tf_sub = sub_box.text_frame
            tf_sub.word_wrap = True
            p_sub = tf_sub.paragraphs[0]
            p_sub.text = s_data["subtitle"]
            p_sub.font.size = Pt(22)
            p_sub.font.color.rgb = body_color
            p_sub.font.name = "Segoe UI"
            
            meta_box = slide.shapes.add_textbox(Inches(1.0), Inches(5.2), Inches(11.3), Inches(1.5))
            tf_meta = meta_box.text_frame
            tf_meta.word_wrap = True
            p_meta = tf_meta.paragraphs[0]
            p_meta.text = s_data["meta"]
            p_meta.font.size = Pt(14)
            p_meta.font.color.rgb = muted_color
            p_meta.font.name = "Segoe UI"
            
        else:
            # Standard slide layout
            # Add slide title
            title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(1.0))
            tf = title_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = s_data["title"]
            p.font.size = Pt(36)
            p.font.bold = True
            p.font.color.rgb = title_color
            p.font.name = "Segoe UI"
            
            # Add points text box
            content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.0))
            tf_content = content_box.text_frame
            tf_content.word_wrap = True
            
            first = True
            for pt in s_data["points"]:
                if isinstance(pt, tuple):
                    pt_title, pt_desc = pt
                    p_title = tf_content.add_paragraph() if not first else tf_content.paragraphs[0]
                    first = False
                    p_title.text = pt_title
                    p_title.font.size = Pt(20)
                    p_title.font.bold = True
                    p_title.font.color.rgb = title_color
                    p_title.font.name = "Segoe UI"
                    p_title.space_before = Pt(14)
                    
                    if isinstance(pt_desc, list):
                        for sub_pt in pt_desc:
                            p_sub = tf_content.add_paragraph()
                            p_sub.text = "• " + sub_pt
                            p_sub.font.size = Pt(15)
                            p_sub.font.color.rgb = body_color
                            p_sub.font.name = "Segoe UI"
                            p_sub.space_before = Pt(4)
                    else:
                        p_desc = tf_content.add_paragraph()
                        p_desc.text = pt_desc
                        p_desc.font.size = Pt(15)
                        p_desc.font.color.rgb = body_color
                        p_desc.font.name = "Segoe UI"
                        p_desc.space_before = Pt(4)
                else:
                    pt_title, pt_list = pt
                    p_title = tf_content.add_paragraph() if not first else tf_content.paragraphs[0]
                    first = False
                    p_title.text = pt_title
                    p_title.font.size = Pt(20)
                    p_title.font.bold = True
                    p_title.font.color.rgb = title_color
                    p_title.font.name = "Segoe UI"
                    p_title.space_before = Pt(14)
                    
                    if isinstance(pt_list, list):
                        for sub_pt in pt_list:
                            p_sub = tf_content.add_paragraph()
                            p_sub.text = "• " + sub_pt
                            p_sub.font.size = Pt(15)
                            p_sub.font.color.rgb = body_color
                            p_sub.font.name = "Segoe UI"
                            p_sub.space_before = Pt(4)
                    else:
                        p_desc = tf_content.add_paragraph()
                        p_desc.text = pt_list
                        p_desc.font.size = Pt(15)
                        p_desc.font.color.rgb = body_color
                        p_desc.font.name = "Segoe UI"
                        p_desc.space_before = Pt(4)
                        
    prs.save("AI_Recruiter_Presentation.pptx")
    print("AI_Recruiter_Presentation.pptx generated successfully!")

if __name__ == "__main__":
    create_presentation()
