// ==========================================================================
// RESEARCHMIND-AI - FRONTEND STATE & API ENGINE
// ==========================================================================

const API_BASE = "http://127.0.0.1:8000/api/v1";

// 1. Application State
const state = {
    token: localStorage.getItem("token") || null,
    user: null,
    projects: [],
    activeProjectId: null,
    documents: [],
    activeDocForChat: null,
    pollingIntervals: {}
};

// 2. DOM Elements
const el = {
    appLoader: document.getElementById("app-loader"),
    authContainer: document.getElementById("auth-container"),
    appContainer: document.getElementById("app-container"),
    loginForm: document.getElementById("login-form"),
    registerForm: document.getElementById("register-form"),
    loginEmail: document.getElementById("login-email"),
    loginPass: document.getElementById("login-password"),
    registerEmail: document.getElementById("register-email"),
    registerPass: document.getElementById("register-password"),
    toggleToReg: document.getElementById("toggle-to-register"),
    toggleToLogin: document.getElementById("toggle-to-login"),
    currentUserEmail: document.getElementById("current-user-email"),
    btnLogout: document.getElementById("btn-logout"),
    btnWelcomeCreateProj: document.getElementById("btn-welcome-create-project"),
    btnOpenCreateProj: document.getElementById("btn-open-create-project"),
    
    // Project View
    welcomeView: document.getElementById("welcome-view"),
    projectView: document.getElementById("project-view"),
    activeProjectTitle: document.getElementById("active-project-title"),
    activeProjectDesc: document.getElementById("active-project-desc"),
    activeProjectTags: document.getElementById("active-project-tags"),
    projectsListContainer: document.getElementById("projects-list-container"),
    
    // Document Upload & List
    uploadZone: document.getElementById("upload-zone"),
    fileInput: document.getElementById("file-input"),
    uploadProgressBar: document.getElementById("upload-progress-bar"),
    documentsListContainer: document.getElementById("documents-list-container"),
    
    // Chat pane
    chatActiveDoc: document.getElementById("chat-active-document"),
    chatDocName: document.getElementById("chat-doc-name"),
    chatEmptyState: document.getElementById("chat-empty-state"),
    chatWorkspace: document.getElementById("chat-workspace"),
    chatMessagesContainer: document.getElementById("chat-messages-container"),
    chatInputForm: document.getElementById("chat-input-form"),
    chatQueryInput: document.getElementById("chat-query-input"),
    btnSendQuery: document.getElementById("btn-send-query"),
    
    // Modals
    createProjectModal: document.getElementById("create-project-modal"),
    createProjectForm: document.getElementById("create-project-form"),
    projectTitleInput: document.getElementById("project-title"),
    projectDescInput: document.getElementById("project-desc"),
    projectTagsInput: document.getElementById("project-tags"),
    btnCloseModal: document.getElementById("btn-close-project-modal"),
    btnCancelModal: document.getElementById("btn-cancel-project-modal")
};

// 3. API Fetch Wrapper
async function apiCall(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    
    // Default headers
    options.headers = options.headers || {};
    if (state.token) {
        options.headers["Authorization"] = `Bearer ${state.token}`;
    }
    
    // Auto JSON content-type if body is object and not FormData or URLSearchParams
    if (options.body && !(options.body instanceof FormData) && !(options.body instanceof URLSearchParams) && typeof options.body === "object") {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(options.body);
    }
    
    try {
        const response = await fetch(url, options);
        
        if (response.status === 401) {
            // Unauthorized - clean up session
            handleLogout();
            throw new Error("Session expired. Please log in again.");
        }
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `API request failed with status ${response.status}`);
        }
        
        if (response.status === 204) {
            return null;
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API Error [${endpoint}]:`, error);
        throw error;
    }
}

// 4. Session & Authentication Logic
async function checkAuth() {
    if (!state.token) {
        showAuthScreen();
        return;
    }
    
    try {
        const user = await apiCall("/auth/me");
        state.user = user;
        el.currentUserEmail.textContent = user.email;
        showAppScreen();
        await loadProjects();
    } catch (error) {
        showAuthScreen();
    }
}

function showAuthScreen() {
    el.appLoader.classList.add("hidden");
    el.appContainer.classList.add("hidden");
    el.authContainer.classList.remove("hidden");
}

function showAppScreen() {
    el.appLoader.classList.add("hidden");
    el.authContainer.classList.add("hidden");
    el.appContainer.classList.remove("hidden");
}

function handleLogout() {
    state.token = null;
    state.user = null;
    state.projects = [];
    state.activeProjectId = null;
    state.documents = [];
    state.activeDocForChat = null;
    
    // Clear all status polling intervals
    Object.values(state.pollingIntervals).forEach(clearInterval);
    state.pollingIntervals = {};
    
    localStorage.removeItem("token");
    showAuthScreen();
}

// 5. Auth Event Listeners
el.toggleToReg.addEventListener("click", (e) => {
    e.preventDefault();
    el.loginForm.classList.add("hidden");
    el.registerForm.classList.remove("hidden");
    document.querySelector(".auth-header h2").textContent = "Create Account";
    document.getElementById("auth-subtitle").textContent = "Register a new research workspace";
});

el.toggleToLogin.addEventListener("click", (e) => {
    e.preventDefault();
    el.registerForm.classList.add("hidden");
    el.loginForm.classList.remove("hidden");
    document.querySelector(".auth-header h2").textContent = "Welcome Back";
    document.getElementById("auth-subtitle").textContent = "Sign in to your research workspace";
});

el.loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = el.loginEmail.value;
    const password = el.loginPass.value;
    
    try {
        // OAuth2 Password Grant Form format
        const body = new URLSearchParams();
        body.append("username", email);
        body.append("password", password);
        
        const data = await apiCall("/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: body
        });
        
        state.token = data.access_token;
        localStorage.setItem("token", data.access_token);
        el.loginEmail.value = "";
        el.loginPass.value = "";
        await checkAuth();
    } catch (error) {
        alert(`Login failed: ${error.message}`);
    }
});

el.registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = el.registerEmail.value;
    const password = el.registerPass.value;
    
    try {
        await apiCall("/auth/register", {
            method: "POST",
            body: { email, password }
        });
        alert("Registration successful! You can now sign in.");
        el.toggleToLogin.click();
        el.loginEmail.value = email;
    } catch (error) {
        alert(`Registration failed: ${error.message}`);
    }
});

el.btnLogout.addEventListener("click", (e) => {
    e.preventDefault();
    handleLogout();
});

// 6. Project Management Actions
async function loadProjects() {
    try {
        const data = await apiCall("/projects/");
        state.projects = data;
        renderProjectsList();
    } catch (error) {
        console.error("Failed to load projects:", error);
    }
}

function renderProjectsList() {
    el.projectsListContainer.innerHTML = "";
    if (state.projects.length === 0) {
        el.projectsListContainer.innerHTML = `<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; padding:10px;">No projects created.</div>`;
        return;
    }
    
    state.projects.forEach(proj => {
        const projId = proj._id || proj.id;
        const tab = document.createElement("div");
        tab.className = `project-tab ${state.activeProjectId === projId ? "active" : ""}`;
        tab.dataset.id = projId;
        
        tab.innerHTML = `
            <div class="project-tab-left">
                <i class="fa-solid fa-folder-closed project-tab-icon"></i>
                <span class="project-tab-name">${proj.title}</span>
            </div>
            <i class="fa-solid fa-trash btn-delete-project" title="Delete Project"></i>
        `;
        
        // Open Project on Tab click (excluding the delete button click)
        tab.addEventListener("click", (e) => {
            if (e.target.classList.contains("btn-delete-project")) {
                e.stopPropagation();
                deleteProject(projId);
            } else {
                selectProject(projId);
            }
        });
        
        el.projectsListContainer.appendChild(tab);
    });
}

async function selectProject(projectId) {
    state.activeProjectId = projectId;
    renderProjectsList();
    
    try {
        // Clear chat state when switching projects
        closeChatWorkspace();
    } catch (err) {
        console.error("Error closing chat workspace:", err);
    }
    
    try {
        const proj = state.projects.find(p => String(p._id || p.id) === String(projectId));
        if (!proj) {
            console.error(`Project with ID ${projectId} not found in state.`);
            return;
        }
        el.activeProjectTitle.textContent = proj.title;
        el.activeProjectDesc.textContent = proj.description || "No description provided.";

        
        // Render tags
        el.activeProjectTags.innerHTML = "";
        if (proj.tags && proj.tags.length > 0) {
            proj.tags.forEach(tag => {
                const tagEl = document.createElement("span");
                tagEl.className = "tag-pill";
                tagEl.textContent = tag;
                el.activeProjectTags.appendChild(tagEl);
            });
        }
        
        // Swap workspace panels
        el.welcomeView.classList.add("hidden");
        el.projectView.classList.remove("hidden");
        
        // Load documents mapping to this project
        await loadDocuments();
    } catch (error) {
        console.error("Failed to select project:", error);
    }
}

async function createProject(title, description, tagsString) {
    const tags = tagsString ? tagsString.split(",").map(t => t.trim()).filter(t => t.length > 0) : [];
    
    try {
        const newProj = await apiCall("/projects/", {
            method: "POST",
            body: { title, description, tags }
        });
        
        await loadProjects();
        closeProjectModal();
        selectProject(newProj._id || newProj.id);
    } catch (error) {
        alert(`Failed to create project: ${error.message}`);
    }
}

async function deleteProject(projectId) {
    if (!confirm("Are you sure you want to delete this project? All associated documents will remain in the database but the project wrapper will be removed.")) return;
    
    try {
        await apiCall(`/projects/${projectId}`, {
            method: "DELETE"
        });
        
        if (state.activeProjectId === projectId) {
            state.activeProjectId = null;
            el.projectView.classList.add("hidden");
            el.welcomeView.classList.remove("hidden");
        }
        
        await loadProjects();
    } catch (error) {
        alert(`Failed to delete project: ${error.message}`);
    }
}

// Project Modal Triggers
function openProjectModal() { el.createProjectModal.classList.remove("hidden"); }
function closeProjectModal() {
    el.createProjectModal.classList.add("hidden");
    el.createProjectForm.reset();
}
el.btnWelcomeCreateProj.addEventListener("click", openProjectModal);
el.btnOpenCreateProj.addEventListener("click", openProjectModal);
el.btnCloseModal.addEventListener("click", closeProjectModal);
el.btnCancelModal.addEventListener("click", closeProjectModal);

el.createProjectForm.addEventListener("submit", (e) => {
    e.preventDefault();
    createProject(
        el.projectTitleInput.value,
        el.projectDescInput.value,
        el.projectTagsInput.value
    );
});

// 7. Document Management Logic
async function loadDocuments() {
    if (!state.activeProjectId) return;
    
    try {
        const docs = await apiCall(`/documents/project/${state.activeProjectId}`);
        state.documents = docs;
        renderDocumentsList();
    } catch (error) {
        console.error("Failed to load documents:", error);
    }
}

function renderDocumentsList() {
    el.documentsListContainer.innerHTML = "";
    
    if (state.documents.length === 0) {
        el.documentsListContainer.innerHTML = `
            <div style="color:var(--text-muted); font-size:0.85rem; text-align:center; padding:30px;">
                No research papers uploaded yet. Drag a PDF here!
            </div>
        `;
        return;
    }
    
    state.documents.forEach(doc => {
        const docId = String(doc._id || doc.id);
        const activeDocId = state.activeDocForChat ? String(state.activeDocForChat._id || state.activeDocForChat.id) : null;
        const card = document.createElement("div");
        card.className = `doc-item-card ${activeDocId === docId ? "active" : ""}`;
        card.dataset.id = docId;
        
        // Map status classes
        let statusClass = "status-uploaded";
        let statusIcon = '<i class="fa-solid fa-file-arrow-up"></i>';
        if (doc.status === "processing") {
            statusClass = "status-processing";
            statusIcon = '<span class="spinner-mini"></span>';
            
            // Auto start polling for this document if not already running
            startStatusPolling(docId);
        } else if (doc.status === "indexed") {
            statusClass = "status-indexed";
            statusIcon = '<i class="fa-solid fa-circle-check"></i>';
        } else if (doc.status === "failed") {
            statusClass = "status-failed";
            statusIcon = '<i class="fa-solid fa-circle-exclamation"></i>';
        }
        
        // Convert file size
        const kbSize = doc.file_size ? `${(doc.file_size / 1024).toFixed(1)} KB` : "Unknown Size";
        
        card.innerHTML = `
            <div class="doc-item-left">
                <i class="fa-regular fa-file-pdf doc-item-icon"></i>
                <div class="doc-item-details">
                    <span class="doc-item-name" title="${doc.filename}">${doc.filename}</span>
                    <div class="doc-item-meta">
                        <span>${kbSize}</span>
                        <span class="status-badge ${statusClass}">${statusIcon} ${doc.status}</span>
                    </div>
                </div>
            </div>
            <div class="doc-item-actions">
                ${doc.status === "uploaded" || doc.status === "failed" ? `
                    <button class="btn-doc-action btn-doc-action-process" title="Ingest & Extract Metadata (Phase 4 & 5)">
                        <i class="fa-solid fa-gears"></i>
                    </button>
                ` : ""}
                ${doc.status === "indexed" ? `
                    <button class="btn-doc-action btn-doc-action-chat" title="Chat with Assistant (Phase 6)">
                        <i class="fa-solid fa-comments"></i>
                    </button>
                ` : ""}
                <button class="btn-doc-action btn-doc-action-delete" title="Delete Document">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        `;
        
        // Wire up doc actions
        const btnProcess = card.querySelector(".btn-doc-action-process");
        const btnChat = card.querySelector(".btn-doc-action-chat");
        const btnDelete = card.querySelector(".btn-doc-action-delete");
        
        if (btnProcess) {
            btnProcess.addEventListener("click", () => processDocument(docId));
        }
        if (btnChat) {
            btnChat.addEventListener("click", () => startChatWithDoc(doc));
        }
        btnDelete.addEventListener("click", () => deleteDocument(docId));
        
        el.documentsListContainer.appendChild(card);
    });
}

// Drag & Drop Handlers
el.uploadZone.addEventListener("click", () => el.fileInput.click());
el.uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    el.uploadZone.classList.add("dragover");
});
el.uploadZone.addEventListener("dragleave", () => el.uploadZone.classList.remove("dragover"));
el.uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    el.uploadZone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
});
el.fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) handleUpload(file);
});

async function handleUpload(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
        alert("Only PDF files are supported!");
        return;
    }
    
    const formData = new FormData();
    formData.append("file", file);
    
    // Show progress bar
    el.uploadProgressBar.classList.remove("hidden");
    const fill = el.uploadProgressBar.querySelector(".progress-bar-fill");
    fill.style.width = "40%";
    
    try {
        await apiCall(`/documents/upload?project_id=${state.activeProjectId}`, {
            method: "POST",
            body: formData
        });
        
        fill.style.width = "100%";
        setTimeout(() => {
            el.uploadProgressBar.classList.add("hidden");
            fill.style.width = "0%";
        }, 800);
        
        await loadDocuments();
    } catch (error) {
        el.uploadProgressBar.classList.add("hidden");
        alert(`Upload failed: ${error.message}`);
    }
}

async function processDocument(docId) {
    try {
        // Optimistic UI updates
        const doc = state.documents.find(d => (d._id || d.id) === docId);
        if (doc) doc.status = "processing";
        renderDocumentsList();
        
        await apiCall(`/documents/${docId}/process`, { method: "POST" });
        startStatusPolling(docId);
    } catch (error) {
        alert(`Failed to trigger document processing: ${error.message}`);
        await loadDocuments();
    }
}

function startStatusPolling(docId) {
    if (state.pollingIntervals[docId]) return;
    
    state.pollingIntervals[docId] = setInterval(async () => {
        try {
            const updatedDoc = await apiCall(`/documents/${docId}`);
            
            // Check if status changed
            const cachedIndex = state.documents.findIndex(d => (d._id || d.id) === docId);
            if (cachedIndex !== -1) {
                state.documents[cachedIndex].status = updatedDoc.status;
            }
            
            if (updatedDoc.status === "indexed" || updatedDoc.status === "failed") {
                clearInterval(state.pollingIntervals[docId]);
                delete state.pollingIntervals[docId];
                await loadDocuments(); // full refresh
            } else {
                renderDocumentsList();
            }
        } catch (error) {
            console.error("Error polling doc status:", error);
            clearInterval(state.pollingIntervals[docId]);
            delete state.pollingIntervals[docId];
        }
    }, 3000);
}

async function deleteDocument(docId) {
    if (!confirm("Are you sure you want to delete this PDF? All extracted text chunks and vector embeddings will be permanently deleted from MongoDB and Qdrant.")) return;
    
    try {
        // Clear active chat if this doc is active
        const activeDocId = state.activeDocForChat?._id || state.activeDocForChat?.id;
        if (activeDocId === docId) {
            closeChatWorkspace();
        }
        
        // Stop polling if active
        if (state.pollingIntervals[docId]) {
            clearInterval(state.pollingIntervals[docId]);
            delete state.pollingIntervals[docId];
        }
        
        await apiCall(`/documents/${docId}`, { method: "DELETE" });
        await loadDocuments();
    } catch (error) {
        alert(`Failed to delete document: ${error.message}`);
    }
}

// 8. RAG Chat Assistant Interface Logic
function startChatWithDoc(doc) {
    state.activeDocForChat = doc;
    renderDocumentsList(); // update active styling
    
    // Configure header
    el.chatDocName.textContent = doc.filename;
    el.chatActiveDoc.classList.remove("hidden");
    
    // Show tab bar
    document.getElementById("pane-tabs-bar").classList.remove("hidden");
    
    // Switch to Chat Q&A tab by default
    switchTab("chat-tab");
    
    // Swap panels
    el.chatEmptyState.classList.add("hidden");
    
    // Clear chat history
    el.chatMessagesContainer.innerHTML = "";
    
    // Welcome chat prompt
    appendChatMessage("assistant", `Hi! I've fully processed and indexed **${doc.filename}**. What would you like to know about it? I'll answer based on its contents and cite exact page sources.`);
    
    // Load Compare Paper Dropdown
    loadComparePaperDropdown();
}

function closeChatWorkspace() {
    state.activeDocForChat = null;
    el.chatActiveDoc.classList.add("hidden");
    document.getElementById("pane-tabs-bar").classList.add("hidden");
    
    // Hide all tab panels and show empty state
    document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
    el.chatEmptyState.classList.remove("hidden");
    
    // Clear any results
    document.getElementById("tool-result-box").classList.add("hidden");
    document.getElementById("project-result-box").classList.add("hidden");
}


function appendChatMessage(sender, text, citations = []) {
    const msg = document.createElement("div");
    msg.className = `chat-msg ${sender === "user" ? "chat-msg-user" : "chat-msg-bot"}`;
    
    const avatarIcon = sender === "user" ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';
    
    // Render markdown bold text helper
    const formattedText = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
        
    let citationsHtml = "";
    if (citations && citations.length > 0) {
        citationsHtml = `
            <div class="sources-title"><i class="fa-solid fa-quote-left"></i> Source Citations</div>
            <div class="citations-list">
        `;
        
        citations.forEach((cit, idx) => {
            citationsHtml += `
                <div class="citation-card" onclick="this.classList.toggle('expanded')">
                    <div class="citation-meta">
                        <span>Source #${idx + 1} &bull; Page ${cit.page} &bull; ${cit.section}</span>
                        <span class="citation-doc-source">${cit.author || "Unknown"} (${cit.year || "n/a"})</span>
                    </div>
                    <div class="citation-snippet">"${cit.snippet}"</div>
                </div>
            `;
        });
        
        citationsHtml += "</div>";
    }
    
    msg.innerHTML = `
        <div class="chat-msg-avatar">${avatarIcon}</div>
        <div class="chat-msg-body">
            <div class="chat-msg-bubble">${formattedText}</div>
            ${citationsHtml}
        </div>
    `;
    
    el.chatMessagesContainer.appendChild(msg);
    el.chatMessagesContainer.scrollTop = el.chatMessagesContainer.scrollHeight;
}

function appendTypingIndicator() {
    const indicator = document.createElement("div");
    indicator.className = "chat-msg chat-msg-bot";
    indicator.id = "typing-indicator-node";
    indicator.innerHTML = `
        <div class="chat-msg-avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="chat-msg-body">
            <div class="chat-msg-bubble">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    el.chatMessagesContainer.appendChild(indicator);
    el.chatMessagesContainer.scrollTop = el.chatMessagesContainer.scrollHeight;
}

function removeTypingIndicator() {
    const node = document.getElementById("typing-indicator-node");
    if (node) node.remove();
}

function appendEmptyAssistantMessage() {
    const msg = document.createElement("div");
    msg.className = "chat-msg chat-msg-bot";
    msg.innerHTML = `
        <div class="chat-msg-avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="chat-msg-body">
            <div class="chat-status-indicator" style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 6px; font-style: italic; display: flex; align-items: center; gap: 6px;">
                <span class="spinner-mini"></span>
                <span class="status-text">Initializing agent specialists planner...</span>
            </div>
            <div class="chat-msg-bubble">
                <div class="chat-msg-bubble-text"></div>
            </div>
        </div>
    `;
    el.chatMessagesContainer.appendChild(msg);
    el.chatMessagesContainer.scrollTop = el.chatMessagesContainer.scrollHeight;
    return msg;
}

el.chatInputForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = el.chatQueryInput.value.trim();
    if (!query || !state.activeDocForChat) return;
    
    el.chatQueryInput.value = "";
    appendChatMessage("user", query);
    appendTypingIndicator();
    
    try {
        const activeDocId = String(state.activeDocForChat._id || state.activeDocForChat.id);
        const token = state.token || localStorage.getItem("token");
        
        const response = await fetch(`${API_BASE}/documents/${activeDocId}/query`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ question: query })
        });
        
        removeTypingIndicator();
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to query document");
        }
        
        const assistantMsgEl = appendEmptyAssistantMessage();
        const statusEl = assistantMsgEl.querySelector(".chat-status-indicator");
        const statusTextEl = assistantMsgEl.querySelector(".status-text");
        const bubbleEl = assistantMsgEl.querySelector(".chat-msg-bubble-text");
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalAnswer = "";
        let sources = [];
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();
            
            for (const line of lines) {
                const cleanLine = line.trim();
                if (!cleanLine.startsWith("data: ")) continue;
                
                try {
                    const data = JSON.parse(cleanLine.substring(6));
                    
                    if (data.type === "status") {
                        statusEl.style.display = "flex";
                        statusTextEl.textContent = data.content;
                    } else if (data.type === "token") {
                        statusEl.style.display = "none";
                        finalAnswer += data.content;
                        bubbleEl.innerHTML = parseMarkdown(finalAnswer);
                        el.chatMessagesContainer.scrollTop = el.chatMessagesContainer.scrollHeight;
                    } else if (data.type === "done") {
                        sources = data.sources;
                    } else if (data.type === "error") {
                        throw new Error(data.content);
                    }
                } catch (err) {
                    console.error("Stream parse error:", err);
                }
            }
        }
        
        // Add Citations if available
        if (sources && sources.length > 0) {
            const citationsEl = document.createElement("div");
            citationsEl.className = "chat-citations";
            citationsEl.innerHTML = '<span class="citation-label"><i class="fa-solid fa-feather"></i> Citations:</span>';
            
            sources.forEach(src => {
                const pill = document.createElement("span");
                pill.className = "citation-pill";
                pill.textContent = `Page ${src.page}`;
                pill.title = `${src.snippet} (${src.author}, ${src.year})`;
                citationsEl.appendChild(pill);
            });
            
            assistantMsgEl.querySelector(".chat-msg-body").appendChild(citationsEl);
            el.chatMessagesContainer.scrollTop = el.chatMessagesContainer.scrollHeight;
        }
        
    } catch (error) {
        removeTypingIndicator();
        appendChatMessage("assistant", `Sorry, I encountered an error answering your question: ${error.message}`);
    }
});


// Setup tab button click event handlers & Research Tools execution logic
function switchTab(tabId) {
    document.querySelectorAll(".pane-tab-btn").forEach(btn => {
        btn.classList.remove("active");
        if (btn.getAttribute("data-tab") === tabId) {
            btn.classList.add("active");
        }
    });
    
    document.querySelectorAll(".tab-content").forEach(content => {
        content.classList.add("hidden");
    });
    
    const activeContent = document.getElementById(tabId);
    if (activeContent) {
        activeContent.classList.remove("hidden");
    }
}

function loadComparePaperDropdown() {
    const select = document.getElementById("compare-paper-select");
    if (!select) return;
    
    select.innerHTML = '<option value="">Choose a paper...</option>';
    
    const currentDocId = state.activeDocForChat ? String(state.activeDocForChat._id || state.activeDocForChat.id) : null;
    state.documents.forEach(doc => {
        const docId = String(doc._id || doc.id);
        if (docId !== currentDocId && doc.status === "indexed") {
            const option = document.createElement("option");
            option.value = docId;
            option.textContent = doc.filename;
            select.appendChild(option);
        }
    });
}

function parseMarkdown(text) {
    if (!text) return "";
    let html = text;
    // Escape standard tags
    html = html.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    // Convert headers
    html = html.replace(/^### (.*$)/gim, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="md-h2">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="md-h1">$1</h1>');
    // Convert bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Convert bullet points
    html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="md-li">$1</li>');
    // Wrap consecutive linebreaks
    html = html.replace(/\n/g, '<br>');
    return html;
}

async function runResearchTool(toolName, apiEndpoint, extraParams = {}) {
    const activeDocId = state.activeDocForChat?._id || state.activeDocForChat?.id;
    if (!activeDocId) return;
    
    const resultBox = document.getElementById("tool-result-box");
    const resultContent = document.getElementById("tool-result-content");
    const resultTitle = document.getElementById("tool-result-title");
    
    resultTitle.textContent = `${toolName} - Processing...`;
    resultContent.innerHTML = `
        <div class="tool-loading">
            <div class="spinner-mini"></div>
            <span>Executing specialist agent logic for ${toolName.toLowerCase()}...</span>
        </div>
    `;
    resultBox.classList.remove("hidden");
    
    try {
        let endpoint = `/documents/${activeDocId}/tools/${apiEndpoint}`;
        if (extraParams.document_id_2) {
            endpoint += `?document_id_2=${extraParams.document_id_2}`;
        }
        
        const response = await apiCall(endpoint, { method: "POST" });
        resultTitle.textContent = toolName;
        resultContent.innerHTML = parseMarkdown(response.result);
    } catch (error) {
        resultTitle.textContent = `${toolName} - Failed`;
        resultContent.innerHTML = `<div class="tool-error"><i class="fa-solid fa-triangle-exclamation"></i> Error running tool: ${error.message}</div>`;
    }
}

// Attach Events
document.querySelectorAll(".pane-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        const tabId = btn.getAttribute("data-tab");
        switchTab(tabId);
    });
});

document.getElementById("btn-tool-summarize").addEventListener("click", () => {
    runResearchTool("Summarize Paper", "summarize");
});

document.getElementById("btn-tool-gaps").addEventListener("click", () => {
    runResearchTool("Find Research Gaps", "gaps");
});

document.getElementById("btn-tool-recommend").addEventListener("click", () => {
    runResearchTool("Recommend Papers", "recommend");
});

document.getElementById("btn-tool-flashcards").addEventListener("click", () => {
    runResearchTool("Generate Flashcards", "flashcards");
});

document.getElementById("btn-tool-timeline").addEventListener("click", () => {
    runResearchTool("Timeline Extraction", "timeline");
});

document.getElementById("btn-tool-compare").addEventListener("click", () => {
    const otherDocId = document.getElementById("compare-paper-select").value;
    if (!otherDocId) {
        alert("Please select another paper to compare with.");
        return;
    }
    runResearchTool("Compare Papers", "compare", { document_id_2: otherDocId });
});

document.getElementById("btn-clear-tool-result").addEventListener("click", () => {
    document.getElementById("tool-result-box").classList.add("hidden");
});

// Literature Review Project synthesis
document.getElementById("btn-tool-litreview").addEventListener("click", async () => {
    const projectId = state.activeProjectId;
    if (!projectId) return;
    
    const resultBox = document.getElementById("project-result-box");
    const resultContent = document.getElementById("project-result-content");
    
    resultContent.innerHTML = `
        <div class="tool-loading">
            <div class="spinner-mini"></div>
            <span>Synthesizing Literature Review for all papers in this project...</span>
        </div>
    `;
    resultBox.classList.remove("hidden");
    
    try {
        const response = await apiCall(`/documents/project/${projectId}/tools/literature-review`, { method: "POST" });
        resultContent.innerHTML = parseMarkdown(response.result);
    } catch (error) {
        resultContent.innerHTML = `<div class="tool-error"><i class="fa-solid fa-triangle-exclamation"></i> Error generating literature review: ${error.message}</div>`;
    }
});

document.getElementById("btn-clear-project-result").addEventListener("click", () => {
    document.getElementById("project-result-box").classList.add("hidden");
});

// 9. Startup Initial Session Check
window.addEventListener("DOMContentLoaded", checkAuth);

