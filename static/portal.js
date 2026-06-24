// AI Recruiter - Candidate Feedback Portal Logic
const API_BASE = window.location.origin;

let candidateId = "";
let feedbackData = null;

document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token") || params.get("cand_id");
    
    if (!token) {
        renderErrorState("Invalid shareable link. Missing Candidate credentials.");
        return;
    }
    
    candidateId = token;
    fetchCandidateFeedback();
});

async function fetchCandidateFeedback() {
    try {
        const response = await fetch(`${API_BASE}/api/candidate/${candidateId}`);
        if (response.status === 404) {
            renderErrorState("This link is invalid or has expired.", "Not Found");
            return;
        }
        if (!response.ok) {
            renderErrorState("Something went wrong, contact recruiter.", "Error State");
            return;
        }
        
        feedbackData = await response.json();
        
        // Hide infinite loader
        const loader = document.getElementById("portal-loader");
        if (loader) loader.style.display = "none";
        
        // Show main header and tabs/content
        const header = document.getElementById("header-section");
        if (header) header.style.display = "block";
        
        renderPortalContent();
    } catch (error) {
        renderErrorState("Something went wrong, contact recruiter.", "Error State");
    }
}

function getInitials(name) {
    if (!name) return "--";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, Math.min(name.length, 2)).toUpperCase();
}

function renderPortalContent() {
    const outcomeBadge = document.getElementById("outcome-badge");
    const nameEl = document.getElementById("candidate-name");
    const roleEl = document.getElementById("role-applied");
    const companyEl = document.getElementById("company-name");
    const dateEl = document.getElementById("date-applied");
    const avatarEl = document.getElementById("candidate-avatar");
    const outcomeDesc = document.getElementById("outcome-desc");
    const ringEl = document.getElementById("score-ring-element");
    const ringText = document.getElementById("score-ring-text");
    
    const tabs = document.getElementById("portal-tabs");
    
    const name = feedbackData.name || "Applicant";
    const role = feedbackData.role_applied || "Software Engineering Role";
    const company = feedbackData.company_name || "AI Recruiter Workspace Hub";
    const dateStr = feedbackData.date_applied || "May 31, 2026";
    const score = feedbackData.fit_score || 0;
    
    // Set text elements
    if (nameEl) nameEl.innerText = name;
    if (roleEl) roleEl.innerText = role;
    if (companyEl) companyEl.innerHTML = `<i class="fa-solid fa-building" style="margin-right: 4px;"></i> ${company}`;
    if (dateEl) dateEl.innerHTML = `<i class="fa-regular fa-calendar" style="margin-right: 4px;"></i> ${dateStr}`;
    
    // Set initials avatar
    if (avatarEl) avatarEl.innerText = getInitials(name);
    
    // Set score ring glowing color
    if (ringEl && ringText) {
        const roundedScore = Math.round(score);
        ringText.innerText = `${roundedScore}%`;
        ringEl.className = "score-ring"; // Reset styles
        if (roundedScore >= 80) {
            ringEl.classList.add("green");
        } else if (roundedScore >= 60) {
            ringEl.classList.add("yellow");
        } else {
            ringEl.classList.add("red");
        }
    }
    
    if (feedbackData.status === "shortlisted") {
        // --- SELECTED STATE ---
        if (outcomeBadge) {
            outcomeBadge.className = "portal-status-badge shortlisted";
            outcomeBadge.innerHTML = '<i class="fa-solid fa-circle-check"></i> Cleared';
        }
        
        if (outcomeDesc) {
            outcomeDesc.innerHTML = `
                Congratulations, **${name}**! We are thrilled to share that your application for the **${role}** position has been advanced! 
                Our talent acquisition team has successfully verified your technical criteria and screening milestones. 
                <br><br>
                📅 **Next Steps**: A hiring manager will reach out to your primary contact details within 24 hours to schedule your core system design panel.
            `;
        }
        
        // Hide tabs since they are cleared/advanced
        if (tabs) tabs.style.display = "none";
        hideAllTabsContent();
    } else if (feedbackData.status === "rejected") {
        // --- COACHING / REJECTED STATE ---
        if (outcomeBadge) {
            outcomeBadge.className = "portal-status-badge rejected";
            outcomeBadge.innerHTML = '<i class="fa-solid fa-graduation-cap"></i> Coaching Mode';
        }
        
        if (outcomeDesc) {
            outcomeDesc.innerHTML = feedbackData.rejection_feedback || `
                Thank you for participating in our screening process for the **${role}** workspace. While we are unable 
                to advance your candidacy at this time, our AI Recruiter has compiled highly constructive, tailored learning bridges 
                and hands-on portfolio recommendations to help you close your technical gaps for future applications.
            `;
        }
        
        // Show tabs & build lists
        if (tabs) tabs.style.display = "flex";
        buildGapsList();
        buildActionPlanList();
        buildStudyLinks();
        
        // Default to showing first tab
        switchPortalTab("gaps");
    } else {
        // --- PENDING STATE ---
        if (outcomeBadge) {
            outcomeBadge.className = "portal-status-badge pending";
            outcomeBadge.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Active Screening';
        }
        
        if (outcomeDesc) {
            outcomeDesc.innerText = `Your application for the ${role} role is currently in progress. Complete your live Conversational Screening Test to view complete AI analysis reports and stats.`;
        }
        
        if (tabs) tabs.style.display = "none";
        hideAllTabsContent();
    }
}

function hideAllTabsContent() {
    const sectionGaps = document.getElementById("section-gaps");
    const sectionAction = document.getElementById("section-action");
    const sectionStudy = document.getElementById("section-study");
    if (sectionGaps) sectionGaps.style.display = "none";
    if (sectionAction) sectionAction.style.display = "none";
    if (sectionStudy) sectionStudy.style.display = "none";
}

window.switchPortalTab = function(tabId) {
    const sectionGaps = document.getElementById("section-gaps");
    const sectionAction = document.getElementById("section-action");
    const sectionStudy = document.getElementById("section-study");
    
    const tabGaps = document.getElementById("tab-gaps");
    const tabAction = document.getElementById("tab-action");
    const tabStudy = document.getElementById("tab-study");
    
    // Hide all
    hideAllTabsContent();
    
    if (tabGaps) tabGaps.classList.remove("active");
    if (tabAction) tabAction.classList.remove("active");
    if (tabStudy) tabStudy.classList.remove("active");
    
    // Show active
    if (tabId === "gaps" && sectionGaps && tabGaps) {
        sectionGaps.style.display = "flex";
        tabGaps.classList.add("active");
    } else if (tabId === "action" && sectionAction && tabAction) {
        sectionAction.style.display = "flex";
        tabAction.classList.add("active");
    } else if (tabId === "study" && sectionStudy && tabStudy) {
        sectionStudy.style.display = "flex";
        tabStudy.classList.add("active");
    }
};

function buildGapsList() {
    const container = document.getElementById("gaps-list-container");
    if (!container) return;
    container.innerHTML = "";
    
    const gaps = feedbackData.skill_gaps || [];
    
    if (gaps.length === 0) {
        container.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 20px;">No core skill gaps identified! Excellent background alignment.</p>`;
        return;
    }
    
    gaps.forEach((gap, index) => {
        const severityClass = gap.severity ? gap.severity.toLowerCase().split(' ')[0] : "intermediate";
        
        // Restore progress slider state from localStorage
        const storageKey = `gap_progress_${candidateId}_${gap.name}`;
        const savedProgress = localStorage.getItem(storageKey);
        const progress = savedProgress !== null ? parseInt(savedProgress) : 0;
        
        const item = document.createElement("div");
        item.className = "gap-card-item";
        
        item.innerHTML = `
            <div class="gap-card-header">
                <span class="gap-card-title">${gap.name}</span>
                <span class="gap-card-severity ${severityClass}">${gap.severity || 'Intermediate needed'}</span>
            </div>
            <div class="gap-card-desc">${gap.why_it_matters}</div>
            <div class="gap-progress-control">
                <div class="gap-progress-label-row">
                    <span>Self-Assessed Progress</span>
                    <span id="slider-val-${index}">${progress}%</span>
                </div>
                <input type="range" class="gap-slider-input" min="0" max="100" value="${progress}" id="slider-input-${index}" oninput="updateGapProgress('${gap.name}', ${index}, this.value)">
                <div class="gap-slider-bar-fill">
                    <div class="gap-slider-bar-fill-inner" id="slider-fill-${index}" style="width: ${progress}%;"></div>
                </div>
            </div>
        `;
        container.appendChild(item);
    });
}

window.updateGapProgress = function(gapName, index, val) {
    // Save to localStorage
    const storageKey = `gap_progress_${candidateId}_${gapName}`;
    localStorage.setItem(storageKey, val);
    
    // Update labels and bar fills live
    const valSpan = document.getElementById(`slider-val-${index}`);
    if (valSpan) valSpan.innerText = `${val}%`;
    
    const fillInner = document.getElementById(`slider-fill-${index}`);
    if (fillInner) fillInner.style.width = `${val}%`;
};

function buildActionPlanList() {
    const container = document.getElementById("action-list-container");
    if (!container) return;
    container.innerHTML = "";
    
    const steps = feedbackData.action_plan || [];
    
    if (steps.length === 0) {
        container.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 20px;">No specific portfolio project recommendations. General learning active.</p>`;
        return;
    }
    
    steps.forEach((step, index) => {
        // Restore checked state from localStorage
        const storageKey = `action_item_${candidateId}_${index}`;
        const isChecked = localStorage.getItem(storageKey) === "true";
        
        const item = document.createElement("div");
        item.className = `action-checklist-item ${isChecked ? 'checked' : ''}`;
        item.id = `action-item-${index}`;
        
        item.innerHTML = `
            <div class="action-item-left">
                <label class="action-checkbox-wrapper">
                    <input type="checkbox" class="action-checkbox" ${isChecked ? 'checked' : ''} onchange="toggleActionItem(${index}, this.checked)">
                    <div class="action-checkbox-custom"><i class="fa-solid fa-check"></i></div>
                </label>
                <span class="action-item-text">${step.task}</span>
            </div>
            <div class="action-time-badge">${step.time || '~3 days'}</div>
        `;
        container.appendChild(item);
    });
}

window.toggleActionItem = function(index, isChecked) {
    const storageKey = `action_item_${candidateId}_${index}`;
    localStorage.setItem(storageKey, isChecked ? "true" : "false");
    
    const itemEl = document.getElementById(`action-item-${index}`);
    if (itemEl) {
        if (isChecked) {
            itemEl.classList.add("checked");
        } else {
            itemEl.classList.remove("checked");
        }
    }
};

function getPlatformBadgeClass(platform) {
    const plat = (platform || "Docs").toLowerCase();
    if (plat.includes("youtube")) return "youtube";
    if (plat.includes("udemy")) return "udemy";
    if (plat.includes("github")) return "github";
    return "docs";
}

function getPlatformIcon(platform) {
    const plat = (platform || "Docs").toLowerCase();
    if (plat.includes("youtube")) return "fa-brands fa-youtube";
    if (plat.includes("udemy")) return "fa-solid fa-graduation-cap";
    if (plat.includes("github")) return "fa-brands fa-github";
    return "fa-regular fa-file-lines";
}

function buildStudyLinks() {
    const container = document.getElementById("study-links-container");
    if (!container) return;
    container.innerHTML = "";
    
    const resources = feedbackData.study_resources || [];
    
    if (resources.length === 0) {
        container.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 20px; grid-column: span 2;">No study guides registered. Utilize general engineering resources.</p>`;
        return;
    }
    
    resources.forEach(res => {
        const card = document.createElement("a");
        card.href = res.url || "#";
        card.target = "_blank";
        card.className = "study-resource-card";
        
        card.innerHTML = `
            <div class="study-card-header">
                <span class="platform-badge ${getPlatformBadgeClass(res.platform)}">
                    <i class="${getPlatformIcon(res.platform)}"></i> ${res.platform || 'Docs'}
                </span>
                <span style="font-size: 0.75rem; color: var(--text-muted);"><i class="fa-regular fa-clock" style="margin-right: 4px;"></i> ${res.duration || '4 hours'}</span>
            </div>
            <div class="study-card-title">${res.name || 'Comprehensive Guide'}</div>
            <div class="study-card-footer">
                <span class="study-card-tag">${res.relevance || 'Engineering Gap'}</span>
                <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.75rem; color: var(--text-muted);"></i>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderErrorState(message, type = "Error") {
    // Hide infinite loader
    const loader = document.getElementById("portal-loader");
    if (loader) loader.style.display = "none";
    
    // Hide main header and tabs/content
    const header = document.getElementById("header-section");
    if (header) header.style.display = "none";
    
    const tabs = document.getElementById("portal-tabs");
    if (tabs) tabs.style.display = "none";
    
    hideAllTabsContent();
    
    const portal = document.getElementById("portal-container");
    if (portal) {
        portal.innerHTML = `
            <div class="portal-header-card glass-panel" style="border-color: rgba(239, 68, 68, 0.2); background: rgba(239, 68, 68, 0.02); text-align: center; padding: 48px;">
                <i class="fa-solid fa-circle-exclamation" style="font-size: 3rem; color: var(--accent-danger); margin-bottom: 16px;"></i>
                <h2 class="portal-outcome-title" style="color: var(--accent-danger); margin-bottom: 8px;">${type === "Not Found" ? "Link Invalid or Expired" : "System Error"}</h2>
                <p class="portal-outcome-desc" style="color: var(--text-secondary); max-width: 500px; margin: 0 auto; line-height: 1.6;">${message}</p>
                <br>
                <button onclick="window.location.reload()" class="btn-secondary" style="font-size: 0.85rem; padding: 10px 20px; border-radius: 8px; cursor: pointer; background: hsla(225, 20%, 25%, 0.3); border: 1px solid var(--border-color); color: #ffffff;">
                    <i class="fa-solid fa-arrows-rotate"></i> Reload Page
                </button>
            </div>
        `;
    }
}
