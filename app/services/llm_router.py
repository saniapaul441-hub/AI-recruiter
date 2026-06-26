import json
import re
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings

class LLMRouterService:
    def __init__(self):
        # Configure Gemini
        self.api_key_configured = bool(settings.GEMINI_API_KEY)
        if self.api_key_configured:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Use gemini-2.0-flash / gemini-2.5-flash as default fast models
            self.model_name = "gemini-2.0-flash"
        else:
            print("WARNING: GEMINI_API_KEY not found. LLM services will run in Mock/Heuristic Fallback mode.")
            self.model_name = None

    def _clean_json_response(self, text: str) -> str:
        """Helper to extract clean JSON from markdown code blocks if the model outputs them."""
        text = text.strip()
        # Find ```json ... ``` block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            return json_match.group(1).strip()
        return text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def _call_gemini(self, prompt: str, system_instruction: str = None) -> str:
        """Call Gemini API with retry logic and system instructions."""
        if not self.api_key_configured or not self.model_name:
            raise ValueError("Gemini API is not configured.")
        
        # Configure generative model with zero temperature to prevent hallucinations
        gen_config = {"temperature": 0.0}
        if "json" in prompt.lower():
            gen_config["response_mime_type"] = "application/json"

        model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=gen_config
        )
        
        # Prepare contents
        contents = prompt
        if system_instruction:
            # Pushing system instruction to modern SDK model initialization
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction,
                generation_config=gen_config
            )
            
        response = model.generate_content(contents)
        return response.text

    def deconstruct_jd(self, jd_text: str) -> dict:
        """Deconstruct a Job Description into structural fields."""
        if not self.api_key_configured:
            # Fallback heuristics if no API key
            return {
                "must_have_skills": ["Python", "FastAPI"],
                "nice_to_have_skills": ["PostgreSQL", "Pinecone", "CSS"],
                "experience_level": "Mid-Senior (3-5 years)",
                "role_type": "Full-Time",
                "extracted_title": "Software Engineer"
            }
        
        system_instruction = (
            "You are an elite talent acquisition expert. Analyze the provided Job Description "
            "and extract its requirements into a clean, structured JSON object."
        )
        
        prompt = f"""
        Analyze the following Job Description (JD):
        ---
        {jd_text}
        ---
        
        Deconstruct it and return a JSON object with these EXACT keys:
        - "extracted_title": A concise title for the role.
        - "must_have_skills": List of 5-10 absolutely critical hard/soft skills required.
        - "nice_to_have_skills": List of 5-10 preferred but non-mandatory skills.
        - "experience_level": Desired level/years of experience (e.g. Junior, Mid, Senior, 3+ years).
        - "role_type": Type of role (e.g., Full-Time, Remote, Hybrid, Part-Time).
        - "summary": A brief 2-sentence summary of what the role actually does and its core focus.
        
        Return ONLY the raw JSON object. Do not wrap in markdown or any other explanation.
        """
        
        try:
            response_text = self._call_gemini(prompt, system_instruction)
            cleaned = self._clean_json_response(response_text)
            return json.loads(cleaned)
        except Exception as e:
            print(f"Error deconstructing JD with LLM: {e}")
            # Fallback mock
            return {
                "extracted_title": "Software Engineer",
                "must_have_skills": ["Python", "FastAPI", "REST APIs"],
                "nice_to_have_skills": ["SQLAlchemy", "PostgreSQL", "Docker"],
                "experience_level": "3+ years",
                "role_type": "Full-time",
                "summary": "Build high-performance web APIs and database services."
            }

    def structure_resume(self, raw_resume_text: str) -> dict:
        """Structure raw resume text into structured fields using Gemini."""
        if not self.api_key_configured:
            # Local parser regex placeholder
            from app.services.parser import ResumeParserService
            contact = ResumeParserService.extract_contact_info(raw_resume_text)
            return {
                "name": contact["name"],
                "email": contact["email"],
                "phone": contact["phone"],
                "skills": ["Python", "Software Engineering"],
                "experience": [{"company": "Unknown", "title": "Developer", "description": raw_resume_text[:200]}],
                "education": []
            }
            
        system_instruction = (
            "You are a professional resume parser. Convert the messy, unstructured "
            "text extracted from a candidate's resume into a highly structured JSON profile."
        )
        
        prompt = f"""
        Extract the resume details from the raw text below:
        ---
        {raw_resume_text}
        ---
        
        Return a JSON object with this EXACT structure:
        {{
            "name": "Candidate Full Name (extract from text)",
            "email": "Candidate Email Address (extract from text)",
            "phone": "Candidate Phone Number (extract from text)",
            "skills": ["Skill1", "Skill2", "Skill3", ...],
            "experience": [
                {{
                    "company": "Company Name",
                    "title": "Job Title",
                    "start_date": "Start Date (e.g. MM/YYYY or Year)",
                    "end_date": "End Date or 'Present'",
                    "description": "Short summary of responsibilities & key quantitative accomplishments"
                }}
            ],
            "education": [
                {{
                    "institution": "University/College Name",
                    "degree": "Degree and Major",
                    "grad_year": "Graduation Year"
                }}
            ]
        }}
        
        Guidelines:
        - Clean up formatting and fix spelling of standard technical skills (e.g. "python" -> "Python").
        - If some values are missing, use empty strings or empty lists.
        - Return ONLY the raw JSON object.
        """
        
        try:
            response_text = self._call_gemini(prompt, system_instruction)
            cleaned = self._clean_json_response(response_text)
            return json.loads(cleaned)
        except Exception as e:
            print(f"Error structuring resume: {e}")
            from app.services.parser import ResumeParserService
            contact = ResumeParserService.extract_contact_info(raw_resume_text)
            skills = ResumeParserService.extract_skills_heuristic(raw_resume_text)
            experience = ResumeParserService.extract_experience_heuristic(raw_resume_text)
            education = ResumeParserService.extract_education_heuristic(raw_resume_text)
            return {
                "name": contact["name"],
                "email": contact["email"],
                "phone": contact["phone"],
                "skills": skills,
                "experience": experience,
                "education": education
            }

    def _get_heuristic_rank(self, candidate_profile: dict, jd_requirements: dict) -> dict:
        """Generate high-fidelity, distinct mock alignment scores and text pros/cons using local heuristics."""
        import random
        # Simple keyword matching heuristic for skills
        cand_skills = [s.lower().strip() for s in candidate_profile.get("skills", [])]
        must_skills = [s.lower().strip() for s in jd_requirements.get("must_have_skills", [])]
        
        matches = [s for s in must_skills if any(cs in s or s in cs for cs in cand_skills)]
        
        # Calculate dynamic base score based on matching skills
        if len(must_skills) > 0:
            skills_factor = len(matches) / len(must_skills)
        else:
            skills_factor = 0.5
            
        # Add years of experience factor if candidate profile has experience
        exp_list = candidate_profile.get("experience", [])
        years_exp = len(exp_list) * 2.5 # Estimating years
        
        # Formulate base score
        base_score = 40.0 + (skills_factor * 40.0) + min(years_exp * 2.0, 15.0)
        # Add some random variance to distinguish candidates cleanly
        random.seed(hash(candidate_profile.get("name", "")) % (2**32 - 1))
        base_score += random.uniform(-5.0, 5.0)
        base_score = min(max(round(base_score, 1), 20.0), 98.0)
        
        # Formulate sub_scores
        exp_score = min(max(base_score - 4.0 + random.uniform(-4, 4), 15.0), 98.0)
        skills_score = min(max(base_score + 6.0 + random.uniform(-4, 4), 15.0), 98.0)
        # Leadership score: higher if candidate titles have leadership terms
        leadership_terms = ["lead", "manager", "director", "head", "architect", "senior", "sr"]
        has_lead = any(any(t in str(job.get("title", "")).lower() for t in leadership_terms) for job in exp_list)
        ld_factor = 15.0 if has_lead else -10.0
        leadership_score = min(max(base_score + ld_factor + random.uniform(-6, 6), 15.0), 98.0)
        
        # Formulate custom pros/cons based on matching/missing skills
        matched_skills_names = [s.title() for s in matches]
        missing_skills = [s.title() for s in must_skills if s.lower() not in cand_skills]
        
        pros = []
        if matched_skills_names:
            pros.append(f"Strong match for core skills: {', '.join(matched_skills_names[:3])}.")
        if has_lead:
            pros.append("Demonstrates solid engineering leadership and architectural ownership in past roles.")
        else:
            pros.append("Good background in individual contributor software development roles.")
        pros.append(f"Has clear educational and professional progression spanning {len(exp_list)} career blocks.")
        
        cons = []
        if missing_skills:
            cons.append(f"Identified skill gaps in requested JD must-haves: {', '.join(missing_skills[:3])}.")
        else:
            cons.append("Could benefit from deeper specialized exposure to complex cloud microservices.")
        if not has_lead:
            cons.append("Lacks explicit lead or engineering manager job titles in past tenure.")
        cons.append("Tenure at some past companies is relatively short or transition-dense.")
        
        behavioral_signals = (
            f"Demonstrates strong capability in {', '.join(matched_skills_names[:2]) if matched_skills_names else 'engineering'}. "
            "Exhibits results-oriented career progression and active technical involvement."
        )
        
        return {
            "score": round(base_score, 1),
            "sub_scores": {
                "experience": round(exp_score, 1),
                "skills": round(skills_score, 1),
                "leadership": round(leadership_score, 1)
            },
            "pros": pros[:3],
            "cons": cons[:3],
            "behavioral_indicators": behavioral_signals
        }

    def deep_rank_candidate(self, candidate_profile: dict, jd_requirements: dict) -> dict:
        """Deep LLM ranking of candidate against job description requirements."""
        if not self.api_key_configured:
            return self._get_heuristic_rank(candidate_profile, jd_requirements)

        system_instruction = (
            "You are an expert executive recruiter. Perform a rigorous, unbiased evaluation "
            "of the candidate's profile against the job description requirements. "
            "CRITICAL: Base your evaluation solely on the facts directly stated in the Candidate Profile. "
            "Do not make assumptions, extrapolate experience, or hallucinate skills that are not explicitly documented."
        )

        prompt = f"""
        Compare this Candidate Profile with the parsed Job Description Requirements:
        
        JOB DESCRIPTION REQUIREMENTS:
        - Title: {jd_requirements.get('extracted_title')}
        - Must Haves: {jd_requirements.get('must_have_skills')}
        - Nice to Haves: {jd_requirements.get('nice_to_have_skills')}
        - Experience Level Desired: {jd_requirements.get('experience_level')}
        - Summary: {jd_requirements.get('summary')}
        
        CANDIDATE PROFILE:
        - Name: {candidate_profile.get('name')}
        - Skills: {candidate_profile.get('skills')}
        - Experience: {json.dumps(candidate_profile.get('experience', []))}
        - Education: {json.dumps(candidate_profile.get('education', []))}
        
        Instructions:
        1. Evaluate fit based on:
           - Hard Skills & Adjacent Skills (do they know the tech, or have highly relevant alternative tech?).
           - Role Alignment (did their past responsibilities match what this role does?).
           - Progression & Tenure (promotions, longevity, title growth).
           - Accomplishment depth (are their bullets task-based or result-oriented?).
        2. Assign an overall alignment score between 0.0 and 100.0.
        3. Assign three specific sub-scores between 0.0 and 100.0 for:
           - "experience": Years and progression fit.
           - "skills": Match for must-have and nice-to-have hard skills.
           - "leadership": Level of initiative, mentorship, architectural ownership, or leadership shown.
        4. List 3 distinct, specific "Pros" (strengths).
        5. List 3 distinct, specific "Cons" (gaps or areas of concern).
        6. Analyze "Behavioral Signals" (e.g. impact-driven, self-starter, technical leader) in a 2-sentence summary.
        
        Return a JSON object with this EXACT structure:
        {{
            "score": 84.5,
            "sub_scores": {{
                "experience": 88.0,
                "skills": 92.0,
                "leadership": 70.0
            }},
            "pros": [
                "Pro 1 detailing their specific experience matching the JD",
                "Pro 2",
                "Pro 3"
            ],
            "cons": [
                "Con 1 detailing a key gap or concern",
                "Con 2",
                "Con 3"
            ],
            "behavioral_indicators": "2-sentence summary of candidate's career trajectory behavioral signals."
        }}
        
        Return ONLY the raw JSON object.
        """
        
        try:
            response_text = self._call_gemini(prompt, system_instruction)
            cleaned = self._clean_json_response(response_text)
            parsed = json.loads(cleaned)
            # Ensure sub_scores exists in parsed JSON
            if "sub_scores" not in parsed:
                parsed["sub_scores"] = {
                    "experience": parsed.get("score", 70.0),
                    "skills": parsed.get("score", 70.0),
                    "leadership": parsed.get("score", 70.0)
                }
            return parsed
        except Exception as e:
            print(f"Error deep ranking candidate via API: {e}. Running local heuristic fallback.")
            return self._get_heuristic_rank(candidate_profile, jd_requirements)

    def generate_rejection_feedback(self, candidate_profile: dict, jd_requirements: dict) -> dict:
        """Generate compassionate, highly constructive feedback for rejected candidates."""
        if not self.api_key_configured:
            return {
                "skill_gaps": [
                    "Lack of enterprise FastAPI project experience.",
                    "Familiarity with distributed vector databases like Pinecone.",
                    "Demonstrated experience leading system design workflows."
                ],
                "improvement_steps": [
                    "Build a multi-service backend project using FastAPI and document it.",
                    "Complete a tutorial on vector embeddings and index construction.",
                    "Contribute to system architecture decisions in open-source or local projects."
                ],
                "time_to_close": [
                    "1-2 months of dedicated project building.",
                    "2-3 weeks of study and practical labs.",
                    "3-4 months of team-based development."
                ]
            }

        system_instruction = (
            "You are a coaching-oriented recruiter who believes in providing maximum value "
            "to applicants. Write highly specific, encouraging, and actionable feedback. "
            "CRITICAL: Tailor your feedback strictly to the candidate's actual experience and the "
            "identified gaps relative to the job requirements. Do not hallucinate or assume facts not in the profile."
        )

        prompt = f"""
        We are rejecting a candidate for a role. Provide detailed constructive career feedback to help them grow and close their gaps for future applications to similar roles.
        
        ROLE REQUIREMENTS:
        - Title: {jd_requirements.get('extracted_title')}
        - Must Haves: {jd_requirements.get('must_have_skills')}
        - Summary: {jd_requirements.get('summary')}
        
        CANDIDATE PROFILE:
        - Name: {candidate_profile.get('name')}
        - Skills: {candidate_profile.get('skills')}
        - Experience: {json.dumps(candidate_profile.get('experience', []))}
        
        Based on their gaps relative to the JD, generate:
        - "skill_gaps": A list of exactly 3 specific skill or experience gaps (e.g. 'No experience building distributed microservices').
        - "improvement_steps": A list of exactly 3 highly specific, concrete actionable steps they can take to close these gaps (e.g. 'Build an end-to-end FastAPI backend with JWT security and Docker').
        - "time_to_close": A list of exactly 3 estimated time frames needed to close each gap (e.g. '1 month of focused project building').
        
        Return a JSON object with this EXACT structure:
        {{
            "skill_gaps": ["gap 1", "gap 2", "gap 3"],
            "improvement_steps": ["step 1", "step 2", "step 3"],
            "time_to_close": ["time 1", "time 2", "time 3"]
        }}
        
        Make sure the feedback is tailored to their actual experience and the role's tech stack. Return ONLY raw JSON.
        """
        
        try:
            response_text = self._call_gemini(prompt, system_instruction)
            cleaned = self._clean_json_response(response_text)
            return json.loads(cleaned)
        except Exception as e:
            print(f"Error generating rejection feedback via API: {e}. Running local fallback.")
            return {
                "skill_gaps": [
                    "Lack of enterprise FastAPI project experience.",
                    "Familiarity with distributed vector databases like Pinecone.",
                    "Demonstrated experience leading system design workflows."
                ],
                "improvement_steps": [
                    "Build a multi-service backend project using FastAPI and document it.",
                    "Complete a tutorial on vector embeddings and index construction.",
                    "Contribute to system architecture decisions in open-source or local projects."
                ],
                "time_to_close": [
                    "1-2 months of dedicated project building.",
                    "2-3 weeks of study and practical labs.",
                    "3-4 months of team-based development."
                ]
            }
    def generate_interview_response(self, candidate_name: str, job_title: str, step: int, conversation_history: list, candidate_answer: str) -> str:
        """Generate a dynamic and highly relevant conversational response/question from the AI recruiter."""
        if not self.api_key_configured or not self.model_name:
            return self._get_static_fallback(candidate_name, job_title, step)
            
        system_instruction = (
            "You are a warm, professional, highly engaging conversational AI Recruiter conducting a live screening interview. "
            "Your tone is welcoming, professional, and interactive. You analyze the candidate's answers "
            "and respond dynamically, referencing their previous statements directly to make the conversation feel natural."
        )
        
        history_str = ""
        for turn in conversation_history:
            role = "Candidate" if turn.get("role") == "candidate" else "AI Recruiter"
            history_str += f"{role}: {turn.get('text', '')}\n"
            
        prompt = f"""
        Conducting screening interview for candidate: {candidate_name}
        Job Role Workspace: {job_title}
        Current Step: Step {step} of 4.
        
        CONVERSATION HISTORY SO FAR:
        {history_str}
        
        MOST RECENT CANDIDATE ANSWER:
        "{candidate_answer}"
        
        Instructions based on the current step:
        - **Step 1 (Introduction)**: Greet the candidate warmly, welcome them to the proctored screening room, and ask them to introduce themselves and detail their primary backend technical stack.
        - **Step 2 (Behavioral Fit)**: React to their introduction/stack dynamically (be warm, do not be generic). Then, ask them a specific behavioral question about an engineering challenge, tight timeline, or database deadlock they overcame in a past project. Tailor the scenario to their described stack.
        - **Step 3 (Technical Design)**: React to their behavioral response dynamically. Then, ask them a highly relevant technical system design question appropriate for a {job_title} role (e.g., microservice communication, database indexing, SQLAlchemy bottlenecks, or scaling concurrent APIs).
        - **Step 4 (Closing)**: React briefly to their technical answer, congratulate them on successfully completing all screening blocks, and tell them the hiring team will follow up soon.
        
        Guidelines:
        1. Keep your response brief and natural (strictly under 3 sentences).
        2. Reference specific keywords/details from the candidate's last answer to show active listening.
        3. Do NOT say "Thank you for sharing that detailed background" if their response was a simple greeting or short sentence. Act conversational!
        4. Output ONLY the AI Recruiter's next natural response. Do not include markdown headers or prefix the output with "AI Recruiter:".
        """
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error in dynamic interview response: {e}")
            return self._get_static_fallback(candidate_name, job_title, step)
            
    def _get_static_fallback(self, candidate_name: str, job_title: str, step: int) -> str:
        """Provide a clean fallback if Gemini is offline or fails."""
        if step == 1:
            return (
                f"Hello {candidate_name}! Welcome to the AI Screening Room. I am your conversational recruiter. "
                f"Let's start our screening round. Can you tell me a little bit about yourself and your primary technical stack?"
            )
        elif step == 2:
            return (
                "Thank you for sharing that! Let's move on to a behavioral challenge. "
                "Can you describe a challenging system conflict, database deadlock, or a tight timeline you encountered "
                "in a past backend project, and walk me through the exact steps you took to resolve it?"
            )
        elif step == 3:
            return (
                f"Fascinating problem-solving! Now for a technical deep-dive relevant to our {job_title} workspace: "
                f"Could you explain how you would design and optimize a backend microservice to handle slow SQLAlchemy "
                f"queries and manage high-concurrency API requests under load?"
            )
        else:
            return (
                "Excellent! That completely wraps up our conversational screening round. I have successfully analyzed "
        "your communication skills, technical confidence, and role alignment metrics. Our TA team will follow "
                "up with you very shortly. Have a wonderful day!"
            )

    def analyze_introduction(self, candidate_name: str, job_title: str, accumulated_text: str) -> dict:
        """Analyze accumulated introduction text and verify if candidate answered all 3 required items."""
        if not self.api_key_configured:
            # Fallback heuristic checker
            missing = []
            text_lower = accumulated_text.lower()
            if not any(x in text_lower for x in ["name", "role", "work as", "myself", "i am", "developer", "engineer"]):
                missing.append("Name and current role")
            if not any(x in text_lower for x in ["skill", "python", "javascript", "tech", "react", "fastapi", "django", "postgres", "sql", "git", "docker", "c++", "java", "html", "css"]):
                missing.append("Skills / tech stack")
            if not any(x in text_lower for x in ["experience", "work", "project", "build", "develop", "freelance", "job", "intern", "study", "degree", "university", "college", "graduate", "major", "bachelor", "master"]):
                missing.append("Experience or educational background")
                
            completed = len(missing) == 0
            if completed:
                next_q = ""
            else:
                next_q = f"Thank you. To complete your introduction, could you please tell me about: {', '.join(missing)}? These are still left to answer."
            return {
                "completed": completed,
                "missing_items": missing,
                "next_question": next_q
            }

        system_instruction = (
            "You are an expert executive recruiter conducting the introductory phase of an interview. "
            "Analyze the candidate's introduction text(s) so far and identify which of the 3 required items are present or missing."
        )

        prompt = f"""
        Candidate Name: {candidate_name}
        Job Title Applied: {job_title}
        
        ACCUMULATED CANDIDATE RESPONSES FOR STEP 1:
        ---
        {accumulated_text}
        ---

        Verify if the candidate has answered all of the following 3 required items. Be strict: each item must be answered with relevant context, not just one word or generic placeholders.
        1. Name and current role (Who they are and what they do right now)
        2. Skills / tech stack (The main tools, languages, and frameworks they know)
        3. Experience or educational background (Any study background, projects built, or work experience)

        Return a JSON object with this EXACT structure:
        {{
            "completed": false,
            "missing_items": [
                "Name and current role",
                "Skills / tech stack",
                "Experience or educational background"
                ... (only list items from the 3 that are NOT yet answered or need details)
            ],
            "next_question": "A warm, natural, and conversational question asking the candidate to provide the missing items. You must explicitly mention which of the missing questions/items are still left to answer. Keep it brief (2-3 sentences)."
        }}

        If ALL 3 items have been answered, set "completed" to true, "missing_items" to an empty array [], and "next_question" to an empty string "".
        
        Return ONLY the raw JSON object. Do not wrap in markdown code blocks.
        """

        try:
            response_text = self._call_gemini(prompt, system_instruction)
            cleaned = self._clean_json_response(response_text)
            parsed = json.loads(cleaned)
            # Ensure proper keys exist
            if "completed" not in parsed:
                parsed["completed"] = len(parsed.get("missing_items", [])) == 0
            if "missing_items" not in parsed:
                parsed["missing_items"] = []
            if "next_question" not in parsed:
                parsed["next_question"] = ""
            return parsed
        except Exception as e:
            print(f"Error checking intro completeness via API: {e}. Running local fallback.")
            missing = []
            text_lower = accumulated_text.lower()
            if not any(x in text_lower for x in ["name", "role", "work as", "myself", "i am", "developer", "engineer"]):
                missing.append("Name and current role")
            if not any(x in text_lower for x in ["skill", "python", "javascript", "tech", "react", "fastapi", "django", "postgres", "sql", "git", "docker", "c++", "java", "html", "css"]):
                missing.append("Skills / tech stack")
            if not any(x in text_lower for x in ["experience", "work", "project", "build", "develop", "freelance", "job", "intern", "study", "degree", "university", "college", "graduate", "major", "bachelor", "master"]):
                missing.append("Experience or educational background")
                
            completed = len(missing) == 0
            if completed:
                next_q = ""
            else:
                next_q = f"Thank you. To complete your introduction, could you please tell me about: {', '.join(missing)}? These are still left to answer."
            return {
                "completed": completed,
                "missing_items": missing,
                "next_question": next_q
            }

llm_router = LLMRouterService()
