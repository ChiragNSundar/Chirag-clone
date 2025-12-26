/**
 * AI Clone Bot - Main Application JavaScript
 */

// ===================================
// Configuration & State
// ===================================

const API_BASE = '';
let socket = null;
let currentSessionId = generateSessionId();
let currentTrainingContext = null;
let currentBotResponse = null;

// ===================================
// Utilities
// ===================================

function generateSessionId() {
    return 'session_' + Math.random().toString(36).substr(2, 9);
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function formatTime(date) {
    return new Date(date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Quota/error banner at top of page
let lastFailedAction = null;

function showQuotaError(retryCallback = null) {
    hideQuotaError();
    lastFailedAction = retryCallback;

    const banner = document.createElement('div');
    banner.id = 'quota-error-banner';
    banner.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: white;
        padding: 12px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    banner.innerHTML = `
        <span style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.2rem;">⚠️</span>
            <span>API quota exceeded. Please wait a moment and try again.</span>
        </span>
        <div style="display: flex; gap: 10px;">
            <button onclick="retryLastAction()" style="background: white; color: #ef4444; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600;">
                ↻ Retry
            </button>
            <button onclick="hideQuotaError()" style="background: transparent; color: white; border: 1px solid white; padding: 8px 16px; border-radius: 6px; cursor: pointer;">
                Dismiss
            </button>
        </div>
    `;
    document.body.prepend(banner);
}

function hideQuotaError() {
    const banner = document.getElementById('quota-error-banner');
    if (banner) banner.remove();
}

function retryLastAction() {
    hideQuotaError();
    if (lastFailedAction) {
        lastFailedAction();
    } else {
        // Default: retry training message
        sendTrainingMessage(true);
    }
}

// ===================================
// Socket Connection
// ===================================

function initSocket() {
    try {
        socket = io(window.location.origin, {
            transports: ['websocket', 'polling']
        });

        socket.on('connect', () => {
            console.log('🔌 Connected to server');
        });

        socket.on('disconnect', () => {
            console.log('🔌 Disconnected from server');
        });

        socket.on('chat_response', (data) => {
            hideTypingIndicator();
            addMessage(data.response, 'bot');
        });

        socket.on('error', (data) => {
            hideTypingIndicator();
            showToast(data.message || 'An error occurred', 'error');
        });

        socket.on('training_saved', () => {
            showToast('Training data saved!', 'success');
        });
    } catch (e) {
        console.log('WebSocket not available, using HTTP');
    }
}

// ===================================
// Chat Functions
// ===================================

function addMessage(text, sender, confidence = null) {
    const messagesContainer = document.getElementById('chat-messages');

    // Remove welcome message if present
    const welcome = messagesContainer.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`; // Changed from ${sender}-message to ${sender} to match existing CSS

    // Add confidence badge if available
    let confidenceHtml = '';
    if (confidence !== null && confidence !== undefined) {
        let badgeClass = 'low';
        if (confidence > 80) badgeClass = 'high';
        else if (confidence > 50) badgeClass = 'medium';

        confidenceHtml = `<span class="confidence-badge ${badgeClass}" title="Confidence Score">${confidence}%</span>`;
    }

    // Assuming formatMessage and timeAgo are defined elsewhere or will be added.
    // For now, using escapeHtml for text and formatTime for time.
    const avatar = sender === 'user' ? '👤' : '🤖';

    msgDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <p class="message-text">${escapeHtml(text)}</p>
            ${sender === 'bot' && confidence !== null ? `<div class="message-meta">${formatTime(new Date())} ${confidenceHtml}</div>` : `<div class="message-meta">${formatTime(new Date())}</div>`}
        </div>
    `;

    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function updateMood(moodData) {
    const icon = document.getElementById('bot-mood-icon');
    const text = document.getElementById('bot-mood-text');

    if (icon && text && moodData) {
        icon.textContent = moodData.emoji;
        text.textContent = moodData.mood.charAt(0).toUpperCase() + moodData.mood.slice(1);

        // Add animation
        icon.classList.add('bounce');
        setTimeout(() => icon.classList.remove('bounce'), 1000);
    }
}

function showTypingIndicator() {
    const messagesContainer = document.getElementById('chat-messages');

    const indicator = document.createElement('div');
    indicator.className = 'message bot typing-indicator';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="loading">
                <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `;

    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    // Add user message
    addMessage(message, 'user');
    input.value = '';
    input.style.height = 'auto';

    // Show typing indicator
    showTypingIndicator();

    try {
        // Try WebSocket first
        if (socket && socket.connected) {
            socket.emit('chat_message', {
                message: message,
                session_id: currentSessionId
            });
        } else {
            // Fallback to HTTP
            const response = await fetch(`${API_BASE}/api/chat/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: currentSessionId
                })
            });

            const data = await response.json();
            hideTypingIndicator();

            // Show the response even if there's an error (backend sends helpful messages)
            if (data.response) {
                addMessage(data.response, 'bot', data.confidence);
                if (data.mood) updateMood(data.mood);
            }

            if (data.error && !data.response) {
                showToast(data.error, 'error');
                addMessage('Sorry, I encountered an error. Please check your API configuration.', 'bot');
            }
        }
    } catch (error) {
        hideTypingIndicator();
        showToast('Failed to connect to server. Is it running?', 'error');
        addMessage('Could not reach the server. Please make sure the backend is running.', 'bot');
        console.error(error);
    }
}

function newChat() {
    currentSessionId = generateSessionId();
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">👋</div>
            <h2>Start a Conversation</h2>
            <p>Send a message to see how your AI clone responds. The more you train it, the more it sounds like you!</p>
        </div>
    `;
    showToast('Started new chat', 'success');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===================================
// Training Functions
// ===================================

async function sendTrainingMessage(regenerate = false) {
    const input = document.getElementById('training-input');
    const message = regenerate ? currentTrainingContext : input.value.trim();

    if (!message) return;

    const messagesContainer = document.getElementById('training-messages');

    // Remove welcome
    const welcome = messagesContainer.querySelector('.training-welcome');
    if (welcome) welcome.remove();

    // If not regenerating, add the context message
    if (!regenerate) {
        messagesContainer.innerHTML += `
            <div class="message user">
                <div class="message-content">
                    <p class="message-text">${escapeHtml(message)}</p>
                </div>
            </div>
        `;
        currentTrainingContext = message;
        input.value = '';
    } else {
        // Remove the last bot response for regeneration
        const lastBotMsg = messagesContainer.querySelector('.training-response:last-child');
        if (lastBotMsg) lastBotMsg.remove();
    }

    // Show loading
    messagesContainer.innerHTML += `
        <div class="message bot training-loading">
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="loading"><div class="loading-dots"><span></span><span></span><span></span></div></div>
            </div>
        </div>
    `;
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Get bot response with training_mode enabled
    try {
        const response = await fetch(`${API_BASE}/api/chat/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                session_id: 'training_' + Date.now(),
                training_mode: true  // Enable deep conversation mode
            })
        });

        const data = await response.json();

        // Remove loading
        const loading = messagesContainer.querySelector('.training-loading');
        if (loading) loading.remove();

        // Check for quota error
        if (data.error && data.error.toLowerCase().includes('quota')) {
            showQuotaError();
            return;
        }

        currentBotResponse = data.response;

        // Add bot response with feedback buttons (including regenerate)
        messagesContainer.innerHTML += `
            <div class="message bot training-response">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <p class="message-text">${escapeHtml(data.response)}</p>
                    <div class="feedback-buttons" style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn-primary" onclick="acceptTrainingResponse()" style="padding: 6px 12px; font-size: 0.8rem;">✓ Sounds like me</button>
                        <button class="btn-secondary" onclick="correctTrainingResponse()" style="padding: 6px 12px; font-size: 0.8rem;">✎ I'd say it differently</button>
                        <button class="btn-secondary" onclick="sendTrainingMessage(true)" style="padding: 6px 12px; font-size: 0.8rem; background: rgba(239,68,68,0.2); border-color: #ef4444;">↻ Try again</button>
                    </div>
                </div>
            </div>
        `;

        messagesContainer.scrollTop = messagesContainer.scrollHeight;

    } catch (error) {
        // Remove loading
        const loading = messagesContainer.querySelector('.training-loading');
        if (loading) loading.remove();
        showToast('Failed to get response', 'error');
    }
}

function acceptTrainingResponse() {
    if (!currentTrainingContext || !currentBotResponse) return;

    fetch(`${API_BASE}/api/training/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            context: currentTrainingContext,
            bot_response: currentBotResponse,
            accepted: true
        })
    }).then(() => {
        showToast('Response accepted! Bot learned from this.', 'success');
        removeFeedbackButtons();
        loadStats();
    }).catch(() => {
        showToast('Failed to save training data', 'error');
    });
}

function correctTrainingResponse() {
    // Show modal
    document.getElementById('modal-context').textContent = currentTrainingContext;
    document.getElementById('modal-bot-response').textContent = currentBotResponse;
    document.getElementById('correction-input').value = '';
    document.getElementById('feedback-modal').classList.add('active');
}

function submitCorrection() {
    const correction = document.getElementById('correction-input').value.trim();

    if (!correction) {
        showToast('Please enter your response', 'error');
        return;
    }

    fetch(`${API_BASE}/api/training/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            context: currentTrainingContext,
            correct_response: correction,
            accepted: false
        })
    }).then(() => {
        showToast('Thanks! Bot will learn from your correction.', 'success');
        closeModal();
        removeFeedbackButtons();
        loadStats();
    }).catch(() => {
        showToast('Failed to save correction', 'error');
    });
}

function removeFeedbackButtons() {
    const buttons = document.querySelector('.feedback-buttons');
    if (buttons) buttons.remove();
}

function closeModal() {
    document.getElementById('feedback-modal').classList.remove('active');
}

async function addExample() {
    const context = document.getElementById('example-context').value.trim();
    const response = document.getElementById('example-response').value.trim();

    if (!context || !response) {
        showToast('Both fields are required', 'error');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/training/example`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ context, response })
        });

        const data = await res.json();

        if (data.success) {
            showToast('Example added!', 'success');
            document.getElementById('example-context').value = '';
            document.getElementById('example-response').value = '';
            loadStats();
        } else {
            showToast(data.error || 'Failed to add example', 'error');
        }
    } catch (error) {
        showToast('Failed to add example', 'error');
    }
}

// ===================================
// Facts Functions
// ===================================

async function loadFacts() {
    try {
        const response = await fetch(`${API_BASE}/api/training/facts`);
        const data = await response.json();

        const factsList = document.getElementById('facts-list');

        if (data.facts && data.facts.length > 0) {
            factsList.innerHTML = data.facts.map((fact, index) => `
                <div class="fact-item">
                    <span>${escapeHtml(fact)}</span>
                    <button onclick="deleteFact(${index})">✕</button>
                </div>
            `).join('');
        } else {
            factsList.innerHTML = '<p class="empty-state">No facts added yet</p>';
        }
    } catch (error) {
        console.error('Failed to load facts:', error);
    }
}

async function addFact() {
    const input = document.getElementById('new-fact');
    const fact = input.value.trim();

    if (!fact) return;

    try {
        const response = await fetch(`${API_BASE}/api/training/fact`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fact })
        });

        const data = await response.json();

        if (data.success) {
            showToast('Fact added!', 'success');
            input.value = '';
            loadFacts();
            loadStats();
        } else {
            showToast(data.error || 'Failed to add fact', 'error');
        }
    } catch (error) {
        showToast('Failed to add fact', 'error');
    }
}

async function deleteFact(index) {
    try {
        const response = await fetch(`${API_BASE}/api/training/facts/${index}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast('Fact removed', 'success');
            loadFacts();
            loadStats();
        }
    } catch (error) {
        showToast('Failed to delete fact', 'error');
    }
}

// ===================================
// Upload Functions
// ===================================

function setupFileDrops() {
    setupFileDrop('wa-drop', 'wa-file', 'wa-upload-btn');
    setupFileDrop('dc-drop', 'dc-file', 'dc-upload-btn');
    setupFileDrop('ig-drop', 'ig-file', 'ig-upload-btn');
}

function setupFileDrop(dropId, fileId, buttonId) {
    const drop = document.getElementById(dropId);
    const file = document.getElementById(fileId);
    const button = document.getElementById(buttonId);

    drop.addEventListener('click', () => file.click());

    drop.addEventListener('dragover', (e) => {
        e.preventDefault();
        drop.classList.add('drag-over');
    });

    drop.addEventListener('dragleave', () => {
        drop.classList.remove('drag-over');
    });

    drop.addEventListener('drop', (e) => {
        e.preventDefault();
        drop.classList.remove('drag-over');

        if (e.dataTransfer.files.length) {
            file.files = e.dataTransfer.files;
            handleFileSelect(drop, file, button);
        }
    });

    file.addEventListener('change', () => {
        handleFileSelect(drop, file, button);
    });
}

function handleFileSelect(drop, file, button) {
    if (file.files.length) {
        drop.classList.add('has-file');
        drop.querySelector('span').textContent = `📄 ${file.files[0].name}`;
        button.disabled = false;
    }
}

async function uploadWhatsApp() {
    const file = document.getElementById('wa-file').files[0];
    const name = document.getElementById('wa-name').value.trim();

    if (!file || !name) {
        showToast('Please provide file and your name', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('your_name', name);

    await uploadFile('/api/upload/whatsapp', formData, 'WhatsApp');
}

async function uploadDiscord() {
    const file = document.getElementById('dc-file').files[0];
    const username = document.getElementById('dc-username').value.trim();

    if (!file || !username) {
        showToast('Please provide file and username', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('your_username', username);

    await uploadFile('/api/upload/discord', formData, 'Discord');
}

async function uploadInstagram() {
    const file = document.getElementById('ig-file').files[0];
    const username = document.getElementById('ig-username').value.trim();

    if (!file || !username) {
        showToast('Please provide file and username', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('your_username', username);

    await uploadFile('/api/upload/instagram', formData, 'Instagram');
}

async function uploadFile(endpoint, formData, platform) {
    const resultsDiv = document.getElementById('upload-results');

    resultsDiv.innerHTML = `
        <div class="upload-result">
            <div class="loading">
                <div class="loading-dots">
                    <span></span><span></span><span></span>
                </div>
                <span>Processing ${platform} data...</span>
            </div>
        </div>
    `;

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            resultsDiv.innerHTML = `
                <div class="upload-result success">
                    <h4>✓ ${platform} Import Successful!</h4>
                    <p>Processed ${data.total_messages} messages</p>
                    <p>Found ${data.your_messages} of your messages</p>
                    <p>Added ${data.training_examples_added} training examples</p>
                </div>
            `;
            showToast(`${platform} data imported!`, 'success');
            loadStats();
            loadProfile();
        } else {
            resultsDiv.innerHTML = `
                <div class="upload-result error">
                    <h4>✕ Import Failed</h4>
                    <p>${data.error || 'Unknown error'}</p>
                </div>
            `;
            showToast('Import failed', 'error');
        }
    } catch (error) {
        resultsDiv.innerHTML = `
            <div class="upload-result error">
                <h4>✕ Import Failed</h4>
                <p>Network error occurred</p>
            </div>
        `;
        showToast('Import failed', 'error');
    }
}

// ===================================
// Profile Functions
// ===================================

async function loadProfile() {
    try {
        const response = await fetch(`${API_BASE}/api/chat/personality`);
        const data = await response.json();

        // Set name
        document.getElementById('bot-name').value = data.name || '';

        // Quirks
        const quirksList = document.getElementById('quirks-list');
        if (data.typing_quirks && data.typing_quirks.length > 0) {
            quirksList.innerHTML = data.typing_quirks.map(q =>
                `<span class="quirk-tag">${escapeHtml(q)}</span>`
            ).join('');
        } else {
            quirksList.innerHTML = '<p class="empty-state">Upload some chats to detect your typing patterns</p>';
        }

        // Emojis
        const emojiUsage = document.getElementById('emoji-usage');
        if (data.emoji_patterns && Object.keys(data.emoji_patterns).length > 0) {
            emojiUsage.innerHTML = Object.entries(data.emoji_patterns)
                .slice(0, 10)
                .map(([emoji, count]) => `<span class="emoji-tag">${emoji}</span>`)
                .join('');
        } else {
            emojiUsage.innerHTML = '<p class="empty-state">No emoji patterns detected yet</p>';
        }

        // Tone bars
        const toneBars = document.getElementById('tone-bars');
        if (data.tone_markers) {
            toneBars.innerHTML = Object.entries(data.tone_markers).map(([name, value]) => `
                <div class="tone-bar">
                    <span class="tone-label">${name.charAt(0).toUpperCase() + name.slice(1)}</span>
                    <div class="tone-track">
                        <div class="tone-fill" style="width: ${value * 100}%"></div>
                    </div>
                </div>
            `).join('');
        }

    } catch (error) {
        console.error('Failed to load profile:', error);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/training/stats`);
        const data = await response.json();

        document.getElementById('total-examples').textContent = data.total_examples || 0;
        document.getElementById('stat-examples').textContent = data.total_examples || 0;
        document.getElementById('stat-facts').textContent = data.facts_count || 0;
        document.getElementById('stat-quirks').textContent = data.quirks_count || 0;

    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function saveName() {
    const name = document.getElementById('bot-name').value.trim();

    if (!name) {
        showToast('Please enter a name', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/chat/personality/name`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });

        const data = await response.json();

        if (data.success) {
            showToast('Name updated!', 'success');
        } else {
            showToast(data.error || 'Failed to update name', 'error');
        }
    } catch (error) {
        showToast('Failed to update name', 'error');
    }
}

// ===================================
// Tab Navigation
// ===================================

function setupTabs() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;

            // Update nav buttons
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update tab content
            tabContents.forEach(tab => {
                tab.classList.remove('active');
                if (tab.id === `${tabName}-tab`) {
                    tab.classList.add('active');
                }
            });

            // Load tab-specific data
            if (tabName === 'profile') {
                loadProfile();
            } else if (tabName === 'training') {
                loadFacts();
            }
        });
    });
}

// ===================================
// Event Listeners
// ===================================

function setupEventListeners() {
    // Chat
    document.getElementById('send-btn').addEventListener('click', sendMessage);
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    document.getElementById('chat-input').addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });

    document.getElementById('new-chat-btn').addEventListener('click', newChat);

    // Training
    document.getElementById('training-send-btn').addEventListener('click', sendTrainingMessage);
    document.getElementById('training-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendTrainingMessage();
    });

    document.getElementById('add-example-btn').addEventListener('click', addExample);
    document.getElementById('add-fact-btn').addEventListener('click', addFact);
    document.getElementById('new-fact').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') addFact();
    });

    // Upload
    document.getElementById('wa-upload-btn').addEventListener('click', uploadWhatsApp);
    document.getElementById('dc-upload-btn').addEventListener('click', uploadDiscord);
    document.getElementById('ig-upload-btn').addEventListener('click', uploadInstagram);

    // Profile
    document.getElementById('save-name-btn').addEventListener('click', saveName);

    // Modal
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('accept-response-btn').addEventListener('click', acceptTrainingResponse);
    document.getElementById('submit-correction-btn').addEventListener('click', submitCorrection);

    // Close modal on outside click
    document.getElementById('feedback-modal').addEventListener('click', (e) => {
        if (e.target.id === 'feedback-modal') closeModal();
    });
}

// ===================================
// Brain Map Visualizations
// ===================================

let personalityChart = null;

async function loadBrainMapData() {
    try {
        const response = await fetch(`${API_BASE}/api/visualization/data`);
        const data = await response.json();

        if (data.error) {
            console.error('Visualization error:', data.error);
            return;
        }

        // Render radar chart
        renderPersonalityRadar(data.radar);

        // Render word cloud
        renderWordCloud(data.wordCloud);

        // Render predictions
        await loadPredictions();

        // Update stats
        if (data.stats) {
            document.getElementById('viz-examples').textContent = data.stats.total_examples || 0;
            document.getElementById('viz-facts').textContent = data.stats.facts_count || 0;
            document.getElementById('viz-vocab').textContent = data.stats.vocabulary_size || 0;
            document.getElementById('viz-quirks').textContent = data.stats.quirks_count || 0;
        }

        // Render emojis
        if (data.emojis && data.emojis.length > 0) {
            document.getElementById('emoji-display').innerHTML = data.emojis
                .map(e => `<span class="emoji-item" title="Used ${e.count} times">${e.emoji}</span>`)
                .join('');
        }

        // Render quirks
        if (data.quirks && data.quirks.length > 0) {
            document.getElementById('quirks-display').innerHTML =
                '<div class="quirks-list">' +
                data.quirks.slice(0, 8).map(q => `<span class="quirk-tag">${q}</span>`).join('') +
                '</div>';
        }

    } catch (error) {
        console.error('Failed to load brain map:', error);
    }
}

function renderPersonalityRadar(radarData) {
    const ctx = document.getElementById('personality-radar');
    if (!ctx) return;

    if (personalityChart) {
        personalityChart.destroy();
    }

    personalityChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: radarData.labels,
            datasets: [{
                label: 'Your Personality',
                data: radarData.values,
                backgroundColor: 'rgba(139, 92, 246, 0.2)',
                borderColor: 'rgba(139, 92, 246, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(139, 92, 246, 1)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgba(139, 92, 246, 1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        stepSize: 20,
                        color: 'rgba(255,255,255,0.5)'
                    },
                    grid: {
                        color: 'rgba(255,255,255,0.1)'
                    },
                    angleLines: {
                        color: 'rgba(255,255,255,0.1)'
                    },
                    pointLabels: {
                        color: 'rgba(255,255,255,0.8)',
                        font: { size: 12 }
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderWordCloud(words) {
    const container = document.getElementById('word-cloud');
    if (!container || !words || words.length === 0) return;

    // Simple CSS-based word cloud
    const html = words.map(w => {
        const size = Math.max(12, Math.min(w.size, 48));
        const colors = ['#8b5cf6', '#06b6d4', '#ec4899', '#f59e0b', '#10b981'];
        const color = colors[Math.floor(Math.random() * colors.length)];
        return `<span class="cloud-word" style="font-size: ${size}px; color: ${color};">${w.text}</span>`;
    }).join(' ');

    container.innerHTML = html;
}

async function loadPredictions() {
    try {
        const response = await fetch(`${API_BASE}/api/visualization/predictions`);
        const data = await response.json();

        const container = document.getElementById('predictions-list');
        if (!container) return;

        if (data.predictions && data.predictions.length > 0) {
            container.innerHTML = data.predictions.map(p => `
                <div class="prediction-item">
                    <span class="prediction-category">${p.category}</span>
                    <p class="prediction-text">${p.prediction}</p>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${p.confidence}%"></div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p class="empty-state">Train more to unlock predictions!</p>';
        }
    } catch (error) {
        console.error('Failed to load predictions:', error);
    }
}

// ===================================
// Autopilot
// ===================================

async function loadAutopilotStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/autopilot/status`);
        const data = await response.json();

        // Update Discord status
        const discordStatus = document.getElementById('discord-status');
        if (data.discord) {
            const dotClass = data.discord.running ? 'online' : (data.discord.configured ? 'standby' : 'offline');
            const statusText = data.discord.running ? 'Running' : (data.discord.configured ? 'Ready' : 'Not configured');
            discordStatus.innerHTML = `<span class="status-dot ${dotClass}"></span><span>${statusText}</span>`;

            document.getElementById('discord-dms-toggle').checked = data.discord.auto_reply_dms;
            document.getElementById('discord-mentions-toggle').checked = data.discord.auto_reply_mentions;
            document.getElementById('discord-start-btn').textContent = data.discord.running ? 'Stop' : 'Start Discord Bot';
        }

        // Update Telegram status
        const telegramStatus = document.getElementById('telegram-status');
        if (data.telegram) {
            const dotClass = data.telegram.running ? 'online' : (data.telegram.configured ? 'standby' : 'offline');
            const statusText = data.telegram.running ? 'Running' : (data.telegram.configured ? 'Ready' : 'Not configured');
            telegramStatus.innerHTML = `<span class="status-dot ${dotClass}"></span><span>${statusText}</span>`;

            document.getElementById('telegram-toggle').checked = data.telegram.auto_reply_enabled;
            document.getElementById('telegram-start-btn').textContent = data.telegram.running ? 'Stop' : 'Start Telegram Bot';
        }
    } catch (error) {
        console.error('Failed to load autopilot status:', error);
    }
}

async function loadAutopilotLogs() {
    try {
        const response = await fetch(`${API_BASE}/api/autopilot/logs`);
        const data = await response.json();

        const container = document.getElementById('autopilot-log-list');
        if (data.logs && data.logs.length > 0) {
            container.innerHTML = data.logs.map(log => `
                <div class="log-item">
                    <span class="log-platform">${log.platform}</span>
                    <span class="log-user">${log.user}</span>
                    <p class="log-message">"${log.message}"</p>
                    <p class="log-response">→ "${log.response}"</p>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to load logs:', error);
    }
}

async function toggleDiscordBot() {
    const btn = document.getElementById('discord-start-btn');
    const isStop = btn.textContent.includes('Stop');

    const endpoint = isStop ? '/api/autopilot/discord/stop' : '/api/autopilot/discord/start';
    await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });

    setTimeout(loadAutopilotStatus, 500);
}

async function toggleTelegramBot() {
    const btn = document.getElementById('telegram-start-btn');
    const isStop = btn.textContent.includes('Stop');

    const endpoint = isStop ? '/api/autopilot/telegram/stop' : '/api/autopilot/telegram/start';
    await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });

    setTimeout(loadAutopilotStatus, 500);
}

// ===================================
// Timeline
// ===================================

async function loadTimeline() {
    try {
        // Load insights first
        const insightsRes = await fetch(`${API_BASE}/api/timeline/insights`);
        const insightsData = await insightsRes.json();

        const insightsContainer = document.getElementById('timeline-insights');
        if (insightsData.insights && insightsData.insights.length > 0) {
            insightsContainer.innerHTML = insightsData.insights.map(insight => `
                <div class="insight-card">
                    <span class="insight-icon">${insight.icon}</span>
                    <div class="insight-content">
                        <h4>${insight.title}</h4>
                        <p>${insight.description}</p>
                    </div>
                </div>
            `).join('');
        }

        // Load timeline memories
        const timelineRes = await fetch(`${API_BASE}/api/timeline/memories?days=30`);
        const timelineData = await timelineRes.json();

        const container = document.getElementById('timeline-list');
        if (timelineData.timeline && timelineData.timeline.length > 0) {
            container.innerHTML = timelineData.timeline.map(day => `
                <div class="timeline-day">
                    <div class="timeline-date">${formatDate(day.date)}</div>
                    <div class="timeline-count">${day.count} memories</div>
                    <div class="timeline-memories">
                        ${day.memories.slice(0, 3).map(m => `
                            <span class="memory-chip">${m.type}: ${m.content.substring(0, 30)}...</span>
                        `).join('')}
                    </div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to load timeline:', error);
    }
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ===================================
// Analytics & Backup
// ===================================

async function loadAnalyticsDashboard() {
    try {
        const response = await fetch(`${API_BASE}/api/analytics/dashboard`);
        const data = await response.json();

        // Update stats
        document.getElementById('analytics-conversations').textContent = data.total_conversations || 0;
        document.getElementById('analytics-response-time').textContent = `${data.avg_response_time_ms || 0}ms`;
        document.getElementById('analytics-confidence').textContent = `${data.avg_confidence || 0}%`;
        document.getElementById('analytics-peak-hour').textContent = data.peak_hour !== undefined ? `${data.peak_hour}:00` : '--';

        // Update topics
        const topicsContainer = document.getElementById('analytics-topics');
        if (data.top_topics && data.top_topics.length > 0) {
            topicsContainer.innerHTML = data.top_topics.map(t =>
                `<span class="topic-chip">${t.topic} (${t.count})</span>`
            ).join('');
        }
    } catch (error) {
        console.error('Failed to load analytics:', error);
    }
}

async function loadBackups() {
    try {
        const response = await fetch(`${API_BASE}/api/analytics/backups`);
        const data = await response.json();

        const container = document.getElementById('backup-list');
        if (data.backups && data.backups.length > 0) {
            container.innerHTML = data.backups.map(b => `
                <div class="backup-item">
                    <span class="backup-name">${b.name}</span>
                    <span class="backup-date">${new Date(b.created_at).toLocaleDateString()}</span>
                    <button class="btn-small" onclick="restoreBackup('${b.name}')">Restore</button>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to load backups:', error);
    }
}

async function createBackup() {
    try {
        showToast('Creating backup...', 'info');
        const response = await fetch(`${API_BASE}/api/analytics/backup`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('Backup created successfully!', 'success');
            loadBackups();
        } else {
            showToast('Backup failed: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Backup error', 'error');
    }
}

async function exportPersonality() {
    try {
        const response = await fetch(`${API_BASE}/api/analytics/export`);
        const data = await response.json();

        if (data.success) {
            // Download as JSON
            const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'personality_export.json';
            a.click();
            showToast('Personality exported!', 'success');
        }
    } catch (error) {
        showToast('Export failed', 'error');
    }
}

async function restoreBackup(name) {
    if (!confirm(`Restore backup "${name}"? This will replace current data.`)) return;

    try {
        const response = await fetch(`${API_BASE}/api/analytics/restore/${name}`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('Backup restored! Please refresh the page.', 'success');
        } else {
            showToast('Restore failed: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Restore error', 'error');
    }
}

// ===================================
// Initialize
// ===================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('AI Clone Bot initialized');

    initSocket();
    setupTabs();
    setupEventListeners();
    setupFileDrops();

    // Load initial data
    loadStats();
    loadFacts();

    // Load brain map and timeline when tab is clicked
    document.querySelector('[data-tab="brainmap"]')?.addEventListener('click', () => {
        setTimeout(() => {
            loadBrainMapData();
            loadTimeline();
        }, 100);
    });

    // Load autopilot status when tab is clicked
    document.querySelector('[data-tab="autopilot"]')?.addEventListener('click', () => {
        setTimeout(() => {
            loadAutopilotStatus();
            loadAutopilotLogs();
        }, 100);
    });

    // Load analytics when profile tab is clicked
    document.querySelector('[data-tab="profile"]')?.addEventListener('click', () => {
        setTimeout(() => {
            loadAnalyticsDashboard();
            loadBackups();
        }, 100);
    });

    // Autopilot button listeners
    document.getElementById('discord-start-btn')?.addEventListener('click', toggleDiscordBot);
    document.getElementById('telegram-start-btn')?.addEventListener('click', toggleTelegramBot);

    // Backup button listeners
    document.getElementById('create-backup-btn')?.addEventListener('click', createBackup);
    document.getElementById('export-personality-btn')?.addEventListener('click', exportPersonality);
});
