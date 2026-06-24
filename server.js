const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const multer = require('multer');
const path = require('path');
const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { createClient } = require('@supabase/supabase-js');
const pdfParse = require('pdf-parse');
const mammoth = require('mammoth');

// Load configurations
dotenv.config();

const app = express();
const PORT = process.env.PORT || 8000;
const JWT_SECRET = process.env.JWT_SECRET || process.env.SECRET_KEY || 'ai-recruiter-jwt-default-super-secret-key';

// Initialize Supabase Client
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_KEY;
if (!supabaseUrl || !supabaseKey) {
    console.warn('WARNING: SUPABASE_URL or SUPABASE_KEY is missing. Database calls will fail.');
}
const supabase = createClient(supabaseUrl || '', supabaseKey || '');

// Middleware
app.use(cors());
app.use(express.json());

// Serving Static Files
app.use('/static', express.static(path.join(__dirname, 'static')));
app.use(express.static(path.join(__dirname, 'static')));

// Multer Config for memory storage uploads
const upload = multer({
    storage: multer.memoryStorage(),
    limits: { fileSize: 10 * 1024 * 1024 } // 10MB limit
});

// Authentication Middleware
const authenticateJWT = (req, res, next) => {
    const authHeader = req.headers.authorization;
    if (authHeader && authHeader.startsWith('Bearer ')) {
        const token = authHeader.split(' ')[1];
        jwt.verify(token, JWT_SECRET, (err, user) => {
            if (err) {
                return res.status(401).json({ detail: 'Could not validate credentials' });
            }
            req.user = user;
            next();
        });
    } else {
        return res.status(401).json({ detail: 'Not authenticated' });
    }
};

// Admin Auth Middleware
const requireAdmin = (req, res, next) => {
    if (req.user && req.user.role === 'admin') {
        next();
    } else {
        return res.status(403).json({ detail: 'Forbidden: Admin access required' });
    }
};

// Log Audit Helper
async function logAudit(recruiterId, action, details) {
    try {
        await supabase.from('audit_logs').insert({
            recruiter_id: recruiterId || null,
            action,
            details: details || {}
        });
    } catch (e) {
        console.error('Failed to log audit:', e);
    }
}

// --- CLAUDE API INTEGRATION UTILITIES ---

async function callClaude(prompt, systemInstruction = '') {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
        throw new Error('Anthropic API key is not configured.');
    }
    const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        },
        body: JSON.stringify({
            model: 'claude-3-5-sonnet-20241022',
            max_tokens: 4000,
            system: systemInstruction,
            messages: [{ role: 'user', content: prompt }]
        })
    });
    if (!response.ok) {
        const text = await response.text();
        throw new Error(`Claude API returned status ${response.status}: ${text}`);
    }
    const data = await response.json();
    return data.content[0].text;
}

function cleanJsonResponse(text) {
    let clean = text.trim();
    const match = clean.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
    if (match) {
        clean = match[1].trim();
    }
    return clean;
}

async function deconstructJob(description) {
    if (!process.env.ANTHROPIC_API_KEY) {
        console.warn('Fallback: ANTHROPIC_API_KEY missing. Returning mock JD deconstruction.');
        return {
            extracted_title: 'Backend Software Engineer',
            must_have_skills: ['Python', 'FastAPI', 'PostgreSQL', 'SQLAlchemy'],
            nice_to_have_skills: ['Docker', 'AWS', 'System Design'],
            experience_level: '3+ years',
            role_type: 'Full-Time',
            summary: 'Develop and optimize backend microservices and databases.'
        };
    }
    
    const system = 'You are an elite talent acquisition expert. Analyze the job description and extract requirements into structured JSON.';
    const prompt = `
    Analyze the following Job Description (JD):
    ---
    ${description}
    ---
    
    Deconstruct it and return a JSON object with these EXACT keys:
    - "extracted_title": A concise title for the role.
    - "must_have_skills": List of 5-10 absolutely critical hard/soft skills required.
    - "nice_to_have_skills": List of 5-10 preferred but non-mandatory skills.
    - "experience_level": Desired level/years of experience (e.g. Senior, Mid, Senior, 3+ years).
    - "role_type": Type of role (e.g., Full-Time, Remote, Hybrid, Part-Time).
    - "summary": A brief 2-sentence summary of what the role actually does and its core focus.
    
    Return ONLY the raw JSON object. Do not wrap in explanations.
    `;
    
    try {
        const text = await callClaude(prompt, system);
        const jsonStr = cleanJsonResponse(text);
        return JSON.parse(jsonStr);
    } catch (e) {
        console.error('Error deconstructing job with Claude:', e);
        return {
            extracted_title: 'Backend Software Engineer',
            must_have_skills: ['Python', 'FastAPI', 'PostgreSQL', 'SQLAlchemy'],
            nice_to_have_skills: ['Docker', 'AWS', 'System Design'],
            experience_level: '3+ years',
            role_type: 'Full-Time',
            summary: 'Develop and optimize backend microservices and databases.'
        };
    }
}

async function parseResumeText(buffer, filename) {
    const fileLower = filename.toLowerCase();
    if (fileLower.endsWith('.pdf')) {
        const data = await pdfParse(buffer);
        return data.text || '';
    } else if (fileLower.endsWith('.docx')) {
        const result = await mammoth.extractRawText({ buffer });
        return result.value || '';
    }
    throw new Error('Unsupported file extension. Only PDF and DOCX files are accepted.');
}

async function extractCandidateDetails(rawText) {
    if (!process.env.ANTHROPIC_API_KEY) {
        const emailMatch = rawText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
        const email = emailMatch ? emailMatch[0] : 'unknown@candidate.com';
        const lines = rawText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
        const name = lines.length > 0 ? lines[0].substring(0, 50) : 'Unknown Candidate';
        return {
            name,
            email,
            phone: '',
            skills: ['Python', 'Software Engineering'],
            experience_years: 3
        };
    }
    
    const system = 'You are a professional resume parser. Convert candidate raw text into clean structured JSON profiles.';
    const prompt = `
    Extract the candidate's name, email address, phone number, a list of professional skills, and their estimated years of experience from the raw resume text:
    ---
    ${rawText}
    ---
    
    Return a JSON object with this EXACT structure:
    {
      "name": "Candidate Full Name",
      "email": "Candidate Email Address",
      "phone": "Candidate Phone Number",
      "skills": ["Skill1", "Skill2", "Skill3"],
      "experience_years": 4.5
    }
    
    Guidelines:
    - If some values are missing, use empty strings or empty arrays.
    - Return ONLY the raw JSON object.
    `;
    
    try {
        const text = await callClaude(prompt, system);
        const jsonStr = cleanJsonResponse(text);
        return JSON.parse(jsonStr);
    } catch (e) {
        console.error('Error parsing resume with Claude:', e);
        const emailMatch = rawText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
        const email = emailMatch ? emailMatch[0] : 'unknown@candidate.com';
        const lines = rawText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
        const name = lines.length > 0 ? lines[0].substring(0, 50) : 'Unknown Candidate';
        return {
            name,
            email,
            phone: '',
            skills: ['Python', 'Software Engineering'],
            experience_years: 3
        };
    }
}

async function rankCandidate(candidate, job, weights) {
    if (!process.env.ANTHROPIC_API_KEY) {
        return {
            score: 75.0,
            sub_scores: { experience: 75.0, skills: 80.0, leadership: 70.0 },
            pros: ['Strong candidate resume matcher', 'Demonstrated expertise in engineering roles', 'Excellent written progression details'],
            cons: ['Deeper specific cloud experience might be helpful', 'Lacks explicit references to team management in core roles', 'Tenure at some past companies is transition-dense'],
            behavioral_indicators: 'Result-oriented developer with solid individual contributor outcomes.'
        };
    }
    
    const system = 'You are an expert executive recruiter. Perform a rigorous, unbiased evaluation of the candidate profile against job requirements.';
    const prompt = `
    Compare this Candidate Profile with the Job Description Requirements, using the slider priorities to guide score calculations:
    
    JOB DESCRIPTION:
    - Title: ${job.title}
    - Requirements: ${JSON.stringify(job.parsed_requirements)}
    
    CANDIDATE PROFILE:
    - Name: ${candidate.name}
    - Skills: ${JSON.stringify(candidate.skills)}
    - Experience Years: ${candidate.experience_years}
    - Resume Content: ${candidate.full_parsed_text}
    
    EVALUATION WEIGHTS (Prioritize accordingly):
    - Experience Weight: ${weights.experience}
    - Skills Match Weight: ${weights.skills}
    - Leadership Weight: ${weights.leadership}
    
    Return a JSON object with this EXACT structure:
    {
        "score": 84.5,
        "sub_scores": {
            "experience": 88.0,
            "skills": 92.0,
            "leadership": 70.0
        },
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
    }
    
    Return ONLY the raw JSON object.
    `;
    
    try {
        const text = await callClaude(prompt, system);
        const jsonStr = cleanJsonResponse(text);
        return JSON.parse(jsonStr);
    } catch (e) {
        console.error('Error ranking candidate with Claude:', e);
        return {
            score: 75.0,
            sub_scores: { experience: 75.0, skills: 80.0, leadership: 70.0 },
            pros: ['Strong candidate resume matcher', 'Demonstrated expertise in engineering roles', 'Excellent written progression details'],
            cons: ['Deeper specific cloud experience might be helpful', 'Lacks explicit references to team management in core roles', 'Tenure at some past companies is transition-dense'],
            behavioral_indicators: 'Result-oriented developer with solid individual contributor outcomes.'
        };
    }
}

async function generateCoachingReport(candidate, job) {
    if (!process.env.ANTHROPIC_API_KEY) {
        return {
            skill_gaps: [
                { name: 'FastAPI', why_it_matters: 'Core web framework used to build our backend services.', severity: 'Advanced needed' },
                { name: 'SQLAlchemy', why_it_matters: 'Primary ORM for executing database queries.', severity: 'Intermediate needed' },
                { name: 'Docker', why_it_matters: 'Containerization tool used to package applications.', severity: 'Intermediate needed' }
            ],
            action_plan: [
                { task: 'Build a scalable REST API with FastAPI, using OAuth2 JWT authentication and custom route dependencies.', time: '~3 days' },
                { task: 'Design a relational database model in SQLAlchemy 2.0 with connection pooling and async queries.', time: '~2 days' },
                { task: 'Containerize a multi-service FastAPI app connected to PostgreSQL using Docker Compose.', time: '~3 days' }
            ],
            study_resources: [
                { name: 'FastAPI Official Interactive Tutorial Guide', url: 'https://fastapi.tiangolo.com/tutorial/', platform: 'Docs', duration: '4 hours', relevance: 'FastAPI' },
                { name: 'SQLAlchemy Unified 2.0 ORM Guide & Docs', url: 'https://docs.sqlalchemy.org/en/20/tutorial/', platform: 'Docs', duration: '6 hours', relevance: 'SQLAlchemy' },
                { name: 'Docker Containerization Academy Masterclass', url: 'https://docs.docker.com/get-started/', platform: 'Docs', duration: '3 hours', relevance: 'Docker' }
            ],
            rejection_feedback: 'Demonstrates strong potential but requires deeper hands-on expertise in backend microservices architectures.'
        };
    }
    
    const system = 'You are a coaching-oriented recruiter. Write highly specific, encouraging, and actionable feedback.';
    const prompt = `
    Provide constructive coaching feedback to help this rejected candidate grow and close their gaps for future applications:
    
    ROLE REQUIREMENTS:
    - Job Title: ${job.title}
    - Requirements: ${JSON.stringify(job.parsed_requirements)}
    
    CANDIDATE PROFILE:
    - Name: ${candidate.name}
    - Skills: ${JSON.stringify(candidate.skills)}
    
    Based on their gaps, generate:
    - "skill_gaps": Array of exactly 3 objects:
      {
        "name": "Skill Name (e.g. FastAPI)",
        "why_it_matters": "1-line explanation of why this skill is needed in this role",
        "severity": "Beginner needed" or "Intermediate needed" or "Advanced needed"
      }
    - "action_plan": Array of exactly 3 objects:
      {
        "task": "A highly specific, concrete project task they can build (e.g., Build a REST API with JWT in FastAPI)",
        "time": "Estimated duration (e.g., ~3 days)"
      }
    - "study_resources": Array of exactly 3 objects:
      {
        "name": "Course/Resource Title",
        "url": "Clickable valid URL (e.g. https://fastapi.tiangolo.com/)",
        "platform": "Docs" or "YouTube" or "Udemy" or "GitHub",
        "duration": "Estimated learning duration (e.g., 4 hours)",
        "relevance": "Matching skill name from skill_gaps list"
      }
    - "rejection_feedback": A compassionate summary paragraph explaining their core strengths and areas of growth.
    
    Return a JSON object with this EXACT structure:
    {
      "skill_gaps": [{"name": "...", "why_it_matters": "...", "severity": "..."}],
      "action_plan": [{"task": "...", "time": "..."}],
      "study_resources": [{"name": "...", "url": "...", "platform": "...", "duration": "...", "relevance": "..."}],
      "rejection_feedback": "..."
    }
    
    Return ONLY the raw JSON object.
    `;
    
    try {
        const text = await callClaude(prompt, system);
        const jsonStr = cleanJsonResponse(text);
        return JSON.parse(jsonStr);
    } catch (e) {
        console.error('Error generating coaching report with Claude:', e);
        return {
            skill_gaps: [
                { name: 'FastAPI', why_it_matters: 'Core web framework used to build our backend services.', severity: 'Advanced needed' },
                { name: 'SQLAlchemy', why_it_matters: 'Primary ORM for executing database queries.', severity: 'Intermediate needed' },
                { name: 'Docker', why_it_matters: 'Containerization tool used to package applications.', severity: 'Intermediate needed' }
            ],
            action_plan: [
                { task: 'Build a scalable REST API with FastAPI, using OAuth2 JWT authentication and custom route dependencies.', time: '~3 days' },
                { task: 'Design a relational database model in SQLAlchemy 2.0 with connection pooling and async queries.', time: '~2 days' },
                { task: 'Containerize a multi-service FastAPI app connected to PostgreSQL using Docker Compose.', time: '~3 days' }
            ],
            study_resources: [
                { name: 'FastAPI Official Interactive Tutorial Guide', url: 'https://fastapi.tiangolo.com/tutorial/', platform: 'Docs', duration: '4 hours', relevance: 'FastAPI' },
                { name: 'SQLAlchemy Unified 2.0 ORM Guide & Docs', url: 'https://docs.sqlalchemy.org/en/20/tutorial/', platform: 'Docs', duration: '6 hours', relevance: 'SQLAlchemy' },
                { name: 'Docker Containerization Academy Masterclass', url: 'https://docs.docker.com/get-started/', platform: 'Docs', duration: '3 hours', relevance: 'Docker' }
            ],
            rejection_feedback: 'Demonstrates strong potential but requires deeper hands-on expertise in backend microservices architectures.'
        };
    }
}

// --- API ROUTES ---

// 1. Auth routes
app.post('/api/auth/register', async (req, res) => {
    const { email, password, role } = req.body;
    if (!email || !password) {
        return res.status(400).json({ detail: 'Email and password are required' });
    }
    
    try {
        const passwordHash = await bcrypt.hash(password, 10);
        const { data, error } = await supabase.from('recruiters').insert({
            email,
            password_hash: passwordHash,
            role: role || 'recruiter'
        }).select();
        
        if (error) {
            if (error.code === '23505') {
                return res.status(400).json({ detail: 'Email already exists' });
            }
            throw error;
        }
        
        const recruiter = data[0];
        const accessToken = jwt.sign({ id: recruiter.id, email: recruiter.email, role: recruiter.role }, JWT_SECRET, { expiresIn: '120m' });
        
        await logAudit(recruiter.id, 'register', { email });
        res.status(201).json({ access_token: accessToken, role: recruiter.role });
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

app.post('/api/auth/login', async (req, res) => {
    const { email, password } = req.body;
    if (!email || !password) {
        return res.status(400).json({ detail: 'Email and password are required' });
    }
    
    try {
        const { data, error } = await supabase.from('recruiters').select().eq('email', email);
        if (error || !data || data.length === 0) {
            return res.status(401).json({ detail: 'Invalid credentials' });
        }
        
        const recruiter = data[0];
        const isMatch = await bcrypt.compare(password, recruiter.password_hash);
        if (!isMatch) {
            return res.status(401).json({ detail: 'Invalid credentials' });
        }
        
        const accessToken = jwt.sign({ id: recruiter.id, email: recruiter.email, role: recruiter.role }, JWT_SECRET, { expiresIn: '120m' });
        
        await logAudit(recruiter.id, 'login', { email });
        res.status(200).json({ access_token: accessToken, role: recruiter.role });
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

// 2. Jobs routes
app.post('/api/jobs', authenticateJWT, async (req, res) => {
    const { title, description } = req.body;
    if (!title || !description) {
        return res.status(400).json({ detail: 'Title and description are required' });
    }
    
    try {
        const parsedReqs = await deconstructJob(description);
        const { data, error } = await supabase.from('jobs').insert({
            title,
            description,
            parsed_requirements: parsedReqs
        }).select();
        
        if (error) throw error;
        
        const job = data[0];
        await logAudit(req.user.id, 'job_created', { id: job.id, title: job.title });
        res.status(201).json(job);
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

app.get('/api/jobs', authenticateJWT, async (req, res) => {
    try {
        const { data, error } = await supabase.from('jobs').select().order('created_at', { ascending: false });
        if (error) throw error;
        res.status(200).json(data);
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

// 3. Candidates routes
app.get('/api/candidates', authenticateJWT, async (req, res) => {
    try {
        const { data, error } = await supabase.from('candidates').select().order('created_at', { ascending: false });
        if (error) throw error;
        res.status(200).json(data);
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

app.post('/api/candidates/upload', authenticateJWT, upload.array('files'), async (req, res) => {
    const files = req.files;
    const jobId = req.headers['x-job-id'] || req.body.job_id;
    if (!files || files.length === 0) {
        return res.status(400).json({ detail: 'No resume files uploaded.' });
    }
    if (!jobId) {
        return res.status(400).json({ detail: 'Missing Job Workspace ID context.' });
    }
    
    const createdCandidates = [];
    try {
        for (const file of files) {
            const rawText = await parseResumeText(file.buffer, file.originalname);
            const profile = await extractCandidateDetails(rawText);
            const token = crypto.randomBytes(24).toString('hex');
            
            const { data, error } = await supabase.from('candidates').insert({
                job_id: jobId,
                name: profile.name || 'Unknown Candidate',
                email: profile.email || 'unknown@candidate.com',
                phone: profile.phone || '',
                skills: profile.skills || [],
                experience_years: parseFloat(profile.experience_years) || 0,
                full_parsed_text: rawText,
                portal_token: token,
                status: 'pending',
                fit_score: 0
            }).select();
            
            if (error) throw error;
            
            createdCandidates.push(data[0]);
            await logAudit(req.user.id, 'candidate_uploaded', { id: data[0].id, name: data[0].name });
        }
        res.status(201).json(createdCandidates);
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: e.message || 'Internal server error' });
    }
});

// 4. Rankings / compute routes
app.post(['/api/rankings/compute/:job_id', '/api/rank'], authenticateJWT, async (req, res) => {
    const jobId = req.params.job_id || req.body.job_id;
    if (!jobId) {
        return res.status(400).json({ detail: 'Missing Job ID parameter' });
    }
    
    const expWeight = parseFloat(req.body.experience_weight || req.query.exp_w || 33);
    const skWeight = parseFloat(req.body.skills_weight || req.query.sk_w || 33);
    const ldWeight = parseFloat(req.body.leadership_weight || req.query.ld_w || 33);
    
    try {
        // Retrieve job
        const { data: jobData, error: jobErr } = await supabase.from('jobs').select().eq('id', jobId);
        if (jobErr || !jobData || jobData.length === 0) {
            return res.status(404).json({ detail: 'Job workspace not found' });
        }
        const job = jobData[0];
        
        // Retrieve candidates for job
        const { data: candidates, error: candErr } = await supabase.from('candidates').select().eq('job_id', jobId);
        if (candErr) throw candErr;
        
        const computedRankings = [];
        for (const candidate of candidates) {
            const weights = { experience: expWeight, skills: skWeight, leadership: ldWeight };
            const evalReport = await rankCandidate(candidate, job, weights);
            
            const score = parseFloat(evalReport.score) || 50;
            const status = score >= 70 ? 'shortlisted' : 'rejected';
            
            // Save results to candidates table
            const { data: updatedCand, error: updateErr } = await supabase.from('candidates').update({
                fit_score: score,
                status: status
            }).eq('id', candidate.id).select();
            
            if (updateErr) throw updateErr;
            
            // If rejected, generate constructive Rejection Feedback report
            if (status === 'rejected') {
                const report = await generateCoachingReport(candidate, job);
                
                // Clear any existing feedback report to prevent duplicate keys
                await supabase.from('feedback_reports').delete().eq('candidate_id', candidate.id);
                
                const { error: fbErr } = await supabase.from('feedback_reports').insert({
                    candidate_id: candidate.id,
                    skill_gaps: report.skill_gaps || [],
                    action_plan: report.action_plan || [],
                    study_resources: report.study_resources || [],
                    rejection_feedback: report.rejection_feedback || ''
                });
                if (fbErr) console.error('Failed to save feedback report:', fbErr);
            }
            
            computedRankings.push({
                id: candidate.id,
                job_id: jobId,
                candidate_id: candidate.id,
                score: score,
                status: status,
                sub_scores: evalReport.sub_scores || {},
                pros: evalReport.pros || [],
                cons: evalReport.cons || [],
                feedback_report: { behavioral_indicators: evalReport.behavioral_indicators }
            });
        }
        
        await logAudit(req.user.id, 'rankings_computed', { job_id: jobId, count: computedRankings.length });
        res.status(200).json(computedRankings);
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: e.message || 'Internal server error' });
    }
});

// GET rankings endpoint for frontend render
app.get('/api/rankings/:job_id', authenticateJWT, async (req, res) => {
    const jobId = req.params.job_id;
    try {
        const { data: candidates, error } = await supabase.from('candidates').select().eq('job_id', jobId).order('fit_score', { ascending: false });
        if (error) throw error;
        
        // Map candidates to look like RankingResponse
        const mappedRankings = candidates.map(c => ({
            id: c.id,
            job_id: jobId,
            candidate_id: c.id,
            score: parseFloat(c.fit_score) || 0,
            status: c.status,
            candidate_name: c.name,
            candidate_email: c.email,
            pros: ['Matches technical benchmarks.'],
            cons: ['Self-assessed coaching active.'],
            feedback_report: { behavioral_indicators: 'Analyzed resume profiles.' }
        }));
        
        res.status(200).json(mappedRankings);
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

// GET single candidate details for drawer
app.get('/api/candidates/:candidate_id', authenticateJWT, async (req, res) => {
    const candidateId = req.params.candidate_id;
    try {
        const { data: c, error } = await supabase.from('candidates').select().eq('id', candidateId).single();
        if (error) return res.status(404).json({ detail: 'Candidate not found' });
        
        // Retrieve feedback report if exists
        const { data: fb } = await supabase.from('feedback_reports').select().eq('candidate_id', candidateId).single();
        
        res.status(200).json({
            id: c.id,
            name: c.name,
            email: c.email,
            phone: c.phone || '',
            skills: c.skills || [],
            experience: [], // Mock array to keep JS drawing functions happy
            education: [],
            full_parsed_text: c.full_parsed_text || '',
            feedback_report: fb ? {
                skill_gaps: fb.skill_gaps,
                improvement_steps: fb.action_plan ? fb.action_plan.map(a => a.task) : [],
                time_to_close: fb.action_plan ? fb.action_plan.map(a => a.time) : [],
                behavioral_indicators: fb.rejection_feedback
            } : null
        });
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

// Update customized feedback report from recruiter dashboard
app.put('/api/rankings/:ranking_id/feedback', authenticateJWT, async (req, res) => {
    const candidateId = req.params.ranking_id; // Frontend binds ranking_id to candidate_id in tables
    const { skill_gaps, improvement_steps, time_to_close } = req.body;
    
    try {
        // Map arrays back to expected objects
        const gapsMapped = (skill_gaps || []).map(g => ({
            name: g,
            why_it_matters: 'Core skill required for alignment.',
            severity: 'Intermediate needed'
        }));
        
        const actionPlanMapped = (improvement_steps || []).map((step, index) => ({
            task: step,
            time: (time_to_close || [])[index] || '~3 days'
        }));
        
        // Check if report exists
        const { data: existing } = await supabase.from('feedback_reports').select().eq('candidate_id', candidateId);
        
        let error;
        if (existing && existing.length > 0) {
            ({ error } = await supabase.from('feedback_reports').update({
                skill_gaps: gapsMapped,
                action_plan: actionPlanMapped
            }).eq('candidate_id', candidateId));
        } else {
            ({ error } = await supabase.from('feedback_reports').insert({
                candidate_id: candidateId,
                skill_gaps: gapsMapped,
                action_plan: actionPlanMapped,
                study_resources: []
            }));
        }
        
        if (error) throw error;
        
        await logAudit(req.user.id, 'feedback_report_edited', { candidate_id: candidateId });
        res.status(200).json({ id: candidateId, status: 'success' });
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: e.message || 'Internal server error' });
    }
});

// 5. Public Candidate Portal Endpoint
app.get('/api/portal/:token', async (req, res) => {
    const token = req.params.token;
    if (!token) {
        return res.status(400).json({ detail: 'Missing portal token' });
    }
    
    try {
        // Fetch candidate
        const { data: cData, error: cErr } = await supabase.from('candidates').select().eq('portal_token', token);
        if (cErr || !cData || cData.length === 0) {
            return res.status(404).json({ detail: 'This link is invalid or has expired' });
        }
        const candidate = cData[0];
        
        // Fetch job
        const { data: jobData, error: jobErr } = await supabase.from('jobs').select().eq('id', candidate.job_id);
        if (jobErr || !jobData || jobData.length === 0) {
            return res.status(404).json({ detail: 'Job workspace not found' });
        }
        const job = jobData[0];
        
        // Fetch feedback report
        const { data: fbData } = await supabase.from('feedback_reports').select().eq('candidate_id', candidate.id);
        const fb = fbData && fbData.length > 0 ? fbData[0] : null;
        
        res.status(200).json({
            name: candidate.name,
            email: candidate.email,
            role_applied: job.title,
            fit_score: parseFloat(candidate.fit_score) || 0,
            skill_gaps: fb ? fb.skill_gaps || [] : [],
            action_plan: fb ? fb.action_plan || [] : [],
            study_resources: fb ? fb.study_resources || [] : [],
            rejection_feedback: fb ? fb.rejection_feedback : 'Demonstrates strong technical credentials and great engineering promise.',
            company_name: 'AI Recruiter Workspace Hub',
            status: candidate.status,
            date_applied: new Date(candidate.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
        });
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

// 6. Admin Audit route
app.get('/api/audit', authenticateJWT, requireAdmin, async (req, res) => {
    try {
        const { data, error } = await supabase.from('audit_logs').select().order('timestamp', { ascending: false });
        if (error) throw error;
        
        // Map fields to match Python AuditLogResponse
        const mappedLogs = data.map(l => ({
            id: l.id,
            action: l.action,
            target_id: l.details ? String(l.details.id || '') : '',
            details: l.details || {},
            timestamp: l.timestamp,
            user_id: l.recruiter_id ? 1 : null // Mock integer mapping to fit frontend grid
        }));
        
        res.status(200).json(mappedLogs);
    } catch (e) {
        console.error(e);
        res.status(500).json({ detail: 'Internal server error' });
    }
});

// Fallback Automation modes to keep client dashboard settings functional
app.get('/api/automation/settings', (req, res) => {
    res.json({ autonomous_mode: false });
});
app.post('/api/automation/toggle', (req, res) => {
    res.json({ autonomous_mode: req.body.autonomous_mode || false });
});
app.get('/api/automation/outbox', (req, res) => {
    res.json([]);
});

// Default base routing fallback
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'static', 'index.html'));
});

// Start Server
app.listen(PORT, () => {
    console.log(`AI Recruiter Node.js backend is running at http://localhost:${PORT}`);
});
