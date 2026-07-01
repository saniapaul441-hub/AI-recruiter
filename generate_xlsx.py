import os
import json
import sqlite3
import pandas as pd

# Connect to database
db_path = "recruiter.db"
if not os.path.exists(db_path):
    db_path = os.path.join("c:\\Users\\lenovo\\OneDrive\\Desktop\\AI recruiter", "recruiter.db")

conn = sqlite3.connect(db_path)

# Query jobs
jobs_df = pd.read_sql_query("SELECT id, title FROM jobs", conn)

def format_score(score):
    if pd.isnull(score):
        return ""
    # Format with % sign
    if abs(score - round(score)) < 1e-9:
        return f"{int(round(score))}%"
    else:
        return f"{score:.1f}%"

def process_skills(skills_json):
    if not skills_json:
        return ""
    try:
        skills_list = json.loads(skills_json)
        if isinstance(skills_list, list):
            return ", ".join(skills_list)
        return str(skills_list)
    except Exception:
        if isinstance(skills_json, list):
            return ", ".join(skills_json)
        return str(skills_json)

# Generate individual files for all jobs with a standard clean format
generated_files = []

for idx, job_row in jobs_df.iterrows():
    job_id = job_row['id']
    job_title = job_row['title']
    
    query = """
        SELECT 
            c.name as "Candidate Name",
            c.email as "Email",
            c.phone as "Phone",
            r.score as "Score",
            r.status as "Status",
            c.skills as "Skills"
        FROM rankings r
        JOIN candidates c ON r.candidate_id = c.id
        WHERE r.job_id = ?
        ORDER BY r.score DESC
    """
    
    df = pd.read_sql_query(query, conn, params=(job_id,))
    if df.empty:
        continue
        
    df['Skills'] = df['Skills'].apply(process_skills)
    df.insert(0, 'Rank', range(1, len(df) + 1))
    df['Match Score (%)'] = df['Score'].apply(format_score)
    
    final_df = df[['Rank', 'Candidate Name', 'Email', 'Phone', 'Match Score (%)', 'Status', 'Skills']]
    
    # Save with a clean, standardized filename
    # Standard format: ranked_candidates_job_<id>.xlsx
    filename = f"ranked_candidates_job_{job_id}.xlsx"
    final_df.to_excel(filename, index=False)
    generated_files.append((job_title, job_id, filename, len(final_df)))
    
    # Also save with descriptive names
    safe_title = "".join([c if c.isalnum() else "_" for c in job_title]).lower()
    descriptive_filename = f"ranked_candidates_{safe_title}.xlsx"
    final_df.to_excel(descriptive_filename, index=False)
    
    # If it is the primary Job (e.g. Job ID 1 or Job ID 10), let's copy it to 'ranked_candidates.xlsx'
    if job_id == 1:
        final_df.to_excel("ranked_candidates.xlsx", index=False)
        print("Generated default 'ranked_candidates.xlsx' from Job ID 1 (Lead Backend Engineer).")
    elif job_id == 10 and not os.path.exists("ranked_candidates.xlsx"):
        final_df.to_excel("ranked_candidates.xlsx", index=False)
        print("Generated default 'ranked_candidates.xlsx' from Job ID 10 (AI/ML Engineer).")

conn.close()
print("\nAll files successfully generated!")
