// AI Recruiter - Main Application Logic

const API_BASE = window.location.origin;

// Global fetch interceptor to handle session expiration (401 Unauthorized)
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const response = await originalFetch(...args);
    if (response.status === 401) {
        try {
            const clone = response.clone();
            const data = await clone.json();
            if (data.detail === "Could not validate credentials" || data.detail === "Not authenticated") {
                if (localStorage.getItem("token")) {
                    handleLogout();
                    showToast("Session expired. Please sign in again.", "danger");
                }
            }
        } catch (e) {
            // Safe fallback
        }
    }
    return response;
};

// State Management
let token = localStorage.getItem("token") || "";
let userRole = localStorage.getItem("userRole") || "";
let userEmail = localStorage.getItem("userEmail") || "";
let jobs = [];
let activeJobId = "";
let rankings = [];
let allCandidatesCount = 0;
let isRegisterMode = false;
let activeRankingId = null;

// AI Screening Hub State
let activeTab = "pipeline";
let interviews = [];
let interviewsInterval = null;

// Initializer
document.addEventListener("DOMContentLoaded", () => {
    checkAuth();
});

// Unified Recruiter/Candidate Login Portal Switches
let activeAuthPortal = "recruiter";

function switchAuthTab(portal) {
    if (activeAuthPortal === portal) return;
    activeAuthPortal = portal;
    
    const tabRecruiter = document.getElementById("auth-tab-recruiter");
    const tabCandidate = document.getElementById("auth-tab-candidate");
    
    const formRecruiter = document.getElementById("auth-form");
    const formCandidate = document.getElementById("candidate-auth-form");
    
    const subtitle = document.getElementById("auth-card-subtitle");
    
    if (portal === "recruiter") {
        tabRecruiter.classList.add("active");
        tabRecruiter.style.background = "linear-gradient(135deg, rgba(121, 40, 202, 0.25), rgba(0, 112, 243, 0.25))";
        tabRecruiter.style.borderColor = "rgba(255, 255, 255, 0.08)";
        tabRecruiter.style.color = "#ffffff";
        
        tabCandidate.classList.remove("active");
        tabCandidate.style.background = "transparent";
        tabCandidate.style.borderColor = "transparent";
        tabCandidate.style.color = "#9ca3af";
        
        formRecruiter.style.display = "block";
        formCandidate.style.display = "none";
        
        subtitle.innerText = "Verify credentials to enter the recruiter workspace";
    } else {
        tabCandidate.classList.add("active");
        tabCandidate.style.background = "linear-gradient(135deg, rgba(0, 112, 243, 0.25), rgba(0, 223, 216, 0.25))";
        tabCandidate.style.borderColor = "rgba(255, 255, 255, 0.08)";
        tabCandidate.style.color = "#ffffff";
        
        tabRecruiter.classList.remove("active");
        tabRecruiter.style.background = "transparent";
        tabRecruiter.style.borderColor = "transparent";
        tabRecruiter.style.color = "#9ca3af";
        
        formCandidate.style.display = "block";
        formRecruiter.style.display = "none";
        
        subtitle.innerText = "Access your Conversational AI Screening Round";
    }
}

function handleCandidateAccessSubmit(event) {
    event.preventDefault();
    const candId = document.getElementById("candidate-access-id").value.trim();
    if (!candId) {
        showToast("Please enter a valid Candidate ID to continue.", "danger");
        return;
    }
    // Launch screening portal directly
    showToast("Launching video proctored screening room...", "success");
    setTimeout(() => {
        window.location.href = `/static/screening.html?cand_id=${candId}&job_id=1`;
    }, 800);
}

// Toast Notifications
function showToast(message, type = "success") {
    const grid = document.getElementById("toast-grid");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    grid.appendChild(toast);
    
    // Auto-remove toast after 4s
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function showCountdownToast(baseMessage, durationSeconds) {
    const grid = document.getElementById("toast-grid");
    const toast = document.createElement("div");
    toast.className = "toast info";
    grid.appendChild(toast);
    
    let remaining = durationSeconds;
    let intervalId = null;
    
    const updateToast = () => {
        if (remaining <= 0) {
            clearInterval(intervalId);
            toast.innerText = `${baseMessage} completed!`;
            setTimeout(() => {
                toast.style.opacity = "0";
                setTimeout(() => toast.remove(), 300);
            }, 1000);
        } else {
            toast.innerText = `${baseMessage} (~${remaining}s remaining)`;
            remaining--;
        }
    };
    
    updateToast();
    intervalId = setInterval(updateToast, 1000);
    
    return {
        dismiss: (successMessage) => {
            clearInterval(intervalId);
            toast.innerText = successMessage || `${baseMessage} completed!`;
            toast.className = "toast success";
            setTimeout(() => {
                toast.style.opacity = "0";
                setTimeout(() => toast.remove(), 300);
            }, 1500);
        },
        fail: (errorMessage) => {
            clearInterval(intervalId);
            toast.innerText = errorMessage || `${baseMessage} failed.`;
            toast.className = "toast danger";
            setTimeout(() => {
                toast.style.opacity = "0";
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    };
}


// Authentication handlers
function checkAuth() {
    const authContainer = document.getElementById("auth-container");
    const appContainer = document.getElementById("app-container");
    
    if (token) {
        authContainer.style.display = "none";
        appContainer.classList.add("active");
        
        // Update user panel
        document.getElementById("user-display-email").innerText = userEmail;
        document.getElementById("user-display-role").innerText = userRole.toUpperCase();
        
        // Show administrative buttons
        const auditBtn = document.getElementById("btn-view-audit");
        if (userRole === "admin" && auditBtn) {
            auditBtn.style.display = "inline-block";
        }
        
        // Load initial data
        loadJobs();
        loadCandidatesCount();
        loadAutomationSettings();
        checkSMTPSettings();
        // Periodically refresh the outbox timeline feed every 3 seconds for active countdowns
        setInterval(loadOutboxFeed, 3000);
    } else {
        authContainer.style.display = "flex";
        appContainer.classList.remove("active");
    }
}

function toggleAuthMode(event) {
    if (event) event.preventDefault();
    isRegisterMode = !isRegisterMode;
    
    const title = document.querySelector(".auth-card h2");
    const link = document.getElementById("auth-toggle-link");
    const btn = document.getElementById("btn-auth-submit");
    const roleGroup = document.getElementById("role-select-group");
    
    if (isRegisterMode) {
        title.innerText = "Register Recruiter";
        link.innerText = "Back to Sign In";
        btn.innerText = "Register Account";
        roleGroup.style.display = "block";
    } else {
        title.innerText = "AI Recruiter";
        link.innerText = "Create Recruiter Account";
        btn.innerText = "Sign In";
        roleGroup.style.display = "none";
    }
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    const email = document.getElementById("auth-email").value;
    const password = document.getElementById("auth-password").value;
    const role = document.getElementById("auth-role").value;
    
    const endpoint = isRegisterMode ? "/api/auth/register" : "/api/auth/login";
    const payload = isRegisterMode ? { email, password, role } : { email, password };
    
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || "Authentication failed");
        }
        
        const data = await response.json();
        token = data.access_token;
        userRole = data.role;
        userEmail = email;
        
        localStorage.setItem("token", token);
        localStorage.setItem("userRole", userRole);
        localStorage.setItem("userEmail", userEmail);
        
        showToast(isRegisterMode ? "Registration Successful" : "Welcome back!");
        checkAuth();
    } catch (error) {
        showToast(error.message, "danger");
    }
}

function handleLogout() {
    token = "";
    userRole = "";
    userEmail = "";
    localStorage.clear();
    
    if (interviewsInterval) {
        clearInterval(interviewsInterval);
        interviewsInterval = null;
    }
    document.getElementById("workspace-tabs").style.display = "none";
    document.getElementById("screening-hub-container").style.display = "none";
    
    // Clear dropdown
    const dropdown = document.getElementById("job-dropdown");
    dropdown.innerHTML = '<option value="" disabled selected>Select Active Job Description...</option>';
    
    // Hide panels
    document.getElementById("jd-details-container").style.display = "none";
    document.getElementById("rankings-container").style.display = "none";
    document.getElementById("btn-delete-job").style.display = "none";
    document.getElementById("btn-link-candidate-pool").style.display = "none";
    const toggleContainer = document.getElementById("linked-only-toggle-container");
    if (toggleContainer) toggleContainer.style.display = "none";
    const chkLinkedOnly = document.getElementById("chk-linked-only");
    if (chkLinkedOnly) chkLinkedOnly.checked = false;
    
    // Reset inputs
    document.getElementById("auth-email").value = "";
    document.getElementById("auth-password").value = "";

    const quickViewSelect = document.getElementById("quick-view-latest");
    if (quickViewSelect) {
        quickViewSelect.style.display = "none";
        quickViewSelect.value = "";
    }
    
    showToast("Successfully signed out");
    checkAuth();
}

// Ingest candidate count metric
async function loadCandidatesCount() {
    try {
        const res = await fetch(`${API_BASE}/api/candidates`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            allCandidatesCount = data.length;
        }
    } catch (e) {
        console.error(e);
    }
}

// Jobs logic
async function loadJobs() {
    try {
        const res = await fetch(`${API_BASE}/api/jobs`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Could not fetch jobs: ${res.status} ${res.statusText}`);
        }
        
        jobs = await res.json();
        
        const dropdown = document.getElementById("job-dropdown");
        dropdown.innerHTML = '<option value="" disabled selected>Select Active Job Description...</option>';
        
        jobs.forEach(job => {
            const option = document.createElement("option");
            option.value = job.id;
            option.innerText = job.title;
            dropdown.appendChild(option);
        });
        
        // Re-select active job if exists
        if (activeJobId && jobs.some(j => j.id == activeJobId)) {
            dropdown.value = activeJobId;
            handleJobChange();
        }
    } catch (e) {
        showToast(e.message, "danger");
    }
}

function openAddJobModal() {
    document.getElementById("add-job-modal-overlay").classList.add("active");
}

function closeAddJobModal() {
    document.getElementById("add-job-modal-overlay").classList.remove("active");
    document.getElementById("job-title-input").value = "";
    document.getElementById("job-desc-input").value = "";
}

async function handleCreateJobSubmit(event) {
    event.preventDefault();
    const title = document.getElementById("job-title-input").value;
    const description = document.getElementById("job-desc-input").value;
    
    try {
        const res = await fetch(`${API_BASE}/api/jobs`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ title, description })
        });
        
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Error creating job workspace: ${res.status} ${res.statusText}`);
        }
        
        const newJob = await res.json();
        activeJobId = newJob.id;
        
        closeAddJobModal();
        showToast(`Workspace '${newJob.title}' successfully initialized`);
        
        await loadJobs();
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// Trigger upload files click
function triggerFileInput() {
    if (!activeJobId) {
        showToast("Please select or create a Job Workspace first!", "danger");
        return;
    }
    document.getElementById("resume-file-input").click();
}

async function handleResumeUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const formData = new FormData();
    formData.append("job_id", activeJobId);
    for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
    }
    
    const estimatedSeconds = Math.max(15, files.length * 3);
    const toast = showCountdownToast("Uploading and parsing resumes...", estimatedSeconds);
    
    try {
        const res = await fetch(`${API_BASE}/api/candidates/upload`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "X-Job-Id": activeJobId
            },
            body: formData
        });
        
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Error uploading profiles");
        }
        
        const candidates = await res.json();
        toast.dismiss(`Successfully indexed ${candidates.length} candidates!`);
        
        loadCandidatesCount();
        
        // Auto trigger ranking compute once candidates are uploaded to save clicks
        triggerRankingCompute(candidates.length);
    } catch (e) {
        toast.fail(e.message);
    } finally {
        event.target.value = ""; // Clear file selector
    }
}

// Active job workspace selection change
async function handleJobChange() {
    const dropdown = document.getElementById("job-dropdown");
    activeJobId = dropdown.value;
    if (!activeJobId) return;
    
    const job = jobs.find(j => j.id == activeJobId);
    if (!job) return;
    
    // Update headers
    document.getElementById("display-job-title").innerText = job.title;
    document.getElementById("display-job-summary").innerText = job.description.substring(0, 180) + "...";
    
    // Show AI buttons
    document.getElementById("btn-compute-rank").style.display = "inline-block";
    document.getElementById("btn-delete-job").style.display = "inline-block";
    document.getElementById("btn-link-candidate-pool").style.display = "inline-block";
    const toggleContainer = document.getElementById("linked-only-toggle-container");
    if (toggleContainer) toggleContainer.style.display = "flex";
    
    // Build AI intent container
    const detailsContainer = document.getElementById("jd-details-container");
    const experienceText = document.getElementById("jd-details-experience");
    const mustSkillsContainer = document.getElementById("jd-details-must-skills");
    const niceSkillsContainer = document.getElementById("jd-details-nice-skills");
    
    const reqs = job.parsed_requirements || {};
    experienceText.innerText = `Desired: ${reqs.experience_level || "No criteria specified"}`;
    
    mustSkillsContainer.innerHTML = "";
    const musts = reqs.must_have_skills || [];
    if (musts.length > 0) {
        musts.forEach(s => {
            const badge = document.createElement("span");
            badge.className = "skill-tag must";
            badge.innerText = s;
            mustSkillsContainer.appendChild(badge);
        });
    } else {
        mustSkillsContainer.innerHTML = '<span class="skill-tag" style="color: var(--text-muted);">None specified</span>';
    }
    
    niceSkillsContainer.innerHTML = "";
    const nices = reqs.nice_to_have_skills || [];
    if (nices.length > 0) {
        nices.forEach(s => {
            const badge = document.createElement("span");
            badge.className = "skill-tag nice";
            badge.innerText = s;
            niceSkillsContainer.appendChild(badge);
        });
    } else {
        niceSkillsContainer.innerHTML = '<span class="skill-tag" style="color: var(--text-muted);">None specified</span>';
    }
    
    detailsContainer.style.display = "block";
    
    // Show tabs bar
    document.getElementById("workspace-tabs").style.display = "flex";
    
    // Set default tab on job change to pipeline
    switchWorkspaceTab("pipeline");
    
    // Clear and schedule screening live interviews poll
    if (interviewsInterval) clearInterval(interviewsInterval);
    loadInterviews();
    interviewsInterval = setInterval(loadInterviews, 3000);
    
    // Load existing rankings
    loadRankings();
}

// Delete job workspace
async function handleDeleteJob() {
    if (!activeJobId) return;
    const job = jobs.find(j => j.id == activeJobId);
    if (!job) return;
    
    const confirmDelete = confirm(`Are you sure you want to delete the workspace '${job.title}'? This will permanently delete all candidate rankings associated with this job.`);
    if (!confirmDelete) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/jobs/${activeJobId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Error deleting workspace: ${res.status} ${res.statusText}`);
        }
        
        showToast(`Workspace '${job.title}' deleted successfully.`);
        
        // Clear active workspace
        activeJobId = "";
        document.getElementById("btn-delete-job").style.display = "none";
        document.getElementById("jd-details-container").style.display = "none";
        document.getElementById("rankings-container").style.display = "none";
        document.getElementById("workspace-tabs").style.display = "none";
        document.getElementById("screening-hub-container").style.display = "none";
        const toggleContainer = document.getElementById("linked-only-toggle-container");
        if (toggleContainer) toggleContainer.style.display = "none";
        const chkLinkedOnly = document.getElementById("chk-linked-only");
        if (chkLinkedOnly) chkLinkedOnly.checked = false;

        const quickViewSelect = document.getElementById("quick-view-latest");
        if (quickViewSelect) {
            quickViewSelect.style.display = "none";
            quickViewSelect.value = "";
        }
        
        // Reset metrics cards
        document.getElementById("metric-total-candidates").innerText = "0";
        document.getElementById("metric-shortlisted").innerText = "0";
        document.getElementById("metric-rejected").innerText = "0";
        document.getElementById("metric-avg-score").innerText = "0%";
        
        // Reset headers
        document.getElementById("display-job-title").innerText = "Recruiter Workspace";
        document.getElementById("display-job-summary").innerText = "Please select or create a Job Workspace from the left to start ranking candidates.";
        document.getElementById("btn-compute-rank").style.display = "none";
        
        // Reload workspaces list
        await loadJobs();
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// Compute ratings
async function triggerRankingCompute(count) {
    if (!activeJobId) return;
    
    const chkLinkedOnly = document.getElementById("chk-linked-only");
    const linkedOnly = chkLinkedOnly ? chkLinkedOnly.checked : false;
    
    let candidateCount = count;
    if (!candidateCount) {
        if (linkedOnly) {
            candidateCount = rankings.length || 1;
        } else {
            candidateCount = Math.max(50, rankings.length || 50);
        }
    }
    
    const estimatedSeconds = Math.ceil(candidateCount * 1.5);
    const toast = showCountdownToast(`AI analyzing and ranking candidates`, estimatedSeconds);
    
    try {
        const res = await fetch(`${API_BASE}/api/rankings/compute/${activeJobId}?linked_only=${linkedOnly}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                experience_weight: document.getElementById("slider-exp").value,
                skills_weight: document.getElementById("slider-skills").value,
                leadership_weight: document.getElementById("slider-leadership").value
            })
        });
        
        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.detail || "Error calculating candidate alignments");
        }
        
        toast.dismiss("Shortlist calculated successfully!");
        loadRankings();
    } catch (e) {
        toast.fail(e.message);
    }
}

// Load rankings, applies dynamic slider values
async function loadRankings() {
    if (!activeJobId) return;
    
    const exp_w = document.getElementById("slider-exp").value / 100.0;
    const skills_w = document.getElementById("slider-skills").value / 100.0;
    const leadership_w = document.getElementById("slider-leadership").value / 100.0;
    
    try {
        const res = await fetch(
            `${API_BASE}/api/rankings/${activeJobId}?experience_weight=${exp_w}&skills_weight=${skills_w}&leadership_weight=${leadership_w}`,
            { headers: { "Authorization": `Bearer ${token}` } }
        );
        
        if (!res.ok) throw new Error("Error loading rankings");
        
        rankings = await res.json();
        renderRankingsTable();
        updateOverviewMetrics();
        loadOutboxFeed();
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// Dynamic Sorting complete client-side instantly!
function handleSliderChange() {
    const exp_val = document.getElementById("slider-exp").value;
    const skills_val = document.getElementById("slider-skills").value;
    const leadership_val = document.getElementById("slider-leadership").value;
    
    document.getElementById("slider-exp-val").innerText = `${exp_val}%`;
    document.getElementById("slider-skills-val").innerText = `${skills_val}%`;
    document.getElementById("slider-leadership-val").innerText = `${leadership_val}%`;
    
    // Perform dynamic calculations instantly on loaded state!
    const exp_w = parseFloat(exp_val);
    const sk_w = parseFloat(skills_val);
    const ld_w = parseFloat(leadership_val);
    const total = exp_w + sk_w + ld_w;
    
    if (total === 0) return;
    
    rankings.forEach(r => {
        const sub = r.sub_scores || { experience: r.score, skills: r.score, leadership: r.score };
        const score = (exp_w * sub.experience + sk_w * sub.skills + ld_w * sub.leadership) / total;
        r.score = Math.round(score * 10) / 10;
    });
    
    // Re-sort descending
    rankings.sort((a, b) => b.score - a.score);
    renderRankingsTable();
}

// Render Rankings Table Grid
function renderRankingsTable() {
    const tbody = document.getElementById("rankings-tbody");
    const container = document.getElementById("rankings-container");
    
    tbody.innerHTML = "";
    
    if (rankings.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 32px;">
                    No candidates ranked yet. Please upload resumes and click 'AI Rank Matches' above.
                </td>
            </tr>
        `;
        container.style.display = "block";
        return;
    }
    
    rankings.forEach((r, idx) => {
        const candidate = r.candidate || {};
        const tr = document.createElement("tr");
        
        // Determine Score badge class
        let badgeClass = "average";
        if (r.score >= 80) badgeClass = "excellent";
        else if (r.score >= 60) badgeClass = "good";
        
        // Build primary top skills tags
        const maxSkills = 3;
        const skillsList = candidate.skills || [];
        const skillsStr = skillsList.slice(0, maxSkills).join(", ") + (skillsList.length > maxSkills ? "..." : "");
        
        // Build status indicator
        let statusClass = "pending";
        if (r.status === "shortlisted") statusClass = "shortlisted";
        if (r.status === "rejected") statusClass = "rejected";
        
        tr.innerHTML = `
            <td>
                <span class="score-badge ${badgeClass}">${r.score}%</span>
            </td>
            <td>
                <div class="candidate-name-cell">
                    <strong style="cursor: pointer; color: var(--accent-primary-hover);" onclick="showCandidateDetails(${r.id})">${candidate.name}</strong>
                    <span class="cand-title">${skillsStr || "No skills extracted"}</span>
                </div>
            </td>
            <td>
                <span class="status-indicator ${statusClass}">${r.status}</span>
            </td>
            <td>
                <span style="font-size: 0.8rem; color: var(--text-muted);">
                    ${r.feedback_sent ? '<i class="fa-solid fa-square-check" style="color: var(--accent-success); margin-right: 4px;"></i> Sent' : 'Pending Action'}
                </span>
            </td>
            <td>
                <div class="table-actions">
                    <button class="btn-small success" onclick="updateCandidateStatus(${r.id}, 'shortlisted')">Shortlist</button>
                    <button class="btn-small danger" onclick="updateCandidateStatus(${r.id}, 'rejected')">Reject</button>
                    <button class="btn-small" onclick="showCandidateDetails(${r.id})">Evaluate</button>
                </div>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
    
    container.style.display = "block";
    filterCandidates();
}

// Update overview metrics
function updateOverviewMetrics() {
    const total = rankings.length;
    const shortlisted = rankings.filter(r => r.status === "shortlisted").length;
    const rejected = rankings.filter(r => r.status === "rejected").length;
    
    // Top 5 Average fit score
    const top5 = rankings.slice(0, 5);
    const avgScore = top5.length > 0 
        ? Math.round(top5.reduce((sum, r) => sum + r.score, 0) / top5.length) 
        : 0;
        
    document.getElementById("metric-total-candidates").innerText = total;
    document.getElementById("metric-shortlisted").innerText = shortlisted;
    document.getElementById("metric-rejected").innerText = rejected;
    document.getElementById("metric-avg-score").innerText = `${avgScore}%`;

    // Latest Shortlisted Candidates (up to 10)
    const shortlistedRankings = rankings.filter(r => r.status === "shortlisted");
    const grpLatestShortlisted = document.getElementById("grp-latest-shortlisted");
    
    if (grpLatestShortlisted) {
        grpLatestShortlisted.innerHTML = "";
        if (shortlistedRankings.length > 0) {
            shortlistedRankings.sort((a, b) => {
                const dateA = a.updated_at ? new Date(a.updated_at) : 0;
                const dateB = b.updated_at ? new Date(b.updated_at) : 0;
                if (dateB - dateA !== 0) {
                    return dateB - dateA;
                }
                return b.id - a.id;
            });
            const limit = Math.min(10, shortlistedRankings.length);
            for (let i = 0; i < limit; i++) {
                const r = shortlistedRankings[i];
                const name = r.candidate ? r.candidate.name : `Candidate #${r.candidate_id}`;
                const option = document.createElement("option");
                option.value = r.id;
                option.innerText = name;
                grpLatestShortlisted.appendChild(option);
            }
        } else {
            const option = document.createElement("option");
            option.value = "";
            option.innerText = "None";
            option.disabled = true;
            grpLatestShortlisted.appendChild(option);
        }
    }

    // Latest Rejected Candidates (up to 10)
    const rejectedRankings = rankings.filter(r => r.status === "rejected");
    const grpLatestRejected = document.getElementById("grp-latest-rejected");
    
    if (grpLatestRejected) {
        grpLatestRejected.innerHTML = "";
        if (rejectedRankings.length > 0) {
            rejectedRankings.sort((a, b) => {
                const dateA = a.updated_at ? new Date(a.updated_at) : 0;
                const dateB = b.updated_at ? new Date(b.updated_at) : 0;
                if (dateB - dateA !== 0) {
                    return dateB - dateA;
                }
                return b.id - a.id;
            });
            const limit = Math.min(10, rejectedRankings.length);
            for (let i = 0; i < limit; i++) {
                const r = rejectedRankings[i];
                const name = r.candidate ? r.candidate.name : `Candidate #${r.candidate_id}`;
                const option = document.createElement("option");
                option.value = r.id;
                option.innerText = name;
                grpLatestRejected.appendChild(option);
            }
        } else {
            const option = document.createElement("option");
            option.value = "";
            option.innerText = "None";
            option.disabled = true;
            grpLatestRejected.appendChild(option);
        }
    }

    // Show/hide the dropdown itself based on rankings
    const quickViewSelect = document.getElementById("quick-view-latest");
    if (quickViewSelect) {
        if (rankings.length > 0) {
            quickViewSelect.style.display = "inline-block";
        } else {
            quickViewSelect.style.display = "none";
        }
    }
}

function handleQuickViewLatestChange() {
    const select = document.getElementById("quick-view-latest");
    const val = select.value;
    if (!val) return;
    
    showCandidateDetails(parseInt(val));
    
    // Reset selection to default placeholder
    select.value = "";
}

// Candidate drawer details showing timeline, feedback, etc.
async function showCandidateDetails(rankingId) {
    activeRankingId = rankingId;
    
    // Find matching ranking locally and sync its properties
    const ranking = rankings.find(r => r.id === rankingId);
    if (!ranking) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/candidates/${ranking.candidate_id}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) throw new Error("Error loading candidate profile details");
        
        const detail = await res.json();
        
        // Sync backend changes to local ranking item
        ranking.candidate = {
            name: detail.name,
            email: detail.email,
            phone: detail.phone,
            skills: detail.skills,
            experience: detail.experience
        };
        ranking.feedback_report = detail.feedback_report || {};
        
        // Set text contents
        document.getElementById("drawer-cand-name").innerText = detail.name;
        document.getElementById("drawer-cand-email").innerText = detail.email || "No email extracted";
        
        const fb = detail.feedback_report || {};
        document.getElementById("drawer-ai-behavioral").innerText = fb.behavioral_indicators || "Demonstrates strong background alignment with core technology specifications.";
        
        // Build Pros list
        const prosContainer = document.getElementById("drawer-pros-list");
        prosContainer.innerHTML = "";
        const pros = ranking.pros || [];
        if (pros.length > 0) {
            pros.forEach(p => {
                const li = document.createElement("li");
                li.innerText = p;
                prosContainer.appendChild(li);
            });
        } else {
            prosContainer.innerHTML = '<li style="color: var(--text-muted);">No specific strengths parsed.</li>';
        }
        
        // Build Cons list
        const consContainer = document.getElementById("drawer-cons-list");
        consContainer.innerHTML = "";
        const cons = ranking.cons || [];
        if (cons.length > 0) {
            cons.forEach(c => {
                const li = document.createElement("li");
                li.innerText = c;
                consContainer.appendChild(li);
            });
        } else {
            consContainer.innerHTML = '<li style="color: var(--text-muted);">No specific gaps identified.</li>';
        }
        
        // Build Skills Heatmap comparing Candidate vs Job Description
        const heatmap = document.getElementById("drawer-skills-heatmap");
        heatmap.innerHTML = "";
        
        const activeJob = jobs.find(j => j.id == activeJobId);
        if (activeJob) {
            const jdReqs = activeJob.parsed_requirements || {};
            const mustSkills = jdReqs.must_have_skills || [];
            const niceSkills = jdReqs.nice_to_have_skills || [];
            const candSkills = (detail.skills || []).map(s => String(s).toLowerCase().trim());
            
            // Merge Jd skills
            const allJdSkills = [...new Set([...mustSkills, ...niceSkills])];
            if (allJdSkills.length > 0) {
                allJdSkills.forEach(skill => {
                    const cell = document.createElement("div");
                    const hasMatch = candSkills.some(cs => cs.includes(skill.toLowerCase()) || skill.toLowerCase().includes(cs));
                    cell.className = `heatmap-cell ${hasMatch ? 'match' : 'gap'}`;
                    cell.innerHTML = `
                        <i class="fa-solid ${hasMatch ? 'fa-circle-check' : 'fa-circle-xmark'}" style="margin-right: 6px;"></i>
                        ${skill}
                    `;
                    heatmap.appendChild(cell);
                });
            } else {
                heatmap.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">No JD skills extracted to compare.</p>';
            }
        }
        
        // Build Career progression timeline
        const timeline = document.getElementById("drawer-career-timeline");
        timeline.innerHTML = "";
        const experiences = detail.experience || [];
        
        if (experiences.length > 0) {
            experiences.forEach(exp => {
                const item = document.createElement("div");
                item.className = "timeline-item";
                
                // Format dates
                const start = exp.start_date || "N/A";
                const end = exp.end_date || "Present";
                
                item.innerHTML = `
                    <span class="timeline-dot"></span>
                    <span class="timeline-date">${start} — ${end}</span>
                    <h5 class="timeline-company">${exp.title}</h5>
                    <p style="font-size: 0.8rem; font-weight: 600; color: var(--accent-primary-hover); margin-top: 2px;">${exp.company}</p>
                    <p class="timeline-desc">${exp.description || ""}</p>
                `;
                timeline.appendChild(item);
            });
        } else {
            timeline.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">No career history extracted.</p>';
        }
        
        // Toggle rejection feedback editor
        const feedbackEditor = document.getElementById("feedback-editor-section");
        const saveBtn = document.getElementById("btn-save-feedback");
        const sendBtn = document.getElementById("btn-send-feedback");
        
        if (ranking.status === "rejected") {
            feedbackEditor.style.display = "flex";
            saveBtn.style.display = "block";
            sendBtn.style.display = "block";
            
            // Populate textarea fields
            document.getElementById("editor-gaps").value = (fb.skill_gaps || []).map(g => g.name || g).join("\n");
            document.getElementById("editor-steps").value = (fb.improvement_steps || []).join("\n");
            document.getElementById("editor-timeframes").value = (fb.time_to_close || []).join("\n");
        } else {
            feedbackEditor.style.display = "none";
            saveBtn.style.display = "none";
            sendBtn.style.display = "none";
        }
        
        // Slide in
        document.getElementById("drawer-overlay").classList.add("active");
        document.getElementById("candidate-drawer").classList.add("active");
    } catch (e) {
        showToast(e.message, "danger");
    }
}

function closeDrawer() {
    document.getElementById("drawer-overlay").classList.remove("active");
    document.getElementById("candidate-drawer").classList.remove("active");
    activeRankingId = null;
}

// Update candidate shortlist / reject status
async function updateCandidateStatus(rankingId, newStatus) {
    try {
        const res = await fetch(`${API_BASE}/api/rankings/${rankingId}/status`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (!res.ok) throw new Error("Error updating candidate workflow state");
        
        const updated = await res.json();
        showToast(`Candidate status updated to '${newStatus}'`);
        
        // Sync state locally
        const index = rankings.findIndex(r => r.id === rankingId);
        if (index !== -1) {
            rankings[index].status = updated.status;
            rankings[index].feedback_report = updated.feedback_report;
        }
        
        renderRankingsTable();
        updateOverviewMetrics();
        
        // If drawer is currently active on this candidate, refresh it
        if (activeRankingId === rankingId) {
            showCandidateDetails(rankingId);
        }
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// Save customized rejection feedback report
async function saveCustomizedFeedback() {
    if (!activeRankingId) return;
    
    const gaps = document.getElementById("editor-gaps").value.split("\n").filter(l => l.trim() !== "");
    const steps = document.getElementById("editor-steps").value.split("\n").filter(l => l.trim() !== "");
    const timeframes = document.getElementById("editor-timeframes").value.split("\n").filter(l => l.trim() !== "");
    
    try {
        const res = await fetch(`${API_BASE}/api/rankings/${activeRankingId}/feedback`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                skill_gaps: gaps,
                improvement_steps: steps,
                time_to_close: timeframes
            })
        });
        
        if (!res.ok) throw new Error("Error saving rejection report changes");
        
        const updated = await res.json();
        showToast("Rejection feedback report updated successfully");
        
        // Sync local rankings state
        const index = rankings.findIndex(r => r.id === activeRankingId);
        if (index !== -1) {
            rankings[index].feedback_report = updated.feedback_report;
        }
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// Send (mark as dispatched) the feedback
async function sendCustomizedFeedback() {
    if (!activeRankingId) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/rankings/${activeRankingId}/feedback/send`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        
        if (!res.ok) throw new Error("Error marking feedback as dispatched");
        
        showToast("Feedback report successfully sent to candidate's portal!");
        
        // Sync local rankings state
        const index = rankings.findIndex(r => r.id === activeRankingId);
        if (index !== -1) {
            rankings[index].feedback_sent = true;
        }
        
        renderRankingsTable();
        closeDrawer();
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// Administrative Auditing portal
async function openAuditModal() {
    if (userRole !== "admin") return;
    
    try {
        const res = await fetch(`${API_BASE}/api/audit`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) throw new Error("Access denied. Admin access only.");
        
        const logs = await res.json();
        const tbody = document.getElementById("audit-logs-tbody");
        tbody.innerHTML = "";
        
        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No compliance logs recorded.</td></tr>';
        } else {
            logs.forEach(log => {
                const tr = document.createElement("tr");
                const time = new Date(log.timestamp).toLocaleString();
                
                tr.innerHTML = `
                    <td style="font-weight: 600; color: var(--accent-primary-hover);">${log.action}</td>
                    <td>${log.target_id || 'System'}</td>
                    <td>${time}</td>
                    <td>${log.user_id ? `User #${log.user_id}` : 'Anonymous'}</td>
                `;
                tbody.appendChild(tr);
            });
        }
        
        document.getElementById("audit-modal-overlay").classList.add("active");
    } catch (e) {
        showToast(e.message, "danger");
    }
}

function closeAuditModal() {
    document.getElementById("audit-modal-overlay").classList.remove("active");
}

// --- AUTOMATION & PIPELINE CONTROL LOGIC ---

async function loadAutomationSettings() {
    try {
        const res = await fetch(`${API_BASE}/api/automation/settings`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            document.getElementById("autonomous-toggle-switch").checked = data.autonomous_mode;
        }
    } catch (e) {
        console.error(e);
    }
}

async function handleAutonomousToggle() {
    const isChecked = document.getElementById("autonomous-toggle-switch").checked;
    try {
        const res = await fetch(`${API_BASE}/api/automation/toggle`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ autonomous_mode: isChecked })
        });
        if (res.ok) {
            showToast(`Autonomous Recruitment Mode set to: ${isChecked ? 'FULLY AUTONOMOUS' : 'MANUAL REVIEW'}`);
            // Reload rankings instantly to show retroactive evaluation changes
            if (activeJobId) {
                loadRankings();
            }
        } else {
            throw new Error("Could not toggle autonomous settings");
        }
    } catch (e) {
        showToast(e.message, "danger");
        document.getElementById("autonomous-toggle-switch").checked = !isChecked;
    }
}

async function loadOutboxFeed() {
    if (!token || !activeJobId) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/automation/outbox`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) return;
        
        const logs = await res.json();
        const container = document.getElementById("outbox-container");
        const feed = document.getElementById("outbox-timeline-feed");
        
        if (logs.length === 0) {
            container.style.display = "none";
            return;
        }
        
        container.style.display = "block";
        feed.innerHTML = "";
        
        logs.forEach(log => {
            const item = document.createElement("div");
            item.className = "timeline-feed-item";
            
            // Build Status Tag with Countdown if queued
            let statusText = log.status.toUpperCase();
            if (log.status === "queued" && log.sent_at) {
                const diffMs = new Date(log.sent_at) - new Date();
                if (diffMs > 0) {
                    const min = Math.floor(diffMs / 60000);
                    const sec = Math.floor((diffMs % 60000) / 1000);
                    statusText = `Queued (Dispatch in ${min}m ${sec}s)`;
                } else {
                    statusText = "Sending...";
                }
            }
            
            const timeStr = new Date(log.created_at).toLocaleTimeString();
            
            // Render Intercept button only if queued
            const showInterceptBtn = log.status === "queued";
            
            item.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 4px; text-align: left;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="outbox-status ${log.status}">${statusText}</span>
                        <strong style="color: var(--accent-primary-hover); font-size: 0.85rem;">${log.email_type.toUpperCase()}</strong>
                        <span style="font-size: 0.72rem; color: var(--text-muted);">${timeStr}</span>
                    </div>
                    <span style="font-size: 0.85rem; font-weight: 500; margin-top: 4px; color: var(--text-primary);">To: ${log.recipient_email}</span>
                    <span style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px;">Subject: ${log.subject}</span>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn-small" onclick="previewEmail('${log.id}', '${log.subject.replace(/'/g, "\\'")}', '${encodeURIComponent(log.body)}')">
                        <i class="fa-solid fa-eye" style="margin-right: 4px;"></i> Preview
                    </button>
                    ${showInterceptBtn ? `
                    <button class="btn-small danger" onclick="interceptQueuedEmail('${log.recipient_email}')">
                        <i class="fa-solid fa-shield-halved" style="margin-right: 4px;"></i> Safety Intercept
                    </button>
                    ` : ''}
                </div>
            `;
            feed.appendChild(item);
        });
    } catch (e) {
        console.error("Error loading outbox log feed:", e);
    }
}

function previewEmail(id, subject, bodyEscaped) {
    const body = decodeURIComponent(bodyEscaped);
    document.getElementById("email-preview-title").innerText = `Email Preview: ${subject}`;
    document.getElementById("email-preview-body").innerText = body;
    document.getElementById("email-preview-modal-overlay").classList.add("active");
}

function closeEmailPreviewModal() {
    document.getElementById("email-preview-modal-overlay").classList.remove("active");
}

async function interceptQueuedEmail(recipientEmail) {
    // Find matching candidate ranking
    const r = rankings.find(rank => rank.candidate && rank.candidate.email === recipientEmail);
    if (!r) {
        showToast("No active candidate ranking found to intercept.", "danger");
        return;
    }
    
    try {
        const res = await fetch(`${API_BASE}/api/interviews/override/${r.id}`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            showToast("Safety Intercept Successful! Email dispatch cancelled, flagged for manual review.");
            loadRankings();
        } else {
            throw new Error("Safety override execution failed");
        }
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// --- AI SCREENING HUB & REPLAY SYSTEM ---

// Tab Selector logic
function switchWorkspaceTab(tab) {
    activeTab = tab;
    
    const tabPipeline = document.getElementById("tab-pipeline");
    const tabScreening = document.getElementById("tab-screening");
    
    const jdDetails = document.getElementById("jd-details-container");
    const rankingsCont = document.getElementById("rankings-container");
    const outboxCont = document.getElementById("outbox-container");
    const screeningCont = document.getElementById("screening-hub-container");
    
    if (tab === "pipeline") {
        tabPipeline.classList.add("active");
        tabScreening.classList.remove("active");
        
        if (activeJobId) {
            jdDetails.style.display = "block";
            rankingsCont.style.display = "block";
            loadOutboxFeed();
        }
        screeningCont.style.display = "none";
    } else {
        tabPipeline.classList.remove("active");
        tabScreening.classList.add("active");
        
        jdDetails.style.display = "none";
        rankingsCont.style.display = "none";
        outboxCont.style.display = "none";
        
        if (activeJobId) {
            screeningCont.style.display = "block";
            loadInterviews();
        }
    }
}

// Fetch candidate transcripts and scores
async function loadInterviews() {
    if (!token || !activeJobId) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/interviews/results/${activeJobId}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) throw new Error("Error loading interviews");
        
        interviews = await res.json();
        renderInterviewsTable();
    } catch (e) {
        console.error("Error fetching live AI screenings:", e);
    }
}

// Render the interviews list table
function renderInterviewsTable() {
    const tbody = document.getElementById("screening-hub-tbody");
    if (!tbody) return;
    
    tbody.innerHTML = "";
    
    const candMap = {};
    rankings.forEach(r => {
        if (r.candidate) {
            candMap[r.candidate_id] = r.candidate;
        }
    });
    
    if (interviews.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 32px;">
                    No screening sessions scheduled or initiated yet. Ingest candidates to trigger outreach!
                </td>
            </tr>
        `;
        return;
    }
    
    interviews.forEach(iv => {
        const tr = document.createElement("tr");
        const cand = candMap[iv.candidate_id] || { name: `Candidate #${iv.candidate_id}`, email: "N/A" };
        
        let statusClass = "scheduled";
        let statusText = "Scheduled";
        if (iv.status === "in_progress") {
            statusClass = "in_progress";
            statusText = "In Progress";
        } else if (iv.status === "completed") {
            statusClass = "completed";
            statusText = "Completed";
        }
        
        let ratingsUI = `<span style="color: var(--text-muted); font-size: 0.8rem;">Pending completed session</span>`;
        if (iv.status === "completed") {
            ratingsUI = `
                <div style="display: flex; gap: 6px;">
                    <span class="skill-tag must" title="Communication Score" style="border-radius: 6px; font-weight: 700; padding: 4px 8px;">Comm: ${iv.communication_score}%</span>
                    <span class="skill-tag nice" title="Role Technology Fit" style="border-radius: 6px; font-weight: 700; padding: 4px 8px;">Tech: ${iv.technical_score}%</span>
                    <span class="skill-tag" title="Confidence Score" style="border-radius: 6px; font-weight: 700; padding: 4px 8px; color: var(--accent-warning); background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.2);">Conf: ${iv.confidence_score}%</span>
                </div>
            `;
        }
        
        const summaryText = iv.ai_summary || "Conversational screening round initiated. Active data feed pending.";
        const showReplayBtn = iv.status === "completed" || (iv.transcript && iv.transcript.length > 0);
        
        tr.innerHTML = `
            <td>
                <div class="candidate-name-cell">
                    <strong style="color: var(--text-primary); font-size: 0.95rem;">${cand.name}</strong>
                    <span class="cand-title">${cand.email}</span>
                </div>
            </td>
            <td>
                <span class="status-indicator ${statusClass}">${statusText}</span>
            </td>
            <td>${ratingsUI}</td>
            <td>
                <div style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.85rem; color: var(--text-secondary);" title="${summaryText}">
                    ${summaryText}
                </div>
            </td>
            <td>
                <div class="table-actions">
                    ${showReplayBtn ? `
                        <button class="btn-small success" onclick="viewInterviewAnalysis(${iv.id})">
                            <i class="fa-solid fa-play" style="margin-right: 4px;"></i> View Replay
                        </button>
                    ` : `
                        <button class="btn-small" style="opacity: 0.5; cursor: not-allowed;" disabled>
                            <i class="fa-solid fa-lock" style="margin-right: 4px;"></i> Locked
                        </button>
                    `}
                    <button class="btn-small" onclick="window.open('/static/screening.html?cand_id=${iv.candidate_id}&job_id=${iv.job_id}', '_blank')">
                        <i class="fa-solid fa-flask" style="margin-right: 4px;"></i> Sandbox Test
                    </button>
                </div>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}

// Open chat transcript replay & metrics modal
function viewInterviewAnalysis(ivId) {
    const iv = interviews.find(i => i.id === ivId);
    if (!iv) return;
    
    const candMap = {};
    rankings.forEach(r => {
        if (r.candidate) candMap[r.candidate_id] = r.candidate;
    });
    const cand = candMap[iv.candidate_id] || { name: `Candidate #${iv.candidate_id}`, email: "N/A" };
    
    document.getElementById("replay-cand-name").innerText = `${cand.name} - Conversational Replay`;
    document.getElementById("replay-cand-email").innerText = cand.email;
    
    const overallScore = Math.round((iv.communication_score + iv.technical_score + iv.confidence_score) / 3);
    const scoreBadge = document.getElementById("replay-overall-score");
    scoreBadge.innerText = iv.status === "completed" ? `${overallScore}%` : "N/A";
    scoreBadge.className = `score-badge ${iv.status === "completed" ? (overallScore >= 80 ? 'excellent' : (overallScore >= 60 ? 'good' : 'average')) : 'average'}`;
    
    const outcomeText = document.getElementById("replay-assessment-outcome");
    outcomeText.innerText = iv.status === "completed" ? (overallScore >= 65 ? "Cleared AI Screening" : "AI Screening Failed") : "Evaluating Fit";
    
    const completedTime = document.getElementById("replay-completed-time");
    completedTime.innerText = iv.completed_at ? `Session finished: ${new Date(iv.completed_at).toLocaleString()}` : "Ongoing Session";
    
    document.getElementById("metric-comm-val").innerText = `${iv.communication_score}%`;
    document.getElementById("metric-comm-bar").style.width = `${iv.communication_score}%`;
    
    document.getElementById("metric-tech-val").innerText = `${iv.technical_score}%`;
    document.getElementById("metric-tech-bar").style.width = `${iv.technical_score}%`;
    
    document.getElementById("metric-conf-val").innerText = `${iv.confidence_score}%`;
    document.getElementById("metric-conf-bar").style.width = `${iv.confidence_score}%`;
    
    document.getElementById("replay-ai-summary").innerText = iv.ai_summary || "Session is still active. Complete transcription details are streaming dynamically.";
    
    // Proctoring cheating flag dynamic banner display
    const warningBanner = document.getElementById("replay-cheating-warning-banner");
    if (iv.cheating_suspected) {
        if (!warningBanner) {
            const banner = document.createElement("div");
            banner.id = "replay-cheating-warning-banner";
            banner.className = "glass-panel";
            banner.style.padding = "10px 14px";
            banner.style.marginBottom = "12px";
            banner.style.fontSize = "0.78rem";
            banner.style.color = "#ef4444";
            banner.style.borderColor = "rgba(239, 68, 68, 0.3)";
            banner.style.background = "rgba(239, 68, 68, 0.05)";
            banner.style.borderRadius = "8px";
            banner.style.textAlign = "center";
            banner.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <strong>Proctoring Alert:</strong> Candidate switched tabs/windows during this proctored session! Cheating suspected.`;
            
            const summaryContainer = document.getElementById("replay-ai-summary").parentNode;
            summaryContainer.parentNode.insertBefore(banner, summaryContainer);
        } else {
            warningBanner.style.display = "block";
        }
    } else {
        if (warningBanner) {
            warningBanner.style.display = "none";
        }
    }
    
    const stream = document.getElementById("replay-chat-stream");
    stream.innerHTML = "";
    
    const transcriptList = iv.transcript || [];
    if (transcriptList.length === 0) {
        stream.innerHTML = `<div style="text-align: center; color: var(--text-muted); margin-top: 32px; font-style: italic;">No dialogue logs recorded.</div>`;
    } else {
        transcriptList.forEach(msg => {
            const bubbleRow = document.createElement("div");
            const isAi = msg.role === "ai";
            bubbleRow.className = `replay-chat-bubble-row ${isAi ? 'ai' : 'candidate'}`;
            
            const avatar = document.createElement("div");
            avatar.className = "replay-bubble-avatar";
            avatar.innerHTML = isAi ? '<i class="fa-solid fa-robot"></i>' : '<i class="fa-solid fa-user"></i>';
            
            const text = document.createElement("div");
            text.className = "replay-bubble-text";
            text.innerText = msg.text;
            
            bubbleRow.appendChild(avatar);
            bubbleRow.appendChild(text);
            stream.appendChild(bubbleRow);
        });
    }
    
    document.getElementById("interview-details-modal-overlay").classList.add("active");
    
    setTimeout(() => {
        stream.scrollTop = stream.scrollHeight;
    }, 100);
}

function closeInterviewDetailsModal() {
    document.getElementById("interview-details-modal-overlay").classList.remove("active");
}

// --- CANDIDATE SEARCH, FILTER & LINK FROM POOL ---

function filterCandidates() {
    const searchVal = document.getElementById("candidate-search-input") ? document.getElementById("candidate-search-input").value.toLowerCase().trim() : "";
    const statusVal = document.getElementById("candidate-status-filter") ? document.getElementById("candidate-status-filter").value : "all";
    
    const rows = document.querySelectorAll("#rankings-tbody tr");
    rows.forEach(row => {
        const nameCell = row.querySelector(".candidate-name-cell");
        if (!nameCell) return;
        const name = nameCell.querySelector("strong").innerText.toLowerCase();
        const subtitle = nameCell.querySelector(".cand-title").innerText.toLowerCase();
        
        const statusIndicator = row.querySelector(".status-indicator");
        const status = statusIndicator ? statusIndicator.innerText.toLowerCase().trim() : "";
        
        const matchesSearch = !searchVal || name.includes(searchVal) || subtitle.includes(searchVal);
        const matchesStatus = statusVal === "all" || status === statusVal;
        
        if (matchesSearch && matchesStatus) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

let poolCandidates = [];

function openLinkCandidateModal() {
    document.getElementById("pool-modal-overlay").classList.add("active");
    document.getElementById("pool-search-input").value = "";
    loadPoolCandidates();
}

function closeLinkCandidateModal() {
    document.getElementById("pool-modal-overlay").classList.remove("active");
}

async function loadPoolCandidates() {
    const tbody = document.getElementById("pool-candidates-tbody");
    tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 16px;">Loading general candidate pool...</td></tr>`;
    
    try {
        const res = await fetch(`${API_BASE}/api/candidates`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) throw new Error("Error loading candidates from pool");
        
        poolCandidates = await res.json();
        renderPoolCandidatesTable();
    } catch (e) {
        showToast(e.message, "danger");
        tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--accent-danger); padding: 16px;">Failed to load pool.</td></tr>`;
    }
}

function renderPoolCandidatesTable() {
    const tbody = document.getElementById("pool-candidates-tbody");
    tbody.innerHTML = "";
    
    // Filter candidates that are already in our rankings to prevent duplicate links
    const rankedCandidateIds = rankings.map(r => r.candidate_id);
    const availablePool = poolCandidates.filter(c => !rankedCandidateIds.includes(c.id));
    
    if (availablePool.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 16px;">No new candidates available in the pool.</td></tr>`;
        return;
    }
    
    availablePool.forEach(c => {
        const tr = document.createElement("tr");
        tr.className = "pool-candidate-row";
        
        const maxSkills = 4;
        const skillsList = c.skills || [];
        const skillsStr = skillsList.slice(0, maxSkills).join(", ") + (skillsList.length > maxSkills ? "..." : "");
        
        tr.innerHTML = `
            <td>
                <div class="candidate-name-cell">
                    <strong>${c.name}</strong>
                    <span class="cand-title">${c.email || "No email"}</span>
                </div>
            </td>
            <td>
                <span class="cand-title" style="font-weight: 500;">${skillsStr || "No skills extracted"}</span>
            </td>
            <td>
                <button class="btn-small success" onclick="linkCandidate(${c.id})" style="padding: 6px 12px; height: 32px;">Add</button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}

function filterPoolCandidates() {
    const searchVal = document.getElementById("pool-search-input").value.toLowerCase().trim();
    const rows = document.querySelectorAll("#pool-candidates-tbody tr");
    
    rows.forEach(row => {
        if (!row.classList.contains("pool-candidate-row")) return;
        const nameCell = row.querySelector(".candidate-name-cell");
        if (!nameCell) return;
        
        const name = nameCell.querySelector("strong").innerText.toLowerCase();
        const email = nameCell.querySelector(".cand-title").innerText.toLowerCase();
        
        const skillsCell = row.querySelectorAll("td")[1];
        const skills = skillsCell ? skillsCell.innerText.toLowerCase() : "";
        
        if (!searchVal || name.includes(searchVal) || email.includes(searchVal) || skills.includes(searchVal)) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

async function linkCandidate(candidateId) {
    if (!activeJobId) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/jobs/${activeJobId}/link/${candidateId}`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.detail || "Error linking candidate to job");
        }
        
        showToast("Candidate successfully added to job workspace!");
        
        // Reload rankings list
        await loadRankings();
        
        // Close modal
        closeLinkCandidateModal();
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// --- MAIL SETTINGS MODAL OPERATIONS ---

function openMailSettingsModal() {
    document.getElementById("smtp-host-input").value = "";
    document.getElementById("smtp-port-input").value = "587";
    document.getElementById("smtp-username-input").value = "";
    document.getElementById("smtp-password-input").value = "";
    document.getElementById("smtp-from-input").value = "";
    
    // Fetch existing settings
    fetch(`${API_BASE}/api/auth/smtp`, {
        headers: { "Authorization": `Bearer ${token}` }
    })
    .then(res => {
        if (res.ok) return res.json();
        throw new Error("Could not load mail settings.");
    })
    .then(data => {
        document.getElementById("smtp-host-input").value = data.smtp_host || "";
        document.getElementById("smtp-port-input").value = data.smtp_port || 587;
        document.getElementById("smtp-username-input").value = data.smtp_username || "";
        document.getElementById("smtp-password-input").value = ""; // Don't show password
        document.getElementById("smtp-from-input").value = data.smtp_from || "";
    })
    .catch(e => console.error("Error loading SMTP settings:", e));

    document.getElementById("mail-settings-overlay").classList.add("active");
}

function closeMailSettingsModal() {
    document.getElementById("mail-settings-overlay").classList.remove("active");
}

async function saveMailSettings(event) {
    if (event) event.preventDefault();
    
    const host = document.getElementById("smtp-host-input").value.trim();
    const port = parseInt(document.getElementById("smtp-port-input").value);
    const username = document.getElementById("smtp-username-input").value.trim();
    const password = document.getElementById("smtp-password-input").value.trim();
    const fromAddr = document.getElementById("smtp-from-input").value.trim();
    
    const payload = {
        smtp_host: host || null,
        smtp_port: port || 587,
        smtp_username: username || null,
        smtp_from: fromAddr || null
    };
    
    if (password) {
        payload.smtp_password = password;
    }
    
    try {
        const res = await fetch(`${API_BASE}/api/auth/smtp`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Error saving SMTP settings.");
        }
        
        showToast("Mail configuration successfully saved!");
        checkSMTPSettings();
        closeMailSettingsModal();
    } catch (e) {
        showToast(e.message, "danger");
    }
}

async function sendTestEmail() {
    const host = document.getElementById("smtp-host-input").value.trim();
    const port = parseInt(document.getElementById("smtp-port-input").value);
    const username = document.getElementById("smtp-username-input").value.trim();
    const password = document.getElementById("smtp-password-input").value.trim();
    const fromAddr = document.getElementById("smtp-from-input").value.trim();
    
    if (!host || !username) {
        showToast("Please enter at least Host and Username to send test email.", "warning");
        return;
    }
    
    const payload = {
        smtp_host: host,
        smtp_port: port || 587,
        smtp_username: username,
        smtp_from: fromAddr || null
    };
    if (password) {
        payload.smtp_password = password;
    }
    
    try {
        // Save first
        let res = await fetch(`${API_BASE}/api/auth/smtp`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Could not save settings prior to verification test.");
        
        showToast("Sending test verification email...");
        
        res = await fetch(`${API_BASE}/api/auth/smtp/test`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast(data.message || "Test email dispatched successfully!");
            checkSMTPSettings();
        } else {
            throw new Error(data.detail || "Test email dispatch failed.");
        }
    } catch (e) {
        showToast(e.message, "danger");
    }
}

// Check SMTP settings on the server to update the warning banner
async function checkSMTPSettings() {
    if (!token) return;
    try {
        const res = await fetch(`${API_BASE}/api/auth/smtp`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            const banner = document.getElementById("smtp-warning-banner");
            if (banner) {
                if (!data.smtp_host || !data.smtp_username) {
                    banner.style.display = "flex";
                } else {
                    banner.style.display = "none";
                }
            }
        }
    } catch (e) {
        console.error("Error checking SMTP settings:", e);
    }
}


