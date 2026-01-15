/**
 * Renderer Script - Widget frontend logic
 */

// DOM Elements
const messagesContainer = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const btnMinimize = document.getElementById('btnMinimize');
const btnClose = document.getElementById('btnClose');
const settingsPanel = document.getElementById('settingsPanel');
const backendUrlInput = document.getElementById('backendUrl');
const saveSettingsBtn = document.getElementById('saveSettings');
const cancelSettingsBtn = document.getElementById('cancelSettings');

// State
let backendUrl = 'http://localhost:8000';
let sessionId = 'widget_' + Math.random().toString(36).substr(2, 9);
let isLoading = false;

// Initialize
async function init() {
    try {
        backendUrl = await window.electronAPI.getBackendUrl();
        backendUrlInput.value = backendUrl;
    } catch (e) {
        console.error('Failed to get backend URL:', e);
    }

    // Listen for settings request
    window.electronAPI.onShowSettings(() => {
        showSettings();
    });
}

// Add message to UI
function addMessage(content, role) {
    // Remove welcome message if present
    const welcome = messagesContainer.querySelector('.welcome-message');
    if (welcome) {
        welcome.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.textContent = content;
    messagesContainer.appendChild(messageDiv);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return messageDiv;
}

// Add loading indicator
function addLoadingIndicator() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant loading';
    loadingDiv.id = 'loadingIndicator';
    loadingDiv.innerHTML = `
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
    `;
    messagesContainer.appendChild(loadingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return loadingDiv;
}

// Remove loading indicator
function removeLoadingIndicator() {
    const loading = document.getElementById('loadingIndicator');
    if (loading) {
        loading.remove();
    }
}

// Send message to backend
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || isLoading) return;

    isLoading = true;
    sendBtn.disabled = true;
    messageInput.value = '';

    // Add user message
    addMessage(message, 'user');

    // Show loading
    addLoadingIndicator();

    try {
        const response = await fetch(`${backendUrl}/api/chat/message`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId,
                training_mode: false
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        removeLoadingIndicator();
        addMessage(data.response, 'assistant');

    } catch (error) {
        console.error('Chat error:', error);
        removeLoadingIndicator();
        addMessage(`⚠️ Connection error. Is the backend running at ${backendUrl}?`, 'assistant');
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

// Settings
function showSettings() {
    backendUrlInput.value = backendUrl;
    settingsPanel.classList.add('visible');
}

function hideSettings() {
    settingsPanel.classList.remove('visible');
}

async function saveSettings() {
    const newUrl = backendUrlInput.value.trim();
    if (newUrl) {
        backendUrl = newUrl;
        await window.electronAPI.setBackendUrl(newUrl);
    }
    hideSettings();
}

// Event Listeners
sendBtn.addEventListener('click', sendMessage);

messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

btnMinimize.addEventListener('click', () => {
    window.electronAPI.minimizeWindow();
});

btnClose.addEventListener('click', () => {
    window.electronAPI.closeWindow();
});

saveSettingsBtn.addEventListener('click', saveSettings);
cancelSettingsBtn.addEventListener('click', hideSettings);

// Escape to close settings
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && settingsPanel.classList.contains('visible')) {
        hideSettings();
    }
});

// Initialize on load
init();
