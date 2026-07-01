import json
import csv
import gzip
import argparse
import sys
import os
import re
import datetime

# List of service/consulting companies for background check
SERVICES_LIST = {
    'tcs', 'infosys', 'wipro', 'accenture', 'cognizant', 'capgemini', 'mphasis', 'mindtree', 
    'tech mahindra', 'l&t', 'ltts', 'deloitte', 'ey', 'pwc', 'kpmg', 'genpact', 'ibm', 'hcl', 
    'tata consultancy', 'cts', 'infosys limited', 'wipro limited', 'accenture services'
}

def is_service_company(company_name):
    if not company_name:
        return False
    name_lower = company_name.lower().strip()
    for s in SERVICES_LIST:
        if s in name_lower:
            return True
    return False

def build_pattern(keywords):
    patterns = []
    for kw in keywords:
        p = re.escape(kw).replace(r'\ ', r'[-\s]').replace(r'\-', r'[-\s]')
        patterns.append(rf'\b{p}\b')
    return re.compile('|'.join(patterns), re.IGNORECASE)

# Keywords for match patterns
DENSE_KEYWORDS = ['embedding', 'sentence-transformers', 'openai embeddings', 'bge', 'e5', 'dense retrieval', 'bert', 'cross-encoder', 'bi-encoder']
VECTOR_KEYWORDS = ['pinecone', 'weaviate', 'qdrant', 'milvus', 'elasticsearch', 'opensearch', 'faiss', 'hybrid search', 'vector search', 'vector database', 'chroma', 'hnsw', 'ann', 'approximate nearest neighbor', 'bm25']
PYTHON_KEYWORDS = ['python', 'pyspark', 'numpy', 'pandas', 'scipy', 'scikit-learn', 'pytorch', 'tensorflow', 'keras']
EVAL_KEYWORDS = ['ndcg', 'mrr', 'map', 'mean average precision', 'discounted cumulative gain', 'mean reciprocal rank', 'evaluation framework', 'ab testing', 'a/b testing', 'offline evaluation', 'online evaluation', 'precision@', 'recall@', 'eval framework']
NICE_KEYWORDS = ['lora', 'qlora', 'peft', 'parameter-efficient', 'fine-tune', 'fine tuning', 'finetune', 'finetuned', 'learning to rank', 'learning-to-rank', 'ltr', 'xgboost', 'lightgbm', 'gradient boosting', 'ranknet', 'lambdarank', 'lambdamart']
DOMAIN_KEYWORDS = ['hr-tech', 'hrtech', 'recruiting tech', 'recruitment tech', 'marketplace', 'talent acquisition', 'talent intelligence', 'job matching', 'candidate matching']
DIST_KEYWORDS = ['distributed systems', 'inference optimization', 'triton', 'onnx', 'tensorrt', 'kubernetes', 'docker', 'ray', 'deepspeed', 'torchrun', 'openmp', 'cuda']

# Compile regex patterns
DENSE_PATTERN = build_pattern(DENSE_KEYWORDS)
VECTOR_PATTERN = build_pattern(VECTOR_KEYWORDS)
PYTHON_PATTERN = build_pattern(PYTHON_KEYWORDS)
EVAL_PATTERN = build_pattern(EVAL_KEYWORDS)
NICE_PATTERN = build_pattern(NICE_KEYWORDS)
DOMAIN_PATTERN = build_pattern(DOMAIN_KEYWORDS)
DIST_PATTERN = build_pattern(DIST_KEYWORDS)

# Title patterns
AI_ML_TITLES = ['ai engineer', 'ml engineer', 'machine learning engineer', 'applied ml', 'nlp engineer', 'search engineer', 'retrieval engineer', 'ranking engineer', 'applied ai', 'founding ai engineer', 'founding ml engineer']
SECONDARY_TITLES = ['data scientist', 'nlp scientist', 'deep learning engineer', 'computer vision engineer', 'speech engineer', 'nlp researcher', 'ml scientist', 'research scientist']
ADJACENT_TITLES = ['software engineer', 'backend engineer', 'data engineer', 'full stack engineer', 'software developer', 'systems engineer', 'devops engineer']
MISFIT_TITLES = ['marketing', 'sales', 'hr', 'human resources', 'civil', 'mechanical', 'chemical', 'finance', 'operations', 'accountant', 'designer', 'graphic', 'content writer', 'copywriter', 'business analyst', 'project manager', 'scrum master', 'product owner']

AI_ML_TITLE_PATTERN = build_pattern(AI_ML_TITLES)
SECONDARY_TITLE_PATTERN = build_pattern(SECONDARY_TITLES)
ADJACENT_TITLE_PATTERN = build_pattern(ADJACENT_TITLES)
MISFIT_TITLE_PATTERN = build_pattern(MISFIT_TITLES)

def is_honeypot(candidate, current_date=datetime.date(2026, 6, 30)):
    profile = candidate.get("profile", {})
    yoe = profile.get("years_of_experience", 0)
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    
    # 1. Job duration vs Date range mismatch
    for job in career:
        sd_str = job.get("start_date")
        ed_str = job.get("end_date")
        dur_months = job.get("duration_months", 0)
        if sd_str:
            try:
                sd = datetime.datetime.strptime(sd_str, "%Y-%m-%d").date()
                if ed_str:
                    ed = datetime.datetime.strptime(ed_str, "%Y-%m-%d").date()
                else:
                    ed = current_date
                expected_dur = (ed.year - sd.year) * 12 + (ed.month - sd.month)
                if dur_months - expected_dur > 6:
                    return True
            except Exception:
                pass
                
    # 2. Job duration vs stated YOE mismatch
    for job in career:
        dur_yrs = job.get("duration_months", 0) / 12.0
        if dur_yrs - yoe > 1.0:
            return True
            
    # 3. expert/advanced skills with 0 months >= 3
    expert_zero_months = sum(1 for s in skills if s.get("proficiency") in ["expert", "advanced"] and s.get("duration_months", 0) == 0)
    if expert_zero_months >= 3:
        return True
        
    return False

def score_candidate(candidate, current_date=datetime.date(2026, 6, 30)):
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    
    # ----------------------------------------------------
    # Category A: Title & Career History Relevance (up to 60 points)
    # ----------------------------------------------------
    # 1. Current Title Score (up to 25 points)
    current_title = profile.get("current_title", "").strip()
    title_score = 0.0
    if AI_ML_TITLE_PATTERN.search(current_title):
        title_score = 25.0
    elif SECONDARY_TITLE_PATTERN.search(current_title):
        title_score = 18.0
    elif ADJACENT_TITLE_PATTERN.search(current_title):
        title_score = 10.0
        
    # Check past titles in career history for AI/ML roles (up to 10 points)
    has_past_aiml = False
    has_past_eng = False
    for job in career:
        past_title = job.get("title", "")
        if AI_ML_TITLE_PATTERN.search(past_title) or SECONDARY_TITLE_PATTERN.search(past_title):
            has_past_aiml = True
        if ADJACENT_TITLE_PATTERN.search(past_title):
            has_past_eng = True
            
    career_history_score = 0.0
    if has_past_aiml:
        career_history_score = 10.0
    elif has_past_eng:
        career_history_score = 5.0
        
    # 2. YoE Score (up to 15 points)
    yoe = profile.get("years_of_experience", 0)
    yoe_score = 0.0
    if 6.0 <= yoe <= 8.0:
        yoe_score = 15.0
    elif 5.0 <= yoe <= 9.0:
        yoe_score = 12.0
    elif 4.0 <= yoe <= 10.0:
        yoe_score = 8.0
    elif 3.0 <= yoe <= 12.0:
        yoe_score = 5.0
    else:
        yoe_score = 1.0
        
    # A candidate with no technical title/career history gets 0 for YOE and Title
    has_tech_title = (title_score > 0.0 or has_past_aiml or has_past_eng)
    if not has_tech_title:
        yoe_score = 0.0
        title_score = 0.0
        career_history_score = 0.0
        
    # Penalty for completely misfit current title
    misfit_penalty = 0.0
    if MISFIT_TITLE_PATTERN.search(current_title):
        misfit_penalty = 40.0
        
    category_a_pre_penalty = title_score + career_history_score + yoe_score
    
    # 3. Career Path/Company Penalties
    penalties = 0.0
    
    # consulting check
    companies = [job.get("company", "") for job in career if job.get("company")]
    if companies:
        all_services = all(is_service_company(c) for c in companies)
        current_company = profile.get("current_company", "")
        current_services = is_service_company(current_company)
    else:
        all_services = False
        current_services = False
        
    if all_services:
        penalties += 30.0
    elif current_services:
        penalties += 5.0
        
    # title chaser check (switching every 1-1.5 years)
    past_jobs = [job for job in career if not job.get("is_current")]
    if len(past_jobs) >= 2:
        total_months = sum(job.get("duration_months", 0) for job in past_jobs)
        avg_tenure = total_months / len(past_jobs)
        if avg_tenure < 18:
            penalties += 10.0
            
    # management/architect drift check
    latest_job = None
    for job in career:
        if job.get("is_current"):
            latest_job = job
            break
    if not latest_job and career:
        latest_job = career[0]
        
    if latest_job:
        l_title = latest_job.get("title", "").lower()
        l_dur = latest_job.get("duration_months", 0)
        if l_dur >= 18 and any(term in l_title for term in ['manager', 'director', 'vp', 'architect', 'tech lead', 'technical lead']):
            l_desc = latest_job.get("description", "").lower()
            coding_terms = ['code', 'coding', 'programming', 'develop', 'python', 'implementation', 'shipped', 'github', 'built', 'writing', 'write']
            if not any(term in l_desc for term in coding_terms):
                penalties += 15.0
                
    # pure research check
    all_desc = " ".join([job.get("description", "") for job in career]).lower()
    research_terms = ['research', 'academic', 'paper', 'publications', 'thesis', 'phd', 'postdoc', 'university', 'laboratory', 'lab']
    prod_terms = ['production', 'deploy', 'shipped', 'scale', 'users', 'infrastructure', 'latency', 'pipeline', 'aws', 'docker', 'kubernetes', 'system']
    has_research = any(term in all_desc for term in research_terms)
    has_prod = any(term in all_desc for term in prod_terms)
    if has_research and not has_prod:
        academic_titles = ['researcher', 'scientist', 'fellow', 'phd', 'postdoc', 'assistant', 'professor']
        all_titles = " ".join([job.get("title", "") for job in career]).lower()
        if any(t in all_titles for t in academic_titles):
            penalties += 20.0
            
    # domain misfit CV/Speech check
    cv_speech_terms = ['computer vision', 'opencv', 'yolo', 'cnn', 'image', 'video', 'speech', 'tts', 'stt', 'whisper', 'audio', 'robotics', 'ros', 'lidar']
    nlp_ir_terms = ['nlp', 'natural language processing', 'text', 'search', 'retrieval', 'ranking', 'rag', 'embeddings', 'bert', 'gpt', 'llm', 'vector', 'elasticsearch', 'faiss', 'pinecone', 'bm25', 'information retrieval']
    skill_names_str = " ".join([s.get("name", "") for s in skills]).lower()
    full_text = (profile.get("headline", "") + " " + profile.get("summary", "") + " " + all_desc + " " + skill_names_str).lower()
    
    has_cv_speech = any(term in full_text for term in cv_speech_terms)
    has_nlp_ir = any(term in full_text for term in nlp_ir_terms)
    if has_cv_speech and not has_nlp_ir:
        penalties += 20.0
        
    category_a_score = max(0.0, category_a_pre_penalty - misfit_penalty - penalties)
    
    # Relevance Multiplier from Category A
    relevance_multiplier = category_a_score / 50.0
    relevance_multiplier = min(1.0, max(0.0, relevance_multiplier))
    
    # ----------------------------------------------------
    # Category B: Skills Relevance (up to 20 points)
    # ----------------------------------------------------
    skills_score = 0.0
    
    # python check
    has_python = PYTHON_PATTERN.search(skill_names_str) or PYTHON_PATTERN.search(full_text)
    if has_python:
        skills_score += 6.0
    else:
        skills_score -= 15.0
        
    # embeddings check
    if DENSE_PATTERN.search(skill_names_str) or DENSE_PATTERN.search(full_text):
        skills_score += 6.0
        
    # vector DB check
    if VECTOR_PATTERN.search(skill_names_str) or VECTOR_PATTERN.search(full_text):
        skills_score += 6.0
        
    # evaluation check
    if EVAL_PATTERN.search(skill_names_str) or EVAL_PATTERN.search(full_text):
        skills_score += 2.0
        
    # nice-to-haves (capped at 2 points)
    nice_pts = 0.0
    if NICE_PATTERN.search(skill_names_str) or NICE_PATTERN.search(full_text):
        nice_pts += 1.0
    if DOMAIN_PATTERN.search(skill_names_str) or DOMAIN_PATTERN.search(full_text):
        nice_pts += 1.0
    if DIST_PATTERN.search(skill_names_str) or DIST_PATTERN.search(full_text):
        nice_pts += 1.0
    skills_score += min(2.0, nice_pts)
        
    # LangChain trap check
    langchain_terms = ['langchain', 'llamaindex', 'openai', 'prompt engineering', 'chatgpt']
    traditional_ml_terms = ['scikit-learn', 'pytorch', 'tensorflow', 'xgboost', 'pandas', 'numpy', 'sql', 'regression', 'classification', 'clustering', 'random forest', 'svm', 'neural network', 'deep learning']
    has_langchain = any(term in full_text for term in langchain_terms)
    has_traditional = any(term in full_text for term in traditional_ml_terms)
    if has_langchain and not has_traditional:
        skills_score -= 15.0
        
    skills_score = max(0.0, min(20.0, skills_score))
    
    # ----------------------------------------------------
    # Category C: Redrob Behavioral Signals (up to 10 points)
    # ----------------------------------------------------
    signals_score = 0.0
    
    # recruiter response rate (up to 4 points)
    resp_rate = signals.get("recruiter_response_rate", 0.0)
    signals_score += resp_rate * 4.0
    
    # active recency (up to 2 points)
    last_active_str = signals.get("last_active_date")
    if last_active_str:
        try:
            last_active = datetime.datetime.strptime(last_active_str, "%Y-%m-%d").date()
            days_inactive = (current_date - last_active).days
            if days_inactive <= 30:
                signals_score += 2.0
            elif days_inactive <= 90:
                signals_score += 1.0
        except:
            pass
            
    # github score (up to 2 points)
    gh_score = signals.get("github_activity_score", -1)
    if gh_score > 50:
        signals_score += 2.0
    elif gh_score >= 10:
        signals_score += 1.0
        
    # notice period (up to 1 point)
    notice_days = signals.get("notice_period_days", 0)
    if notice_days <= 30:
        signals_score += 1.0
    elif notice_days <= 60:
        signals_score += 0.5
        
    # open to work (up to 1 point)
    if signals.get("open_to_work_flag"):
        signals_score += 1.0
        
    signals_score = max(0.0, min(10.0, signals_score))
    
    # ----------------------------------------------------
    # Combine with Relevance Multiplier
    # ----------------------------------------------------
    total_score = category_a_score + skills_score * relevance_multiplier + signals_score * relevance_multiplier
    
    # Normalize final score to 0.0 - 1.0 range
    normalized_score = max(0.0001, min(0.9999, total_score / 90.0))
    return normalized_score

def get_concern_phrase(c, index):
    signals = c.get("redrob_signals", {})
    notice = signals.get("notice_period_days", 0)
    response_rate = signals.get("recruiter_response_rate", 0.0)
    
    career = c.get("career_history", [])
    companies = [job.get("company", "") for job in career]
    is_serv = any(is_service_company(comp) for comp in companies)
    
    parts = []
    if notice >= 60:
        notice_phrases = [
            f"a notice period of {notice} days",
            f"a {notice}-day notice period",
            f"their {notice}-day notice",
            f"a {notice}-day notice"
        ]
        parts.append(notice_phrases[index % len(notice_phrases)])
        
    if is_serv:
        services_phrases = [
            "services company background",
            "service-firm history",
            "consulting background",
            "services background"
        ]
        parts.append(services_phrases[index % len(services_phrases)])
        
    if response_rate < 0.35:
        rate_phrases = [
            f"a low response rate of {response_rate:.0%}",
            f"low responsiveness ({response_rate:.0%})",
            f"a response rate of {response_rate:.0%}",
            f"low responsiveness of {response_rate:.0%}"
        ]
        parts.append(rate_phrases[index % len(rate_phrases)])
        
    if not parts:
        return ""
        
    conjunctions = [
        ", though ",
        ", but ",
        "; note: ",
        ", despite ",
        "; however, "
    ]
    conj = conjunctions[index % len(conjunctions)]
    
    return conj + " and ".join(parts)

def generate_reasoning(candidate, rank, score):
    profile = candidate.get("profile", {})
    title = profile.get("current_title", "Software Engineer")
    yoe = profile.get("years_of_experience", 0)
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    career = candidate.get("career_history", [])
    
    # Extract company name of current job
    company = profile.get("current_company", "")
    if not company and career:
        company = career[0].get("company", "their current company")
        
    # Get snippet from career description
    snippet = ""
    if career:
        desc = career[0].get("description", "")
        if desc:
            sentences = re.split(r'[.!?]\s+', desc)
            for sent in sentences:
                sent = sent.strip().replace('"', '').replace("'", "")
                if not sent:
                    continue
                
                # Split by punctuation to find clean sub-clauses
                clauses = re.split(r'[,;()]\s*', sent)
                best_clause = ""
                
                for cl in clauses:
                    cl = cl.strip()
                    cl_lower = cl.lower()
                    if any(cl_lower.startswith(v) for v in ['built', 'implemented', 'designed', 'shipped', 'deployed', 'optimized', 'led', 'created', 'developed', 'trained', 'tuned', 'worked', 'managed', 'supervised']):
                        # Clean trailing prepositions and conjunctions
                        words = cl.split()
                        while words and words[-1].lower() in [
                            'that', 'for', 'with', 'and', 'a', 'an', 'the', 'in', 'on', 'at', 'of', 'to', 'by', 'from', 'as', 'about', 'over', 'under', 'through', 'but', 'or', 'so', 'yet', 'using', 'which',
                            'our', 'your', 'his', 'her', 'their', 'its', 'my', 'us', 'we', 'they', 'them', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had'
                        ]:
                            words.pop()
                        cleaned = " ".join(words)
                        if len(cleaned) > 15 and len(cleaned) < 80:
                            best_clause = cleaned
                            break
                            
                if best_clause:
                    snippet = re.sub(r'[\s\-—–:;,]+$', '', best_clause).lower()
                    break
                else:
                    # Fallback to word-bounded truncation of the first sentence, popping trailing prepositions
                    words = sent.split()
                    if len(words) > 8:
                        words = words[:8]
                    while words and words[-1].lower() in [
                        'that', 'for', 'with', 'and', 'a', 'an', 'the', 'in', 'on', 'at', 'of', 'to', 'by', 'from', 'as', 'about', 'over', 'under', 'through', 'but', 'or', 'so', 'yet', 'using', 'which',
                        'our', 'your', 'his', 'her', 'their', 'its', 'my', 'us', 'we', 'they', 'them', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had'
                    ]:
                        words.pop()
                    fallback = " ".join(words)
                    if fallback:
                        snippet = re.sub(r'[\s\-—–:;,]+$', '', fallback).lower()
                        break
                        
    if not snippet:
        snippet = "shipped production ml features"
        
    # Extract matched skills
    matched_skills = []
    skill_names = [s["name"].lower() for s in skills]
    for s in ["nlp", "embeddings", "vector search", "pinecone", "weaviate", "milvus", "elasticsearch", "faiss", "pytorch", "xgboost"]:
        if s in skill_names:
            matched_skills.append(s)
    skill_str = ", ".join(matched_skills[:2]) if matched_skills else "applied ML/retrieval"
    
    pat_idx = rank % 8
    
    # Dynamic templates based on rank
    if rank <= 15: # Confident, top-tier fit
        templates = [
            f"Outstanding match: this {title} brings {yoe:.1f} years of experience and recently {snippet} at {company}.",
            f"Exceptional candidate with deep expertise in {skill_str} from their work at {company} spanning {yoe:.1f} years.",
            f"Highly recommended: has a proven track record as a {title} ({yoe:.1f} yrs) and recently {snippet}.",
            f"At {company}, this candidate {snippet}; they represent a top-tier {title} with {yoe:.1f} years of experience.",
            f"Excellent founding fit: offers {yoe:.1f} years of experience as a {title}, demonstrating strong skills in {skill_str}.",
            f"Top-tier candidate: an experienced {title} ({yoe:.1f} yrs) who {snippet} in their current role.",
            f"Exceptional fit: highly relevant background in {skill_str} spanning {yoe:.1f} years, including their work to {snippet}.",
            f"Outstanding {title} with {yoe:.1f} years of experience, showing strong matching capabilities in {skill_str}."
        ]
    elif rank <= 50: # Strong candidate
        templates = [
            f"Strong candidate: a {title} with {yoe:.1f} years of experience, who {snippet} at {company}.",
            f"Well-qualified candidate showing solid background in {skill_str} from their work at {company} ({yoe:.1f} yrs).",
            f"Solid fit: features a strong track record as a {title} ({yoe:.1f} yrs), having recently {snippet}.",
            f"At {company}, this candidate {snippet}; they represent a well-suited {title} with {yoe:.1f} years of experience.",
            f"Strong fit: offers {yoe:.1f} years of experience as a {title}, demonstrating relevant skills in {skill_str}.",
            f"Well-suited profile: an experienced {title} ({yoe:.1f} yrs) who {snippet} in their current role.",
            f"Highly relevant background: background in {skill_str} spanning {yoe:.1f} years, including their work to {snippet}.",
            f"Well-qualified {title} with {yoe:.1f} years of experience, showing matching capabilities in {skill_str}."
        ]
    else: # Measured, hedged fit
        templates = [
            f"Adjacent background: a {title} with {yoe:.1f} years of experience, who {snippet} at {company}.",
            f"Alternative match showing adjacent skills in {skill_str} from their work at {company} ({yoe:.1f} yrs).",
            f"Measured fit: features a basic track record as a {title} ({yoe:.1f} yrs), having recently {snippet}.",
            f"At {company}, this candidate {snippet}; they represent a potential {title} with {yoe:.1f} years of experience.",
            f"Acceptable candidate: offers {yoe:.1f} years of experience as a {title}, demonstrating basic adjacent skills in {skill_str}.",
            f"Potential profile: an experienced {title} ({yoe:.1f} yrs) who {snippet} in their current role.",
            f"Measured background: background in {skill_str} spanning {yoe:.1f} years, including their work to {snippet}.",
            f"Acceptable {title} with {yoe:.1f} years of experience, showing adjacent capabilities in {skill_str}."
        ]
        
    phrase = templates[pat_idx]
    
    # Add concerns
    concern = get_concern_phrase(candidate, rank)
    if concern:
        phrase = phrase.rstrip('.') + concern
        
    if not phrase.endswith('.'):
        phrase += '.'
        
    return phrase

def main():
    parser = argparse.ArgumentParser(description="Rank candidates for Senior AI Engineer.")
    parser.add_argument("--candidates", type=str, default=None, help="Path to candidates data file.")
    parser.add_argument("--out", type=str, default="submission.csv", help="Path to output submission CSV.")
    args = parser.parse_args()
    
    # Resolve default candidates file path
    candidates_path = args.candidates
    if not candidates_path:
        default_dir = r"c:\Users\lenovo\OneDrive\Desktop\AI recruiter\ai_recruiter\hacathon_data"
        options = ["candidates.jsonl", "candidates.jsonl.gz", "sample_candidates.json"]
        for opt in options:
            full_opt = os.path.join(default_dir, opt)
            if os.path.exists(full_opt):
                candidates_path = full_opt
                break
                
    if not candidates_path or not os.path.exists(candidates_path):
        print(f"Error: Candidate file not found. Checked default directory.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Loading candidates from {candidates_path}...")
    
    # Load candidates based on file extension
    candidates = []
    if candidates_path.endswith('.json') and not candidates_path.endswith('.jsonl') and not candidates_path.endswith('.jsonl.gz'):
        with open(candidates_path, 'r', encoding='utf-8') as f:
            candidates = json.load(f)
    else:
        open_func = gzip.open if candidates_path.endswith('.gz') else open
        mode = 'rt' if candidates_path.endswith('.gz') else 'r'
        with open_func(candidates_path, mode, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    candidates.append(json.loads(line))
                    
    print(f"Loaded {len(candidates)} candidates.")
    
    scored_candidates = []
    honeypot_count = 0
    
    # Score each candidate and filter honeypots
    for c in candidates:
        if is_honeypot(c):
            honeypot_count += 1
            continue
        score = score_candidate(c)
        scored_candidates.append((score, c["candidate_id"], c))
        
    print(f"Filtered out {honeypot_count} honeypot/anomalous candidates.")
    print(f"Scored {len(scored_candidates)} candidates.")
    
    # Sort candidates:
    # 1. Primary: Score rounded to 4 decimal places descending
    # 2. Secondary: candidate_id ascending (deterministic tie-breaker)
    scored_candidates.sort(key=lambda x: (-round(x[0], 4), x[1]))
    
    # Select top 100
    top_100 = scored_candidates[:100]
    
    print(f"Writing top 100 ranked candidates to {args.out}...")
    
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for idx, (score, cid, c) in enumerate(top_100):
            rank = idx + 1
            rounded_score = round(score, 4)
            reasoning = generate_reasoning(c, rank, rounded_score)
            # Scores must be strictly formatted as float strings (e.g. 0.9520)
            score_str = f"{rounded_score:.4f}"
            writer.writerow([cid, rank, score_str, reasoning])
            
    print("Done! Submission CSV generated successfully.")

if __name__ == "__main__":
    main()
