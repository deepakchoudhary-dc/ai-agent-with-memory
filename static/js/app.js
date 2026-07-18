// Marked library configuration for styling Markdown safely
marked.setOptions({
    gfm: true,
    breaks: true,
    headerIds: false,
    mangle: false
});

class LocalChatApp {
    constructor() {
        // Retrieve the initial session ID set globally in templates/index.html
        this.currentSessionId = window.INITIAL_SESSION_ID || "";
        this.isDarkTheme = localStorage.getItem('theme') !== 'light';
        this.activeAbortController = null;
        
        // Elements mapping
        this.messagesEl = document.getElementById('messages');
        this.chatForm = document.getElementById('chat-form');
        this.chatInput = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('send-btn');
        this.stopBtn = document.getElementById('stop-btn');
        this.typingIndicator = document.getElementById('typing-indicator');
        this.typingStateText = document.getElementById('typing-state-text');
        this.sessionsList = document.getElementById('sessions-list');
        this.sessionSearch = document.getElementById('session-search');
        this.statusPill = document.getElementById('status-pill');
        this.statusText = document.getElementById('status-text');
        this.statusDetails = document.getElementById('status-details');
        this.sessionIdLabel = document.getElementById('session-id-label');
        this.activeSessionTitle = document.getElementById('active-session-title');
        this.exportLink = document.getElementById('export-link');
        this.exportJsonLink = document.getElementById('export-json-link');
        this.attachmentList = document.getElementById('attachment-list');
        this.uploadStatus = document.getElementById('upload-status');
        this.attachmentInput = document.getElementById('attachment-input');
        this.themeToggle = document.getElementById('theme-toggle');
        this.themeIcon = document.getElementById('theme-icon');
        this.modelSelector = document.getElementById('model-selector');
        this.memoryCoreList = document.getElementById('memory-core-list');
        
        // Memory Inbox elements
        this.memoryInboxSection = document.getElementById('memory-inbox-section');
        this.memoryInboxList = document.getElementById('memory-inbox-list');

        // Custom Modal elements
        this.modalOverlay = document.getElementById('custom-modal-container');
        this.modalTitle = document.getElementById('custom-modal-title');
        this.modalText = document.getElementById('custom-modal-text');
        this.modalInput = document.getElementById('custom-modal-input-field');
        this.modalCancelBtn = document.getElementById('custom-modal-cancel-btn');
        this.modalConfirmBtn = document.getElementById('custom-modal-confirm-btn');

        this.setupEventListeners();
        this.loadAvailableModels();
        this.initApp();
    }

    async fetchWithCsrf(url, options = {}) {
        if (!options.headers) {
            options.headers = {};
        }
        const method = (options.method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
            const tokenMeta = document.querySelector('meta[name="csrf-token"]');
            if (tokenMeta) {
                options.headers['X-CSRFToken'] = tokenMeta.getAttribute('content');
            }
        }
        return fetch(url, options);
    }

    // Custom Modal Dialog implementation
    showConfirm(title, message, callback) {
        this.modalCancelBtn.style.display = 'inline-block';
        this.modalConfirmBtn.style.display = 'inline-block';
        this.modalTitle.textContent = title;
        this.modalText.textContent = message;
        this.modalInput.style.display = 'none';
        this.modalOverlay.classList.add('active');
        
        const onCancel = () => {
            this.modalOverlay.classList.remove('active');
            cleanup();
            callback(false);
        };
        
        const onConfirm = () => {
            this.modalOverlay.classList.remove('active');
            cleanup();
            callback(true);
        };
        
        const cleanup = () => {
            this.modalCancelBtn.removeEventListener('click', onCancel);
            this.modalConfirmBtn.removeEventListener('click', onConfirm);
        };
        
        this.modalCancelBtn.addEventListener('click', onCancel);
        this.modalConfirmBtn.addEventListener('click', onConfirm);
    }

    showPrompt(title, message, defaultValue, callback) {
        this.modalCancelBtn.style.display = 'inline-block';
        this.modalConfirmBtn.style.display = 'inline-block';
        this.modalTitle.textContent = title;
        this.modalText.textContent = message;
        this.modalInput.value = defaultValue || '';
        this.modalInput.style.display = 'block';
        this.modalOverlay.classList.add('active');
        this.modalInput.focus();
        
        const onCancel = () => {
            this.modalOverlay.classList.remove('active');
            cleanup();
            callback(null);
        };
        
        const onConfirm = () => {
            this.modalOverlay.classList.remove('active');
            cleanup();
            callback(this.modalInput.value);
        };
        
        const cleanup = () => {
            this.modalCancelBtn.removeEventListener('click', onCancel);
            this.modalConfirmBtn.removeEventListener('click', onConfirm);
        };
        
        this.modalCancelBtn.addEventListener('click', onCancel);
        this.modalConfirmBtn.addEventListener('click', onConfirm);
    }

    showAlert(title, message) {
        this.modalCancelBtn.style.display = 'none';
        this.modalConfirmBtn.style.display = 'inline-block';
        this.modalTitle.textContent = title;
        this.modalText.textContent = message;
        this.modalInput.style.display = 'none';
        this.modalOverlay.classList.add('active');
        
        const onConfirm = () => {
            this.modalOverlay.classList.remove('active');
            this.modalConfirmBtn.removeEventListener('click', onConfirm);
        };
        
        this.modalConfirmBtn.addEventListener('click', onConfirm);
    }

    setupEventListeners() {
        // Chat form submission
        this.chatForm.addEventListener('submit', (e) => this.sendMessage(e));
        
        // Textarea height auto-adjust and key bindings
        this.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (this.chatInput.value.trim() && !this.sendBtn.disabled) {
                    this.chatForm.requestSubmit();
                }
            }
        });
        
        this.chatInput.addEventListener('input', () => {
            this.chatInput.style.height = 'auto';
            this.chatInput.style.height = Math.min(this.chatInput.scrollHeight, 180) + 'px';
        });

        // Top Toolbar/Sidebar click bindings
        document.getElementById('new-session-btn').addEventListener('click', () => this.createNewSession());
        document.getElementById('clear-view-btn').addEventListener('click', () => this.clearChatView());
        document.getElementById('upload-btn').addEventListener('click', () => this.attachmentInput.click());
        document.getElementById('reload-attachments-btn').addEventListener('click', () => this.loadAttachments());
        
        const clearAttBtn = document.getElementById('clear-attachments-btn');
        if (clearAttBtn) {
            clearAttBtn.addEventListener('click', () => this.clearAttachments());
        }
        
        // Stop generating listener
        if (this.stopBtn) {
            this.stopBtn.addEventListener('click', () => {
                if (this.activeAbortController) {
                    this.activeAbortController.abort();
                    this.activeAbortController = null;
                    this.setLoadingState(false);
                    this.renderToast("Generation stopped by user", false);
                }
            });
        }

        // Model selection persistence listener
        this.modelSelector.addEventListener('change', () => {
            localStorage.setItem('selectedModel', this.modelSelector.value);
        });

        // File uploads change listener
        this.attachmentInput.addEventListener('change', (e) => this.handleFileUpload(e));

        // Search session filter typing listener
        let searchTimeout;
        this.sessionSearch.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.loadSessions(this.sessionSearch.value.trim());
            }, 250);
        });

        // Theme switch listener
        this.themeToggle.addEventListener('click', () => this.toggleTheme());

        // Mobile Sidebar toggle
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        const mobToggle = document.getElementById('mobile-sidebar-toggle');
        if (mobToggle && sidebar && overlay) {
            mobToggle.addEventListener('click', () => {
                sidebar.classList.toggle('open');
                overlay.classList.toggle('open');
            });
            overlay.addEventListener('click', () => {
                sidebar.classList.remove('open');
                overlay.classList.remove('open');
            });
        }

        // Collapsible sidebar sections
        document.querySelectorAll('.sidebar-section-header').forEach(header => {
            header.addEventListener('click', () => {
                const section = header.parentElement;
                section.classList.toggle('collapsed');
                
                // Store collapsed state in localStorage
                const sectionId = section.getAttribute('id');
                if (sectionId) {
                    localStorage.setItem(`section_collapsed_${sectionId}`, section.classList.contains('collapsed'));
                }
            });
        });
    }

    async initApp() {
        this.applyTheme();

        // Restore collapsible states from localStorage
        document.querySelectorAll('.sidebar-section').forEach(section => {
            const sectionId = section.getAttribute('id');
            if (sectionId) {
                const isCollapsed = localStorage.getItem(`section_collapsed_${sectionId}`) === 'true';
                if (isCollapsed) {
                    section.classList.add('collapsed');
                }
            }
        });

        // Run loaders concurrently in parallel so slow endpoints (e.g. server health connection) do not block UI loading
        this.checkSystemHealth();
        this.loadSessions();
        this.loadHistory(this.currentSessionId);
        this.loadAttachments();
        this.loadFacts();
        this.loadCandidates();
        this.updateExportLink();
    }

    toggleTheme() {
        this.isDarkTheme = !this.isDarkTheme;
        this.applyTheme();
    }

    applyTheme() {
        const root = document.documentElement;
        if (this.isDarkTheme) {
            root.setAttribute('data-theme', 'dark');
            // Moon SVG
            this.themeIcon.innerHTML = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`;
            localStorage.setItem('theme', 'dark');
        } else {
            root.setAttribute('data-theme', 'light');
            // Sun SVG
            this.themeIcon.innerHTML = `
                <circle cx="12" cy="12" r="5"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            `;
            localStorage.setItem('theme', 'light');
        }
    }

    setLoadingState(isLoading, stateText = 'Thinking') {
        this.sendBtn.disabled = isLoading;
        if (isLoading) {
            this.typingStateText.textContent = stateText;
            this.typingIndicator.style.display = 'inline-flex';
        } else {
            this.typingIndicator.style.display = 'none';
        }
    }

    setStatus(isOnline, summary, details) {
        this.statusPill.classList.toggle('offline', !isOnline);
        this.statusText.textContent = summary;
        this.statusDetails.textContent = details || '';
    }

    updateExportLink() {
        this.exportLink.href = `/export/${encodeURIComponent(this.currentSessionId)}?format=markdown`;
        this.exportJsonLink.href = `/export/${encodeURIComponent(this.currentSessionId)}?format=json`;
        this.sessionIdLabel.textContent = this.currentSessionId;
    }

    renderToast(msg, isError = false) {
        const toast = document.createElement('div');
        toast.className = `toast-notice ${isError ? 'error' : ''}`;
        
        const iconSvg = isError ? 
            `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>` : 
            `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 16 16 12 12 8"></polyline><line x1="8" y1="12" x2="16" y2="12"></line></svg>`;

        toast.innerHTML = `${iconSvg} <span>${msg}</span>`;
        this.messagesEl.appendChild(toast);
        this.scrollToBottom();
        
        // Auto dismiss toast in feed after 5 seconds
        setTimeout(() => {
            toast.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-10px)';
            setTimeout(() => toast.remove(), 500);
        }, 5000);
    }

    clearChatView() {
        this.messagesEl.innerHTML = '';
        this.renderWelcomeDashboard();
    }

    renderWelcomeDashboard() {
        this.messagesEl.innerHTML = `
            <div class="welcome-dashboard">
                <div class="welcome-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                </div>
                <h2 class="welcome-title">Local Memory Chat</h2>
                <p class="welcome-subtitle">A high-performance local AI chat interface with episodic memory capabilities. Your conversations are embedded semantically and stored locally to enrich future prompts contextually.</p>
                
                <div class="welcome-grid">
                    <div class="welcome-card" onclick="document.getElementById('chat-input').value = 'Can you introduce yourself?'; document.getElementById('chat-input').focus();">
                        <div class="welcome-card-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                        </div>
                        <h3>Introduction</h3>
                        <p>"Introduce yourself and list what capabilities you have."</p>
                    </div>
                    <div class="welcome-card" onclick="document.getElementById('chat-input').value = 'Do you remember what we talked about previously?'; document.getElementById('chat-input').focus();">
                        <div class="welcome-card-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                        </div>
                        <h3>Episodic Memory</h3>
                        <p>"Do you remember what we discussed in previous sessions?"</p>
                    </div>
                </div>
            </div>
        `;
    }

    scrollToBottom() {
        this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }

    // Extract <think></think> block from text string
    parseThinkingContent(text) {
        let thinking = '';
        let answer = '';
        const thinkStartTag = '<think>';
        const thinkEndTag = '</think>';
        
        const startIdx = text.indexOf(thinkStartTag);
        const endIdx = text.indexOf(thinkEndTag);
        
        if (startIdx !== -1) {
            if (endIdx !== -1) {
                thinking = text.slice(startIdx + thinkStartTag.length, endIdx).trim();
                answer = text.slice(endIdx + thinkEndTag.length).trim();
            } else {
                thinking = text.slice(startIdx + thinkStartTag.length).trim();
                answer = '';
            }
        } else {
            answer = text.trim();
        }
        
        return { thinking, answer };
    }

    // Format code block headers and HTML escaping inside marked.js wrapper
    renderMarkdown(text) {
        if (!text) return '';
        return DOMPurify.sanitize(marked.parse(text));
    }

    // Health monitoring checks
    async checkSystemHealth() {
        try {
            const response = await this.fetchWithCsrf('/health');
            const data = await response.json();
            
            if (response.ok && data.status === 'healthy') {
                const ollamaInfo = data.ollama ? 'Ollama online' : 'Ollama status unknown';
                const dbInfo = data.database ? 'Database linked' : 'Database error';
                const vectorInfo = data.memory_system ? 'FAISS index initialized' : 'FAISS index missing';
                
                this.setStatus(true, 'Connected', `${ollamaInfo} • ${dbInfo} • ${vectorInfo}`);
            } else {
                this.setStatus(false, 'System Unhealthy', data.error || 'Health check reported errors');
            }
        } catch (error) {
            this.setStatus(false, 'Offline', 'Failed to communicate with Flask backend');
        }
    }

    // Session loader
    async loadSessions(query = '') {
        try {
            const url = query ? `/sessions?q=${encodeURIComponent(query)}` : '/sessions';
            const response = await this.fetchWithCsrf(url);
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.error || 'Failed to retrieve sessions');
            
            const sessions = Array.isArray(data.sessions) ? data.sessions : [];
            this.sessionsList.innerHTML = '';
            
            if (sessions.length === 0) {
                this.sessionsList.innerHTML = `<div class="empty-state">No conversations found.</div>`;
                return;
            }
            
            sessions.forEach(session => {
                const isActive = session.session_id === this.currentSessionId;
                
                const itemDiv = document.createElement('div');
                itemDiv.className = `session-item ${isActive ? 'active' : ''}`;
                itemDiv.setAttribute('data-id', session.session_id);
                
                const dateStr = session.last_activity ? new Date(session.last_activity).toLocaleDateString(undefined, {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : 'Unknown';
                
                itemDiv.innerHTML = `
                    <div class="session-item-content">
                        <div class="session-item-title">${this.escapeHtml(session.title || 'New Chat')}</div>
                        <div class="session-item-meta">${session.message_count || 0} messages • ${dateStr}</div>
                        ${session.snippet ? `<div class="session-item-snippet">${this.escapeHtml(session.snippet)}</div>` : ''}
                    </div>
                    <div class="session-item-actions">
                        <button class="action-icon-btn" title="Rename Chat" onclick="event.stopPropagation(); window.localChatApp.triggerRename('${session.session_id}', '${this.escapeJsString(session.title || 'New Chat')}')">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                        </button>
                        <button class="action-icon-btn delete" title="Delete Chat" onclick="event.stopPropagation(); window.localChatApp.triggerDelete('${session.session_id}')">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                `;
                
                itemDiv.addEventListener('click', () => this.switchSession(session.session_id, session.title || 'Chat Session'));
                this.sessionsList.appendChild(itemDiv);
                
                if (isActive) {
                    this.activeSessionTitle.textContent = session.title || 'Chat Session';
                }
            });
        } catch (error) {
            console.error(error);
            this.sessionsList.innerHTML = `<div class="empty-state text-danger">Failed to load session list.</div>`;
        }
    }

    // Switch session action
    async switchSession(sessionId, title) {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        if (sidebar) sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('open');

        if (sessionId === this.currentSessionId && this.messagesEl.children.length > 0 && !this.messagesEl.querySelector('.welcome-dashboard')) return;
        
        this.currentSessionId = sessionId;
        this.activeSessionTitle.textContent = title || 'Chat Session';
        this.updateExportLink();
        
        // Re-render highlight
        Array.from(this.sessionsList.children).forEach(el => {
            el.classList.toggle('active', el.getAttribute('data-id') === sessionId);
        });

        await this.loadHistory(sessionId);
        await this.loadAttachments();
        this.chatInput.focus();
    }

    // Load messages history
    async loadHistory(sessionId) {
        try {
            this.messagesEl.innerHTML = '';
            const response = await this.fetchWithCsrf(`/history/${encodeURIComponent(sessionId)}`);
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.error || 'Failed to download chat history');
            
            const messages = Array.isArray(data.messages) ? data.messages : [];
            
            if (messages.length === 0) {
                this.renderWelcomeDashboard();
                return;
            }
            
            messages.forEach(msg => {
                this.appendMessageToFeed(msg.role, msg.content, msg.timestamp, null);
            });
            
            this.scrollToBottom();
        } catch (error) {
            this.renderToast(`Failed to load chat history: ${error.message}`, true);
            this.renderWelcomeDashboard();
        }
    }

    // Create new chat session
    async createNewSession() {
        this.setLoadingState(true, 'Creating chat');
        try {
            const response = await this.fetchWithCsrf('/new_session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.error || 'Session creation failed');
            
            this.currentSessionId = data.session_id;
            this.activeSessionTitle.textContent = 'New Chat';
            this.updateExportLink();
            
            this.clearChatView();
            await this.loadSessions();
            await this.loadAttachments();
            this.chatInput.value = '';
            this.chatInput.style.height = 'auto';
            this.chatInput.focus();
        } catch (error) {
            this.renderToast(`Failed to create new session: ${error.message}`, true);
        } finally {
            this.setLoadingState(false);
        }
    }

    // Rename session action trigger
    triggerRename(sessionId, oldTitle) {
        this.showPrompt('Rename Conversation', 'Enter new title for this conversation:', oldTitle, async (newTitle) => {
            if (newTitle === null) return;
            
            const titleClean = newTitle.trim();
            if (!titleClean) return;
            
            try {
                const response = await this.fetchWithCsrf(`/sessions/${encodeURIComponent(sessionId)}/rename`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: titleClean })
                });
                const data = await response.json();
                
                if (!response.ok) throw new Error(data.error || 'Failed to rename session');
                
                if (sessionId === this.currentSessionId) {
                    this.activeSessionTitle.textContent = titleClean;
                }
                
                await this.loadSessions();
            } catch (error) {
                this.showAlert('Error', `Error renaming session: ${error.message}`);
            }
        });
    }

    // Delete session action trigger
    triggerDelete(sessionId) {
        this.showConfirm(
            'Delete Conversation',
            'Are you sure you want to delete this chat session and its corresponding episodic memory embeddings? This action is permanent.',
            async (confirmDelete) => {
                if (!confirmDelete) return;
                
                try {
                    const response = await this.fetchWithCsrf(`/sessions/${encodeURIComponent(sessionId)}`, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    
                    if (!response.ok) throw new Error(data.error || 'Delete failed');
                    
                    if (data.new_session_id) {
                        // Deleted active session, load new session ID
                        this.currentSessionId = data.new_session_id;
                        this.activeSessionTitle.textContent = 'New Chat';
                        this.updateExportLink();
                        this.clearChatView();
                    } else if (sessionId === this.currentSessionId) {
                        // Fallback if deleted active and no new session ID returned
                        this.createNewSession();
                        return;
                    }
                    
                    await this.loadSessions();
                    await this.loadAttachments();
                } catch (error) {
                    this.showAlert('Error', `Error deleting session: ${error.message}`);
                }
            }
        );
    }

    // Get session file attachments list
    async loadAttachments() {
        try {
            const response = await this.fetchWithCsrf(`/attachments?session_id=${encodeURIComponent(this.currentSessionId)}`);
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.error || 'Failed to fetch files');
            
            const attachments = Array.isArray(data.attachments) ? data.attachments : [];
            this.attachmentList.innerHTML = '';
            
            if (attachments.length === 0) {
                this.attachmentList.innerHTML = `<div class="empty-state" style="padding: 6px 0;">No context files attached.</div>`;
                this.uploadStatus.textContent = 'No uploads in this chat.';
                return;
            }
            
            attachments.forEach(file => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'attachment-item';
                
                const sizeFormatted = this.formatBytes(file.size || 0);
                itemDiv.innerHTML = `
                    <div class="attachment-name" title="${this.escapeHtml(file.filename)}">${this.escapeHtml(file.filename)}</div>
                    <div class="attachment-meta">${sizeFormatted}</div>
                    <button class="action-icon-btn delete" title="Delete attachment" onclick="event.stopPropagation(); window.localChatApp.deleteAttachment('${file.id}')" style="background: transparent; border: none; padding: 2px; cursor: pointer; color: var(--text-muted); display: flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 4px; margin-left: 6px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                `;
                this.attachmentList.appendChild(itemDiv);
            });
            
            this.uploadStatus.textContent = `${attachments.length} context file(s) loaded.`;
        } catch (error) {
            console.error(error);
            this.attachmentList.innerHTML = `<div class="empty-state text-danger">Failed to load files.</div>`;
        }
    }

    // Delete an individual attachment file
    deleteAttachment(attachmentId) {
        this.showConfirm(
            'Remove File',
            'Are you sure you want to remove this file from your chat context?',
            async (confirmDelete) => {
                if (!confirmDelete) return;
                try {
                    const response = await this.fetchWithCsrf(`/attachments/${encodeURIComponent(attachmentId)}`, {
                        method: 'DELETE'
                    });
                    if (response.ok) {
                        await this.loadAttachments();
                        this.renderToast("Attachment removed", false);
                    } else {
                        const data = await response.json();
                        this.showAlert('Error', `Failed to delete attachment: ${data.error}`);
                    }
                } catch (error) {
                    this.showAlert('Error', `Error deleting attachment: ${error.message}`);
                }
            }
        );
    }

    // Clear all attachments from the session
    clearAttachments() {
        this.showConfirm(
            'Clear All Files',
            'Are you sure you want to remove all context files from this session?',
            async (confirmClear) => {
                if (!confirmClear) return;
                try {
                    const response = await this.fetchWithCsrf('/attachments/clear', {
                        method: 'POST'
                    });
                    if (response.ok) {
                        await this.loadAttachments();
                        this.renderToast("All attachments cleared", false);
                    } else {
                        const data = await response.json();
                        this.showAlert('Error', `Failed to clear attachments: ${data.error}`);
                    }
                } catch (error) {
                    this.showAlert('Error', `Error clearing attachments: ${error.message}`);
                }
            }
        );
    }

    // Handle file upload post
    async handleFileUpload(event) {
        const files = Array.from(event.target.files || []);
        if (files.length === 0) return;
        
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));
        
        this.uploadStatus.textContent = 'Uploading files...';
        
        try {
            const response = await this.fetchWithCsrf('/attachments/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.error || 'Upload failed');
            
            const uploaded = Array.isArray(data.uploaded) ? data.uploaded.length : 0;
            const rejected = Array.isArray(data.rejected) ? data.rejected.length : 0;
            
            let statusMsg = `Successfully uploaded ${uploaded} file(s).`;
            if (rejected > 0) {
                statusMsg += ` ${rejected} file(s) rejected.`;
                const errors = data.rejected.map(r => `${r.filename}: ${r.reason}`).join('\n');
                this.showAlert('Upload Status', `Some files were rejected:\n${errors}`);
            }
            
            this.uploadStatus.textContent = statusMsg;
            await this.loadAttachments();
        } catch (error) {
            this.uploadStatus.textContent = `Upload failed: ${error.message}`;
            this.showAlert('Upload Failed', `File upload failed: ${error.message}`);
        } finally {
            this.attachmentInput.value = '';
        }
    }

    // Send message trigger
    async sendMessage(event) {
        event.preventDefault();
        
        const messageText = this.chatInput.value.trim();
        if (!messageText) return;
        
        // Clear welcome dashboard if present
        const activeModel = this.modelSelector.value;
        if (this.messagesEl.querySelector('.welcome-dashboard')) {
            this.messagesEl.innerHTML = '';
        }
        
        // Append User Message immediately
        this.appendMessageToFeed('user', messageText, new Date().toISOString(), null);
        
        // Clear input textarea and reset height
        this.chatInput.value = '';
        this.chatInput.style.height = 'auto';
        this.scrollToBottom();
        
        this.setLoadingState(true, 'Streaming response');

        // Create assistant placeholder message for streaming
        const streamNode = this.createStreamingAssistantNode();
        
        this.activeAbortController = new AbortController();
        const signal = this.activeAbortController.signal;

        try {
            const response = await this.fetchWithCsrf('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: messageText, stream: true, model: activeModel }),
                signal: signal
            });
            
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || 'Chat request failed');
            }
            
            await this.readNDJSONStream(response, streamNode);
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log("Chat stream aborted by user.");
            } else {
                console.error(error);
                streamNode.bubbleContainer.innerHTML = `<div class="toast-notice error" style="margin: 0;"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><span>Error: ${error.message}</span></div>`;
            }
        } finally {
            this.activeAbortController = null;
            this.setLoadingState(false);
            this.scrollToBottom();
        }
    }

    // Create streaming assistant message skeleton
    createStreamingAssistantNode() {
        const row = document.createElement('div');
        row.className = 'message-row assistant';
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = 'AI';
        
        const body = document.createElement('div');
        body.className = 'message-body';
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        // Inner streaming indicator
        bubble.innerHTML = `
            <div class="typing-indicator" style="padding: 4px 0;">
                <span>Local model is generating</span>
                <span class="typing-dots"><span></span><span></span><span></span></span>
            </div>
        `;
        
        const meta = document.createElement('div');
        meta.className = 'message-meta';
        meta.textContent = 'Just now';
        
        body.appendChild(bubble);
        body.appendChild(meta);
        row.appendChild(avatar);
        row.appendChild(body);
        
        this.messagesEl.appendChild(row);
        this.scrollToBottom();
        
        return {
            row,
            bodyContainer: body,
            bubbleContainer: bubble,
            metaContainer: meta
        };
    }

    // NDJSON Stream parser
    async readNDJSONStream(response, streamNode) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let streamedText = '';
        let finalPayload = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                const trimmedLine = line.trim();
                if (!trimmedLine) continue;
                
                let payload = null;
                try {
                    payload = JSON.parse(trimmedLine);
                } catch (e) {
                    continue; // Skip parsing errors for partial lines
                }
                
                if (payload.type === 'chunk') {
                    streamedText += payload.content || '';
                    
                    // Parse thinking inline on the fly
                    const { thinking, answer } = this.parseThinkingContent(streamedText);
                    
                    let outputHTML = '';
                    if (thinking) {
                        outputHTML += `
                            <div class="thinking-container">
                                <div class="thinking-toggle" onclick="this.parentElement.classList.toggle('collapsed')">
                                    <span>🤔 Thinking Process...</span>
                                    <svg class="thinking-toggle-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                                </div>
                                <div class="thinking-content">${this.escapeHtml(thinking)}</div>
                            </div>
                        `;
                    }
                    
                    if (answer) {
                        outputHTML += `<div class="message-markdown">${this.renderMarkdown(answer)}</div>`;
                    } else if (!thinking) {
                        // If nothing is parsed yet, show loader
                        outputHTML = `
                            <div class="typing-indicator" style="padding: 4px 0;">
                                <span>Generating content...</span>
                                <span class="typing-dots"><span></span><span></span><span></span></span>
                            </div>
                        `;
                    }
                    
                    streamNode.bubbleContainer.innerHTML = outputHTML;
                    this.scrollToBottom();
                } else if (payload.type === 'done') {
                    finalPayload = payload;
                } else if (payload.type === 'error') {
                    throw new Error(payload.error || 'Model error during streaming');
                }
            }
        }

        // Process final done status payload
        if (!finalPayload) {
            finalPayload = {
                response: streamedText,
                thinking: '',
                session_id: this.currentSessionId,
                memories_used: []
            };
        }
        
        const finalResponse = finalPayload.response || streamedText;
        const finalThinking = finalPayload.thinking || '';
        const finalMemories = finalPayload.memories_used || [];
        
        // Overwrite final message presentation with actions & memories
        this.presentFinalAssistantMessage(streamNode, finalResponse, finalThinking, finalMemories, finalPayload.timestamp || new Date().toISOString());
        
        // Update active state session ID
        if (finalPayload.session_id && finalPayload.session_id !== this.currentSessionId) {
            this.currentSessionId = finalPayload.session_id;
            this.updateExportLink();
        }
        
        // Reload list of sessions, attachments, facts, and candidates
        await this.loadSessions();
        await this.loadAttachments();
        await this.loadFacts();
        await this.loadCandidates();
    }

    // Present final AI reply with copy actions and matching memory timeline
    presentFinalAssistantMessage(streamNode, text, thinking, memories, timestamp) {
        let htmlOutput = '';
        
        // Add thinking accordion
        if (thinking) {
            htmlOutput += `
                <div class="thinking-container">
                    <div class="thinking-toggle" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span>🤔 Thinking Process</span>
                        <svg class="thinking-toggle-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </div>
                    <div class="thinking-content">${this.escapeHtml(thinking)}</div>
                </div>
            `;
        }
        
        // Add final answer
        htmlOutput += `<div class="message-markdown">${this.renderMarkdown(text)}</div>`;
        
        // Add copy buttons and action tray
        htmlOutput += `
            <div class="message-bubble-actions">
                <button class="message-bubble-btn" onclick="window.localChatApp.copyToClipboard(this, \`${this.escapeJsString(text)}\`)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    Copy Response
                </button>
                <button class="message-bubble-btn" onclick="window.localChatApp.regenerateLastMessage()" style="margin-left: 8px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                    Regenerate
                </button>
            </div>
        `;
        
        // Add referenced memories
        if (memories && memories.length > 0) {
            htmlOutput += `
                <div class="memories-container">
                    <div class="memories-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                        Referenced memories (${memories.length})
                    </div>
                    <div class="memory-pills">
            `;
            
            memories.forEach(mem => {
                const pct = (mem.similarity * 100).toFixed(1);
                const memDate = mem.timestamp ? new Date(mem.timestamp).toLocaleDateString() : 'Previous chat';
                htmlOutput += `
                    <div class="memory-pill">
                        <div class="memory-pill-header">
                            <span>Session Match (${memDate})</span>
                            <span class="memory-badge">${pct}% match</span>
                        </div>
                        <div class="memory-pill-body">${this.escapeHtml(mem.content)}</div>
                    </div>
                `;
            });
            
            htmlOutput += `
                    </div>
                </div>
            `;
        }
        
        streamNode.bubbleContainer.innerHTML = htmlOutput;
        
        const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString(undefined, {hour: '2-digit', minute: '2-digit'}) : new Date().toLocaleTimeString();
        streamNode.metaContainer.textContent = timeStr;
        this.scrollToBottom();
        
        // Post-process highlight / syntax bindings
        this.attachCodeBlockCopyHandlers(streamNode.bubbleContainer);
    }

    // Append standard message bubble to log window
    appendMessageToFeed(role, content, timestamp, memories) {
        const row = document.createElement('div');
        row.className = `message-row ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? 'U' : 'AI';
        
        const body = document.createElement('div');
        body.className = 'message-body';
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        if (role === 'user') {
            bubble.textContent = content;
        } else {
            const { thinking, answer } = this.parseThinkingContent(content);
            let htmlOutput = '';
            
            if (thinking) {
                htmlOutput += `
                    <div class="thinking-container collapsed">
                        <div class="thinking-toggle" onclick="this.parentElement.classList.toggle('collapsed')">
                            <span>🤔 Thinking Process (click to expand)</span>
                            <svg class="thinking-toggle-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                        </div>
                        <div class="thinking-content">${this.escapeHtml(thinking)}</div>
                    </div>
                `;
            }
            
            htmlOutput += `<div class="message-markdown">${this.renderMarkdown(answer)}</div>`;
            
            // Copy button
            htmlOutput += `
                <div class="message-bubble-actions">
                    <button class="message-bubble-btn" onclick="window.localChatApp.copyToClipboard(this, \`${this.escapeJsString(answer)}\`)">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        Copy Response
                    </button>
                    <button class="message-bubble-btn" onclick="window.localChatApp.regenerateLastMessage()" style="margin-left: 8px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                        Regenerate
                    </button>
                </div>
            `;
            
            bubble.innerHTML = htmlOutput;
            
            // Add code block copy buttons inside this element
            this.attachCodeBlockCopyHandlers(bubble);
        }
        
        const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString(undefined, {hour: '2-digit', minute: '2-digit'}) : new Date().toLocaleTimeString();
        
        const meta = document.createElement('div');
        meta.className = 'message-meta';
        meta.textContent = timeStr;
        
        body.appendChild(bubble);
        body.appendChild(meta);
        row.appendChild(avatar);
        row.appendChild(body);
        
        this.messagesEl.appendChild(row);
        this.scrollToBottom();
    }

    // Copy helper
    async copyToClipboard(buttonEl, text) {
        try {
            await navigator.clipboard.writeText(text);
            const originalHTML = buttonEl.innerHTML;
            buttonEl.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--success);"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span style="color: var(--success);">Copied</span>
            `;
            setTimeout(() => {
                buttonEl.innerHTML = originalHTML;
            }, 1500);
        } catch (err) {
            console.error('Failed to copy text: ', err);
        }
    }

    // Inject language headers and copy code buttons to dynamically created code tags
    attachCodeBlockCopyHandlers(containerElement) {
        const codeBlocks = containerElement.querySelectorAll('pre');
        
        codeBlocks.forEach(pre => {
            // Check if copy button is already attached
            if (pre.previousElementSibling && pre.previousElementSibling.classList.contains('code-block-header')) return;
            
            const code = pre.querySelector('code');
            const rawText = code ? code.innerText : pre.innerText;
            
            // Detect language
            let lang = 'code';
            if (code && code.className) {
                const match = code.className.match(/language-(\w+)/);
                if (match && match[1]) lang = match[1];
            }
            
            const header = document.createElement('div');
            header.className = 'code-block-header';
            header.innerHTML = `
                <span>${lang.toUpperCase()}</span>
                <span class="message-bubble-btn" style="padding: 2px 6px; font-size: 10px; margin: 0; color: #94a3b8;" onclick="window.localChatApp.copyToClipboard(this, \`${this.escapeJsString(rawText)}\`)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    Copy
                </span>
            `;
            
            pre.parentNode.insertBefore(header, pre);
        });
    }

    // HTML escaping helper
    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }

    // Escape JS string interpolation template characters
    escapeJsString(str) {
        if (!str) return '';
        return str
            .replace(/\\/g, '\\\\')
            .replace(/`/g, '\\`')
            .replace(/\$/g, '\\$')
            .replace(/"/g, '\\"')
            .replace(/'/g, "\\'")
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r');
    }

    escapeJsStringSimple(str) {
        return this.escapeJsString(str);
    }

    escapeJsStringAttr(str) {
        return this.escapeHtml(this.escapeJsString(str));
    }

    escapeHtmlAttr(str) {
        return this.escapeHtml(str);
    }

    escapeJsStringForInlineHtml(str) {
        return this.escapeJsString(str);
    }

    // Format size numbers
    formatBytes(bytes, decimals = 1) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // Load available Ollama models
    async loadAvailableModels() {
        try {
            const response = await this.fetchWithCsrf('/models');
            const data = await response.json();
            this.modelSelector.innerHTML = '';
            
            const savedModel = localStorage.getItem('selectedModel');
            
            if (data.models && data.models.length > 0) {
                data.models.forEach(modelName => {
                    const option = document.createElement('option');
                    option.value = modelName;
                    option.textContent = modelName;
                    if (savedModel ? modelName === savedModel : modelName === data.default) {
                        option.selected = true;
                    }
                    this.modelSelector.appendChild(option);
                });
            } else {
                const fallbackModel = savedModel || data.default || 'your-model-name';
                this.modelSelector.innerHTML = `<option value="${fallbackModel}">${fallbackModel}</option>`;
            }
        } catch (error) {
            console.error('Failed to load Ollama models:', error);
            const savedModel = localStorage.getItem('selectedModel') || 'your-model-name';
            this.modelSelector.innerHTML = `<option value="${savedModel}">${savedModel}</option>`;
        }
    }

    // Load all extracted profile facts
    async loadFacts() {
        try {
            const response = await this.fetchWithCsrf('/facts');
            const data = await response.json();
            this.memoryCoreList.innerHTML = '';
            
            const facts = Array.isArray(data.facts) ? data.facts : [];
            if (facts.length === 0) {
                this.memoryCoreList.innerHTML = `<div class="empty-state" style="padding: 6px 0; font-size: 11px; text-align: center;">No extracted user facts yet. Start chatting!</div>`;
                return;
            }
            
            facts.forEach(item => {
                const factDiv = document.createElement('div');
                factDiv.className = 'attachment-item';
                factDiv.style.display = 'flex';
                factDiv.style.alignItems = 'center';
                factDiv.style.justifyContent = 'space-between';
                factDiv.style.padding = '8px 10px';
                factDiv.style.gap = '8px';
                factDiv.style.background = 'rgba(99, 102, 241, 0.05)';
                factDiv.style.border = '1px solid rgba(99, 102, 241, 0.1)';
                factDiv.style.borderRadius = '10px';
                
                const tooltipText = item.source_timestamp ? 
                    `Stated in: "${item.session_title || 'Chat'}"\nOriginal text: "${item.source_content || ''}"\nDate: ${new Date(item.source_timestamp).toLocaleString()}` : 
                    'Pre-existing memory fact';
                
                factDiv.innerHTML = `
                    <div class="attachment-name" style="font-size: 11px; color: var(--text-primary); line-height: 1.3; font-weight: 500; cursor: help;" data-tooltip="${this.escapeHtml(tooltipText)}" title="${this.escapeHtml(tooltipText)}">
                        ${this.escapeHtml(item.fact)}
                    </div>
                    <button class="action-icon-btn delete" title="Delete memory fact" onclick="event.stopPropagation(); window.localChatApp.deleteFact('${item.id}')" style="background: transparent; border: none; padding: 2px; cursor: pointer; color: var(--text-muted); display: flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 4px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                `;
                this.memoryCoreList.appendChild(factDiv);
            });
        } catch (error) {
            console.error('Failed to load facts:', error);
            this.memoryCoreList.innerHTML = `<div class="empty-state text-danger" style="font-size: 11px; text-align: center;">Failed to load profile facts.</div>`;
        }
    }

    // Delete a profile fact
    deleteFact(factId) {
        this.showConfirm(
            'Delete Profile Fact',
            'Are you sure you want to delete this fact from your profile? The AI will forget this preference.',
            async (confirmDelete) => {
                if (!confirmDelete) return;
                try {
                    const response = await this.fetchWithCsrf(`/facts/${encodeURIComponent(factId)}`, {
                        method: 'DELETE'
                    });
                    if (response.ok) {
                        await this.loadFacts();
                        this.renderToast("Fact deleted", false);
                    } else {
                        const data = await response.json();
                        this.showAlert('Error', `Failed to delete fact: ${data.error}`);
                    }
                } catch (error) {
                    this.showAlert('Error', `Error deleting fact: ${error.message}`);
                }
            }
        );
    }

    // Load and render pending memory candidates
    async loadCandidates() {
        try {
            const response = await this.fetchWithCsrf('/memory/candidates');
            const data = await response.json();
            
            const candidates = Array.isArray(data.candidates) ? data.candidates : [];
            if (candidates.length === 0) {
                this.memoryInboxSection.style.display = 'none';
                this.memoryInboxList.innerHTML = '';
                return;
            }
            
            this.memoryInboxSection.style.display = 'block';
            this.memoryInboxList.innerHTML = '';
            
            candidates.forEach(item => {
                const candDiv = document.createElement('div');
                candDiv.className = 'attachment-item';
                candDiv.style.display = 'flex';
                candDiv.style.flexDirection = 'column';
                candDiv.style.padding = '8px 10px';
                candDiv.style.gap = '6px';
                candDiv.style.background = 'rgba(99, 102, 241, 0.04)';
                candDiv.style.border = '1px solid rgba(99, 102, 241, 0.15)';
                candDiv.style.borderRadius = '10px';
                
                let badgeClass = 'add';
                let actionLabel = 'New';
                if (item.action === 'UPDATE') {
                    badgeClass = 'update';
                    actionLabel = 'Update';
                } else if (item.action === 'DELETE') {
                    badgeClass = 'delete';
                    actionLabel = 'Forget';
                }
                
                const tooltipText = item.source_content ? 
                    `Inferred from: "${item.source_content}"\nChat: "${item.session_title || 'Chat'}"` : 
                    'Background extraction';
                    
                candDiv.innerHTML = `
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;">
                        <div style="font-size: 11px; line-height: 1.3; font-weight: 500; color: var(--text-primary);" data-tooltip="${this.escapeHtml(tooltipText)}" title="${this.escapeHtml(tooltipText)}">
                            <span class="candidate-badge ${badgeClass}">${actionLabel}</span>
                            ${this.escapeHtml(item.fact)}
                        </div>
                        <div style="display: flex; gap: 4px; align-self: flex-start;">
                            <button class="action-icon-btn" title="Approve proposed memory" onclick="window.localChatApp.approveCandidate('${item.id}')" style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); padding: 4px; cursor: pointer; color: var(--success); display: flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 4px;">
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            </button>
                            <button class="action-icon-btn delete" title="Reject proposed memory" onclick="window.localChatApp.rejectCandidate('${item.id}')" style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); padding: 4px; cursor: pointer; color: var(--danger); display: flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 4px;">
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                            </button>
                        </div>
                    </div>
                `;
                this.memoryInboxList.appendChild(candDiv);
            });
        } catch (error) {
            console.error('Failed to load memory candidates:', error);
        }
    }

    async approveCandidate(candidateId) {
        try {
            const response = await this.fetchWithCsrf(`/memory/candidates/${encodeURIComponent(candidateId)}/approve`, {
                method: 'POST'
            });
            if (response.ok) {
                this.renderToast("Proposed memory approved & applied!", false);
                await this.loadCandidates();
                await this.loadFacts();
            } else {
                const data = await response.json();
                this.showAlert("Error", `Failed to approve proposed memory: ${data.error}`);
            }
        } catch (error) {
            this.showAlert("Error", `Failed to approve proposed memory: ${error.message}`);
        }
    }

    async rejectCandidate(candidateId) {
        try {
            const response = await this.fetchWithCsrf(`/memory/candidates/${encodeURIComponent(candidateId)}/reject`, {
                method: 'POST'
            });
            if (response.ok) {
                this.renderToast("Proposed memory rejected.", false);
                await this.loadCandidates();
            } else {
                const data = await response.json();
                this.showAlert("Error", `Failed to reject proposed memory: ${data.error}`);
            }
        } catch (error) {
            this.showAlert("Error", `Failed to reject proposed memory: ${error.message}`);
        }
    }

    // Regenerate last AI response
    regenerateLastMessage() {
        this.showConfirm(
            'Regenerate Response',
            'Are you sure you want to regenerate the last AI response? This will remove the last user and AI messages and start a new generation.',
            async (confirmRegen) => {
                if (!confirmRegen) return;
                
                try {
                    // Fetch session history to retrieve the last user message text
                    const histResponse = await this.fetchWithCsrf(`/sessions/${encodeURIComponent(this.currentSessionId)}/history`);
                    const histData = await histResponse.json();
                    
                    const messages = Array.isArray(histData.history) ? histData.history : [];
                    let lastUserMessageText = '';
                    
                    // Iterate backwards to find the last user message
                    for (let i = messages.length - 1; i >= 0; i--) {
                        if (messages[i].role === 'user') {
                            lastUserMessageText = messages[i].content;
                            break;
                        }
                    }
                    
                    if (!lastUserMessageText) {
                        this.showAlert("Regeneration Failed", "Could not find a user message in this session to regenerate.");
                        return;
                    }
                    
                    // Delete last message pair from database
                    const delResponse = await this.fetchWithCsrf(`/sessions/${encodeURIComponent(this.currentSessionId)}/messages/last`, {
                        method: 'DELETE'
                    });
                    
                    if (delResponse.ok) {
                        // Set input field to the last user message text and submit form
                        this.chatInput.value = lastUserMessageText;
                        // Reload conversation history view before submitting to clear deleted items visually
                        await this.loadHistory(this.currentSessionId);
                        this.chatForm.requestSubmit();
                    } else {
                        const data = await delResponse.json();
                        this.showAlert("Error", `Failed to delete previous messages: ${data.error}`);
                    }
                } catch (error) {
                    this.showAlert("Error", `Failed to regenerate response: ${error.message}`);
                }
            }
        );
    }
}

// Global instances registration
document.addEventListener('DOMContentLoaded', () => {
    window.localChatApp = new LocalChatApp();
});
