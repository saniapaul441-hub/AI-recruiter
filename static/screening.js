// AI Recruiter - Conversational Screening Room Client Logic
const API_BASE = window.location.origin;
const WS_BASE = window.location.origin.replace(/^http/, "ws");

let ws = null;
let currentCandidateId = "";
let currentJobId = "";
let currentAIBubble = null;
let currentStepNum = 1;
let step1Clicks = 0;
let interviewActive = false;

let localStream = null;
let cameraActive = false;
let micActive = true;
let audioInterval = null;

// Speech Synthesis (Text-To-Speech) states and helpers for natural AI voice
let preloadedVoice = null;
let spokenTextLength = 0;

function loadVoice() {
    if (!('speechSynthesis' in window)) return;
    const voices = window.speechSynthesis.getVoices();
    // Look for a premium natural English voice
    preloadedVoice = voices.find(voice => 
        voice.name.includes("Google US English") || 
        voice.name.includes("Natural") || 
        voice.name.includes("Microsoft Zira") ||
        voice.name.includes("Samantha") ||
        voice.name.includes("Hazel")
    ) || voices.find(voice => voice.lang.startsWith("en-")) || voices[0];
}

// Pre-load voices on startup
if ('speechSynthesis' in window) {
    loadVoice();
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = loadVoice;
    }
}

function speakSentence(text) {
    if (!('speechSynthesis' in window)) return;
    
    // Strip HTML tags if any exist in the streamed text
    const cleanedText = text.replace(/<[^>]*>/g, '').trim();
    if (!cleanedText) return;
    
    const utterance = new SpeechSynthesisUtterance(cleanedText);
    
    if (!preloadedVoice) {
        loadVoice();
    }
    if (preloadedVoice) {
        utterance.voice = preloadedVoice;
    }
    
    // Natural, professional speech attributes
    utterance.rate = 1.0; 
    utterance.pitch = 1.05; 
    
    window.speechSynthesis.speak(utterance);
}

function speakNewSentences(text) {
    if (!('speechSynthesis' in window)) return;
    
    const unspokenText = text.substring(spokenTextLength);
    // Matches end of sentence (. ? !) followed by a space
    const sentenceEndRegex = /[.?!]\s+/g;
    let match;
    let lastIndex = -1;
    
    while ((match = sentenceEndRegex.exec(unspokenText)) !== null) {
        lastIndex = match.index + match[0].length;
    }
    
    if (lastIndex !== -1) {
        const sentenceToSpeak = unspokenText.substring(0, lastIndex).trim();
        if (sentenceToSpeak) {
            speakSentence(sentenceToSpeak);
            spokenTextLength += lastIndex;
        }
    }
}

let proctoringAlertActive = false;

function setupTabSwitchProctoring() {
    if (proctoringAlertActive) return;
    proctoringAlertActive = true;

    // Detect tab switching (visibility change)
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden" && cameraActive && interviewActive) {
            handleProctoringViolation("tab_switch");
        }
    });

    // Detect focus loss (window blur)
    window.addEventListener("blur", () => {
        if (cameraActive && interviewActive) {
            handleProctoringViolation("window_blur");
        }
    });
}

function handleProctoringViolation(type) {
    console.warn(`PROCTORING VIOLATION: ${type} detected!`);
    
    // 1. Display highly visible glass-panel proctoring warning in chat stream
    const chatStream = document.getElementById("chat-stream");
    const warningNotice = document.createElement("div");
    warningNotice.className = "glass-panel";
    warningNotice.style.padding = "12px 16px";
    warningNotice.style.marginTop = "8px";
    warningNotice.style.fontSize = "0.8rem";
    warningNotice.style.color = "#ef4444"; // Accent danger red
    warningNotice.style.borderColor = "rgba(239, 68, 68, 0.3)";
    warningNotice.style.background = "rgba(239, 68, 68, 0.05)";
    warningNotice.style.textAlign = "center";
    warningNotice.style.animation = "pulse-glow 1.5s infinite ease-in-out";
    
    warningNotice.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <strong>Proctoring Alert:</strong> Tab switch or window blur detected. Please stay focused on the interview tab to prevent disqualification.`;
    chatStream.appendChild(warningNotice);
    scrollChatBottom();
    
    // 2. Play vocal warning to candidate
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const warningUtterance = new SpeechSynthesisUtterance("Warning. Tab switch detected. Please stay on this screen.");
        warningUtterance.rate = 1.0;
        warningUtterance.pitch = 0.9; // Authoritative voice
        window.speechSynthesis.speak(warningUtterance);
    }
    
    // 3. Post warning logs to backend proctoring API endpoint
    if (currentCandidateId && currentJobId) {
        fetch(`${API_BASE}/api/interviews/proctor/warning/${currentCandidateId}/${currentJobId}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ type: type })
        })
        .then(res => res.json())
        .then(data => {
            console.log("Proctoring alert registered on backend:", data);
        })
        .catch(err => {
            console.error("Failed to post proctoring alert:", err);
        });
    }
}

// Read query params on load
document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const candId = params.get("cand_id");
    const jobId = params.get("job_id");
    
    if (candId) {
        document.getElementById("candidate-id-input").value = candId;
        currentCandidateId = candId;
    }
    if (jobId) {
        currentJobId = jobId;
    } else {
        currentJobId = "1"; // Default mock job
    }

    // Initialize anti-cheating proctoring listeners
    setupTabSwitchProctoring();

    // Auto-launch interview round if candId query parameter is provided in the URL!
    if (candId) {
        setTimeout(() => {
            startInterviewSession();
        }, 800);
    }
});

function handleInputKey(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendCandidateMessage();
    }
}

async function initWebcam() {
    const videoElement = document.getElementById("webcam-stream");
    const fallbackElement = document.getElementById("webcam-fallback");
    const toggleCamBtn = document.getElementById("toggle-camera-btn");
    const toggleMicBtn = document.getElementById("toggle-mic-btn");
    const faceScanner = document.getElementById("face-scanner");
    
    // Reset flags
    cameraActive = false;
    micActive = false;
    
    try {
        // Step 1: Try to capture both camera & microphone first
        try {
            localStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: "user"
                },
                audio: true
            });
            cameraActive = true;
            micActive = true;
            console.log("Audio and Video tracks loaded successfully.");
        } catch (mediaError) {
            console.warn("Failed both Video + Audio, trying video-only fallback:", mediaError);
            // Step 2: Try camera-only fallback if mic is missing or blocked
            try {
                localStream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        width: { ideal: 640 },
                        height: { ideal: 480 },
                        facingMode: "user"
                    },
                    audio: false
                });
                cameraActive = true;
                micActive = false;
                console.log("Video-only track loaded successfully.");
            } catch (videoError) {
                console.warn("Failed video-only capture, trying audio-only fallback:", videoError);
                // Step 3: Try mic-only fallback if camera is missing or blocked
                localStream = await navigator.mediaDevices.getUserMedia({
                    video: false,
                    audio: true
                });
                cameraActive = false;
                micActive = true;
                console.log("Audio-only track loaded successfully.");
            }
        }
        
        // Handle Video/Camera UI State
        updateCameraUI();
        
        // Handle Microphone UI State
        if (micActive) {
            toggleMicBtn.classList.add("active");
            toggleMicBtn.querySelector("i").className = "fa-solid fa-microphone";
        } else {
            toggleMicBtn.classList.remove("active");
            toggleMicBtn.querySelector("i").className = "fa-solid fa-microphone-slash";
        }
        
        startAudioVisualizer();
        console.log("Webcam/Mic initialized successfully. Camera:", cameraActive, "Mic:", micActive);
    } catch (error) {
        console.warn("Could not access any webcam or microphone devices:", error);
        
        // Show offline fallback but keep scanned layout intact
        fallbackElement.style.display = "flex";
        faceScanner.style.opacity = "0.3";
        
        toggleCamBtn.classList.remove("active");
        toggleCamBtn.querySelector("i").className = "fa-solid fa-video-slash";
        
        toggleMicBtn.classList.remove("active");
        toggleMicBtn.querySelector("i").className = "fa-solid fa-microphone-slash";
        
        // Add a warning note to chat display gently
        const chatStream = document.getElementById("chat-stream");
        const sysNotice = document.createElement("div");
        sysNotice.className = "glass-panel";
        sysNotice.style.padding = "10px 14px";
        sysNotice.style.fontSize = "0.78rem";
        sysNotice.style.color = "var(--accent-warning, #f59e0b)";
        sysNotice.style.borderColor = "rgba(245, 158, 11, 0.2)";
        sysNotice.style.background = "rgba(245, 158, 11, 0.02)";
        sysNotice.style.textAlign = "center";
        sysNotice.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Camera permission was not granted or devices are disconnected. Simulated proctoring active.`;
        chatStream.appendChild(sysNotice);
        scrollChatBottom();
    }
}

function toggleWebcam() {
    if (cameraActive) {
        if (localStream) {
            localStream.getVideoTracks().forEach(track => track.enabled = false);
        }
        cameraActive = false;
        // Stop any currently speaking AI voice when the video stream is deactivated
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        updateCameraUI();
    } else {
        if (localStream) {
            const videoTracks = localStream.getVideoTracks();
            if (videoTracks.length > 0) {
                videoTracks.forEach(track => track.enabled = true);
                cameraActive = true;
                updateCameraUI();
            } else {
                initWebcam();
            }
        } else {
            initWebcam();
        }
    }
}

function toggleMic() {
    const toggleMicBtn = document.getElementById("toggle-mic-btn");
    if (localStream) {
        const audioTracks = localStream.getAudioTracks();
        if (audioTracks.length > 0) {
            micActive = !micActive;
            audioTracks.forEach(track => track.enabled = micActive);
            if (micActive) {
                toggleMicBtn.classList.add("active");
                toggleMicBtn.querySelector("i").className = "fa-solid fa-microphone";
            } else {
                toggleMicBtn.classList.remove("active");
                toggleMicBtn.querySelector("i").className = "fa-solid fa-microphone-slash";
            }
        }
    }
}

function startAudioVisualizer() {
    if (audioInterval) clearInterval(audioInterval);
    
    const bars = document.querySelectorAll(".audio-bar");
    audioInterval = setInterval(() => {
        bars.forEach(bar => {
            if (micActive && cameraActive) {
                const height = Math.floor(Math.random() * 80) + 10;
                bar.style.height = `${height}%`;
            } else {
                bar.style.height = "10%";
            }
        });
    }, 120);
}

async function startInterviewSession() {
    const candInput = document.getElementById("candidate-id-input").value.trim();
    if (!candInput) {
        alert("Please enter a valid Candidate ID to continue.");
        return;
    }
    
    currentCandidateId = candInput;
    
    // Hide overlay
    document.getElementById("login-overlay").style.display = "none";
    
    // Initialize WebRTC Webcam & Mic
    await initWebcam();
    
    // Enforce camera is active
    if (!cameraActive) {
        alert("Camera is mandatory for this AI proctored screening. Please allow camera permissions and enable your camera to proceed.");
        cleanupSessionState();
        return;
    }
    
    // Establish real-time WebSocket connection
    const wsUrl = `${WS_BASE}/api/interviews/chat/${currentCandidateId}/${currentJobId}`;
    ws = new WebSocket(wsUrl);
    
    // Set up WebSocket events
    ws.onopen = () => {
        console.log("WebSocket secure screening room connected.");
        interviewActive = true;
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.error) {
            alert(`Error: ${data.error}`);
            cleanupSessionState();
            return;
        }
        
        // Handle Step transitions
        if (data.step) {
            updateStepProgressBar(data.step);
        }
        
        // Handle Character Streaming
        if (data.stream_start) {
            disableInput(true);
            showTypingIndicator(false);
            createAIBubble();
            
            // Cancel active speech and reset TTS tracking indices
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
            }
            spokenTextLength = 0;
        } else if (data.char) {
            appendAICharacter(data.char);
        } else if (data.stream_end) {
            disableInput(false);
            
            // Speak any trailing text fragment that didn't end with a sentence delimiter
            if (currentAIBubble) {
                const remainingText = currentAIBubble.textContent.substring(spokenTextLength).trim();
                if (remainingText) {
                    speakSentence(remainingText);
                }
            }
            currentAIBubble = null;
            
            // If final step wrap-up is reached, lock inputs permanently
            if (data.step === 4) {
                disableInput(true);
                // Close socket and stop tracks gracefully
                if (ws) {
                    ws.close();
                    ws = null;
                }
                if (localStream) {
                    localStream.getTracks().forEach(track => track.stop());
                    localStream = null;
                }
                if (audioInterval) clearInterval(audioInterval);
                
                // Add visual outcome card guiding back
                setTimeout(() => {
                    const chatStream = document.getElementById("chat-stream");
                    const notice = document.createElement("div");
                    notice.className = "glass-panel";
                    notice.style.padding = "20px";
                    notice.style.marginTop = "16px";
                    notice.style.textAlign = "center";
                    notice.style.borderColor = "rgba(16, 185, 129, 0.25)";
                    notice.style.background = "rgba(16, 185, 129, 0.03)";
                    notice.style.animation = "fadeIn 0.6s ease forwards";
                    
                    notice.innerHTML = `
                        <i class="fa-solid fa-circle-check" style="font-size: 2rem; color: #10b981; margin-bottom: 12px;"></i>
                        <h4 style="font-family: inherit; font-size: 1.05rem; font-weight: 700; color: #ffffff; margin-bottom: 6px;">Conversational Screening Completed!</h4>
                        <p style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 16px; line-height: 1.45;">
                            Your responses have been successfully compiled and analyzed by the AI Evaluation Engine.
                        </p>
                        <button onclick="window.location.href='/static/index.html'" class="btn-primary" style="padding: 10px 20px; font-size: 0.85rem; width: auto; font-family: inherit; display: inline-flex; align-items: center; gap: 8px; cursor: pointer; border-radius: 8px; border: none; font-weight: 600; background: linear-gradient(135deg, #7928ca, #0070f3); box-shadow: 0 4px 10px rgba(121, 40, 202, 0.3);">
                            <i class="fa-solid fa-arrow-left"></i> Return to Workspace Dashboard
                        </button>
                    `;
                    chatStream.appendChild(notice);
                    scrollChatBottom();
                }, 1000);
            }
        }
    };
    
    ws.onclose = (event) => {
        console.log("WebSocket screening room closed.", event.code);
        // If the connection closed abruptly or prematurely (not completed), recover UI
        if (ws !== null) {
            console.warn("WebSocket closed unexpectedly:", event);
            alert("Screening connection closed unexpectedly or failed. Please verify that the Candidate ID exists and the backend server is running.");
            cleanupSessionState();
        }
    };
    
    ws.onerror = (err) => {
        console.error("WebSocket encountered an error:", err);
        alert("WebSocket connection failed. The server might be down or Candidate ID invalid.");
        cleanupSessionState();
    };
}

function cleanupSessionState() {
    interviewActive = false;
    if (ws) {
        const tempWs = ws;
        ws = null; // Set to null first to avoid recursion in onclose!
        tempWs.close();
    }
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }
    if (audioInterval) {
        clearInterval(audioInterval);
        audioInterval = null;
    }
    
    // Stop any active AI speech
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
    
    // Clean up camera and telemetry UI state
    cameraActive = false;
    updateCameraUI();
    stopListening();
    
    // Restore input disabled state
    disableInput(true);
    
    // Return to the login overlay and show it again!
    document.getElementById("login-overlay").style.display = "flex";
}

function createAIBubble() {
    const chatStream = document.getElementById("chat-stream");
    
    const row = document.createElement("div");
    row.className = "chat-bubble-row ai";
    
    const avatar = document.createElement("div");
    avatar.className = "bubble-avatar";
    avatar.innerHTML = '<i class="fa-solid fa-robot" style="font-size: 0.75rem;"></i>';
    
    const bubble = document.createElement("div");
    bubble.className = "bubble-text";
    bubble.innerText = "";
    
    row.appendChild(avatar);
    row.appendChild(bubble);
    chatStream.appendChild(row);
    
    currentAIBubble = bubble;
    scrollChatBottom();
}

function appendAICharacter(char) {
    if (currentAIBubble) {
        currentAIBubble.textContent += char;
        scrollChatBottom();
        
        // Speak sentence in real-time
        speakNewSentences(currentAIBubble.textContent);
    }
}

function sendCandidateMessage() {
    stopListening();
    const textInput = document.getElementById("chat-text-input");
    const message = textInput.value.trim();
    
    if (!message || textInput.disabled) return;
    
    // Display client bubble
    renderCandidateBubble(message);
    
    // Send answer over WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(message);
    }
    
    textInput.value = "";
    disableInput(true);
    showTypingIndicator(true);
}

function renderCandidateBubble(text) {
    const chatStream = document.getElementById("chat-stream");
    
    const row = document.createElement("div");
    row.className = "chat-bubble-row candidate";
    
    const avatar = document.createElement("div");
    avatar.className = "bubble-avatar";
    avatar.innerHTML = '<i class="fa-solid fa-user" style="font-size: 0.75rem;"></i>';
    
    const bubble = document.createElement("div");
    bubble.className = "bubble-text";
    bubble.innerText = text;
    
    row.appendChild(avatar);
    row.appendChild(bubble);
    chatStream.appendChild(row);
    scrollChatBottom();
}

function updateStepProgressBar(step) {
    currentStepNum = step;
    const s1 = document.getElementById("step-segment-1");
    const s2 = document.getElementById("step-segment-2");
    const s3 = document.getElementById("step-segment-3");
    
    s1.classList.remove("active", "done");
    s2.classList.remove("active", "done");
    s3.classList.remove("active", "done");
    
    if (step === 1) {
        s1.classList.add("active");
    } else if (step === 2) {
        s1.classList.add("done");
        s1.innerHTML = '<i class="fa-solid fa-circle-check" style="margin-right: 4px;"></i> Step 1/3: Intro';
        s2.classList.add("active");
    } else if (step === 3) {
        s1.classList.add("done");
        s1.innerHTML = '<i class="fa-solid fa-circle-check" style="margin-right: 4px;"></i> Step 1/3: Intro';
        s2.classList.add("done");
        s2.innerHTML = '<i class="fa-solid fa-circle-check" style="margin-right: 4px;"></i> Step 2/3: Behavioral';
        s3.classList.add("active");
    } else if (step === 4) {
        s1.classList.add("done");
        s1.innerHTML = '<i class="fa-solid fa-circle-check" style="margin-right: 4px;"></i> Step 1/3: Intro';
        s2.classList.add("done");
        s2.innerHTML = '<i class="fa-solid fa-circle-check" style="margin-right: 4px;"></i> Step 2/3: Behavioral';
        s3.classList.add("done");
        s3.innerHTML = '<i class="fa-solid fa-circle-check" style="margin-right: 4px;"></i> Step 3/3: Technical';
    }
}

function disableInput(disabled) {
    const textInput = document.getElementById("chat-text-input");
    const sendBtn = document.getElementById("chat-send-btn");
    const micBtn = document.getElementById("chat-mic-btn");
    
    // Force disabled if camera is mandatory and inactive
    const forceDisabled = disabled || !cameraActive;
    
    if (textInput) textInput.disabled = forceDisabled;
    if (sendBtn) sendBtn.disabled = forceDisabled;
    if (micBtn) {
        micBtn.disabled = forceDisabled;
        if (forceDisabled) {
            stopListening();
        }
    }
    
    if (!forceDisabled && textInput) {
        textInput.focus();
    }
}

function showTypingIndicator(show) {
    const indicator = document.getElementById("ai-typing-bar");
    indicator.style.display = show ? "block" : "none";
    scrollChatBottom();
}

function scrollChatBottom() {
    const chatStream = document.getElementById("chat-stream");
    chatStream.scrollTop = chatStream.scrollHeight;
}

function updateCameraUI() {
    const videoElement = document.getElementById("webcam-stream");
    const fallbackElement = document.getElementById("webcam-fallback");
    const toggleCamBtn = document.getElementById("toggle-camera-btn");
    const faceScanner = document.getElementById("face-scanner");
    const biometricCanvas = document.getElementById("biometric-canvas");
    const telemetryBoard = document.getElementById("telemetry-board");
    const chatTextInput = document.getElementById("chat-text-input");
    const chatSendBtn = document.getElementById("chat-send-btn");
    const chatMicBtn = document.getElementById("chat-mic-btn");

    if (cameraActive) {
        if (videoElement && localStream) videoElement.srcObject = localStream;
        if (fallbackElement) fallbackElement.style.display = "none";
        if (faceScanner) faceScanner.style.opacity = "1";
        if (toggleCamBtn) {
            toggleCamBtn.classList.add("active");
            toggleCamBtn.querySelector("i").className = "fa-solid fa-video";
        }
        if (biometricCanvas) biometricCanvas.style.display = "block";
        if (telemetryBoard) telemetryBoard.style.display = "grid";
        
        // Remove the block overlay if it exists
        const overlay = document.getElementById("camera-required-overlay");
        if (overlay) overlay.remove();
        
        // Enable input if AI is not currently speaking
        if (ws && ws.readyState === WebSocket.OPEN && !currentAIBubble) {
            disableInput(false);
        }
        
        startBiometricTracking();
    } else {
        if (videoElement) videoElement.srcObject = null;
        if (fallbackElement) fallbackElement.style.display = "flex";
        if (faceScanner) faceScanner.style.opacity = "0.3";
        if (toggleCamBtn) {
            toggleCamBtn.classList.remove("active");
            toggleCamBtn.querySelector("i").className = "fa-solid fa-video-slash";
        }
        if (biometricCanvas) biometricCanvas.style.display = "none";
        if (telemetryBoard) telemetryBoard.style.display = "none";
        
        stopBiometricTracking();
        stopListening();
        
        // If the interview is already started (WebSocket exists)
        if (ws && ws.readyState === WebSocket.OPEN) {
            // Disable inputs
            if (chatTextInput) chatTextInput.disabled = true;
            if (chatSendBtn) chatSendBtn.disabled = true;
            if (chatMicBtn) chatMicBtn.disabled = true;
            
            // Show floating warning overlay over chat display
            const chatStream = document.getElementById("chat-stream");
            if (chatStream && !document.getElementById("camera-required-overlay")) {
                const overlay = document.createElement("div");
                overlay.id = "camera-required-overlay";
                overlay.className = "glass-panel";
                overlay.style.padding = "20px";
                overlay.style.margin = "16px auto";
                overlay.style.textAlign = "center";
                overlay.style.borderColor = "rgba(239, 68, 68, 0.4)";
                overlay.style.background = "rgba(239, 68, 68, 0.1)";
                overlay.style.color = "#ffffff";
                overlay.style.zIndex = "100";
                overlay.style.position = "sticky";
                overlay.style.top = "50%";
                overlay.style.transform = "translateY(-50%)";
                overlay.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.5)";
                
                overlay.innerHTML = `
                    <i class="fa-solid fa-camera-rotate" style="font-size: 2.2rem; color: #ef4444; margin-bottom: 12px; animation: pulse-glow 1.5s infinite;"></i>
                    <h4 style="font-size: 1.05rem; font-weight: 700; margin: 0 0 6px 0;">Camera Feed Required</h4>
                    <p style="font-size: 0.8rem; color: #d1d5db; margin: 0; line-height: 1.45;">
                        This screening session is fully AI proctored. You must enable your camera to continue the interview.
                    </p>
                `;
                chatStream.appendChild(overlay);
                scrollChatBottom();
            }
        }
    }
}

let biometricAnimationId = null;
let telemetryInterval = null;

function startBiometricTracking() {
    const canvas = document.getElementById("biometric-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    
    stopBiometricTracking();
    
    // Setup canvas dimensions
    const resizeCanvas = () => {
        const container = canvas.parentElement;
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
    };
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
    
    // Landmarks configuration (base positions as percentages of canvas width/height)
    const baseLandmarks = {
        leftEye: [ {x:0.42, y:0.42}, {x:0.45, y:0.41}, {x:0.48, y:0.42}, {x:0.45, y:0.43} ],
        rightEye: [ {x:0.52, y:0.42}, {x:0.55, y:0.41}, {x:0.58, y:0.42}, {x:0.55, y:0.43} ],
        nose: [ {x:0.5, y:0.45}, {x:0.5, y:0.52}, {x:0.47, y:0.54}, {x:0.5, y:0.55}, {x:0.53, y:0.54} ],
        leftEyebrow: [ {x:0.39, y:0.38}, {x:0.43, y:0.36}, {x:0.47, y:0.37} ],
        rightEyebrow: [ {x:0.53, y:0.37}, {x:0.57, y:0.36}, {x:0.61, y:0.38} ],
        mouthOuter: [ {x:0.44, y:0.63}, {x:0.47, y:0.61}, {x:0.5, y:0.62}, {x:0.53, y:0.61}, {x:0.56, y:0.63}, {x:0.53, y:0.66}, {x:0.5, y:0.67}, {x:0.47, y:0.66} ],
        jawline: [ {x:0.36, y:0.42}, {x:0.37, y:0.5}, {x:0.39, y:0.58}, {x:0.42, y:0.66}, {x:0.46, y:0.73}, {x:0.5, y:0.76}, {x:0.54, y:0.73}, {x:0.58, y:0.66}, {x:0.61, y:0.58}, {x:0.63, y:0.5}, {x:0.64, y:0.42} ]
    };
    
    let time = 0;
    
    const draw = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        time += 0.05;
        const w = canvas.width;
        const h = canvas.height;
        
        ctx.fillStyle = "rgba(0, 223, 216, 0.75)";
        ctx.strokeStyle = "rgba(0, 223, 216, 0.25)";
        ctx.lineWidth = 1;
        
        // Collect all points mapped to current canvas dimensions with simulated motion noise
        const mappedFeatures = {};
        
        // Speech/voice amplitude mapping for mouth animation
        const speakingAmplitude = isListening ? (Math.sin(time * 5) * 8 + 8) : 0;
        
        for (const [featureName, points] of Object.entries(baseLandmarks)) {
            mappedFeatures[featureName] = points.map(pt => {
                // Calculate slight noise jitter
                const jitterX = Math.sin(time + pt.x * 100) * 2;
                const jitterY = Math.cos(time + pt.y * 100) * 2;
                
                let x = pt.x * w + jitterX;
                let y = pt.y * h + jitterY;
                
                // Dynamic mouth scaling when speaking
                if (featureName === "mouthOuter") {
                    const deltaY = (pt.y - 0.64) * speakingAmplitude;
                    y += deltaY;
                }
                
                return { x, y };
            });
        }
        
        // Draw connections and landmark nodes
        for (const [featureName, points] of Object.entries(mappedFeatures)) {
            // Draw polygon line connections
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x, points[i].y);
            }
            if (featureName === "leftEye" || featureName === "rightEye" || featureName === "mouthOuter") {
                ctx.closePath();
            }
            ctx.stroke();
            
            // Draw landmark dot nodes
            points.forEach(pt => {
                ctx.beginPath();
                ctx.arc(pt.x, pt.y, 2, 0, Math.PI * 2);
                ctx.fill();
            });
        }
        
        // Draw crosshair tracking target
        ctx.strokeStyle = "rgba(0, 223, 216, 0.15)";
        ctx.beginPath();
        ctx.arc(w/2, h/2, Math.min(w, h)*0.25, 0, Math.PI * 2);
        ctx.stroke();
        
        biometricAnimationId = requestAnimationFrame(draw);
    };
    
    biometricAnimationId = requestAnimationFrame(draw);
    
    // Fluctuate telemetry board values realistically
    const expressions = ["Attentive", "Focused", "Attentive", "Focused", "Attentive"];
    const gazes = ["Center", "Center", "Left", "Center", "Right"];
    
    telemetryInterval = setInterval(() => {
        const telemetryExpr = document.getElementById("telemetry-expression");
        const telemetryGaze = document.getElementById("telemetry-gaze");
        const telemetryEngagement = document.getElementById("telemetry-engagement");
        const telemetryHR = document.getElementById("telemetry-hr");
        
        if (telemetryExpr) {
            if (isListening) {
                telemetryExpr.innerText = "Speaking";
                telemetryExpr.style.color = "#ef4444";
            } else {
                const randExpr = expressions[Math.floor(Math.random() * expressions.length)];
                telemetryExpr.innerText = randExpr;
                telemetryExpr.style.color = "#00dfd8";
            }
        }
        if (telemetryGaze) {
            const randGaze = gazes[Math.floor(Math.random() * gazes.length)];
            telemetryGaze.innerText = randGaze;
            if (randGaze === "Center") {
                telemetryGaze.style.color = "#3b82f6";
            } else {
                telemetryGaze.style.color = "#f59e0b"; // Warning amber if looking away
            }
        }
        if (telemetryEngagement) {
            const score = Math.floor(Math.random() * 5) + 94; // 94% - 98%
            telemetryEngagement.innerText = `${score}%`;
        }
        if (telemetryHR) {
            const hr = Math.floor(Math.random() * 10) + 70; // 70-80 BPM
            telemetryHR.innerText = `${hr} BPM`;
        }
    }, 2000);
}

function stopBiometricTracking() {
    if (biometricAnimationId) {
        cancelAnimationFrame(biometricAnimationId);
        biometricAnimationId = null;
    }
    if (telemetryInterval) {
        clearInterval(telemetryInterval);
        telemetryInterval = null;
    }
}

let recognition = null;
let isListening = false;

function initSpeechRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        console.warn("Speech recognition not supported in this browser.");
        return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true; 
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        isListening = true;
        updateSpeechButtonState();
    };

    recognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                transcript += event.results[i][0].transcript;
            }
        }
        const inputField = document.getElementById("chat-text-input");
        if (transcript && inputField) {
            inputField.value += (inputField.value ? ' ' : '') + transcript;
            // Dispatch input event so that text area resizing / auto-height works
            inputField.dispatchEvent(new Event('input', { bubbles: true }));
        }
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        if (event.error === 'no-speech') {
            console.log("No speech was detected. Continuing to listen...");
            return;
        }
        if (event.error === 'aborted') {
            console.log("Speech recognition aborted.");
            return;
        }
        
        if (event.error === 'not-allowed') {
            alert("Microphone permission was denied. Please allow microphone permissions in your browser's site settings to use speech-to-text.");
        } else if (event.error === 'network') {
            alert("Speech recognition network error: Google voice service could not be reached. Please check your internet connection or type your response.");
        } else {
            alert("Voice input error: " + event.error);
        }
        stopListening();
    };

    recognition.onend = () => {
        // Auto-restart if we are still supposed to be listening (e.g. didn't call stopListening)
        if (isListening) {
            try {
                recognition.start();
            } catch (e) {
                console.error("Failed to restart speech recognition:", e);
                isListening = false;
                updateSpeechButtonState();
            }
        } else {
            updateSpeechButtonState();
        }
    };
}

function toggleSpeechRecognition() {
    if (!recognition) {
        initSpeechRecognition();
    }
    if (!recognition) {
        alert("Speech recognition is not supported in this browser. Please type your answer.");
        return;
    }
    if (isListening) {
        stopListening();
    } else {
        isListening = true;
        try {
            recognition.start();
        } catch (e) {
            console.error("Failed to start speech recognition:", e);
            isListening = false;
            updateSpeechButtonState();
        }
    }
}

function stopListening() {
    isListening = false;
    if (recognition) {
        try {
            recognition.stop();
        } catch (e) {
            console.error("Error stopping recognition:", e);
        }
    }
    updateSpeechButtonState();
}

function updateSpeechButtonState() {
    const micBtn = document.getElementById("chat-mic-btn");
    if (!micBtn) return;
    if (isListening) {
        micBtn.style.background = "linear-gradient(135deg, #ef4444, #b91c1c)";
        micBtn.style.color = "#ffffff";
        micBtn.innerHTML = '<i class="fa-solid fa-microphone-lines" style="animation: pulse-glow 1.5s infinite ease-in-out;"></i>';
    } else {
        micBtn.style.background = "rgba(255, 255, 255, 0.05)";
        micBtn.style.color = "rgba(255, 255, 255, 0.7)";
        micBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    }
}

function simulateNextDemoStep() {
    const inputField = document.getElementById("chat-text-input");
    if (!inputField || inputField.disabled) {
        alert("Please wait until the AI finishes speaking before auto-filling the next answer.");
        return;
    }
    
    let answer = "";
    if (currentStepNum === 1) {
        if (step1Clicks === 0) {
            answer = "Hi, my name is Sania and I am currently working as a junior backend engineer.";
            step1Clicks++;
        } else {
            answer = "I graduated with a Bachelor's degree in Computer Science. My main technical skills are Python, FastAPI, and PostgreSQL. I have built freelance web application projects and a candidates screening pipeline. I hold an Oracle database certification. I am excited about the AI Recruiter project because of its automated evaluations, and I am looking for a role to contribute my skills and grow as an engineer.";
        }
    } else if (currentStepNum === 2) {
        answer = "In my last team project, we encountered a severe database deadlock under high user traffic. I resolved it by refactoring the database transactions, introducing SQL indexes on foreign keys, and adjusting connection pool timeouts.";
    } else if (currentStepNum === 3) {
        answer = "I would design a distributed systems architecture using FastAPI for API endpoints, Redis to cache active rankings, PostgreSQL for transactional database schemas, and Celery with RabbitMQ to process background tasks.";
    } else {
        alert("The conversational screening is already completed!");
        return;
    }
    
    // Disable send/input during typing animation
    inputField.disabled = true;
    const sendBtn = document.getElementById("chat-send-btn");
    if (sendBtn) sendBtn.disabled = true;
    
    // Animate typing into the textarea
    inputField.value = "";
    let index = 0;
    
    // Temporarily disable mic while auto-typing
    stopListening();
    
    const typingInterval = setInterval(() => {
        if (index < answer.length) {
            inputField.value += answer[index];
            index++;
        } else {
            clearInterval(typingInterval);
            inputField.disabled = false;
            if (sendBtn) sendBtn.disabled = false;
            // Submit the response after a short delay
            setTimeout(() => {
                sendCandidateMessage();
            }, 600);
        }
    }, 12);
}
