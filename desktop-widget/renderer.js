/**
 * Renderer Script - Widget frontend logic
 * Now with Eye Mode for proactive screen-aware assistance
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
let eyeModeEnabled = false;
let eyeModeInterval = null;
const EYE_MODE_INTERVAL_MS = 30000; // Analyze screen every 30 seconds

// Initialize
async function init() {
    try {
        backendUrl = await window.electronAPI.getBackendUrl();
        backendUrlInput.value = backendUrl;

        // Check Eye Mode state
        const eyeModeState = await window.electronAPI.getEyeMode();
        eyeModeEnabled = eyeModeState.enabled;
        updateEyeModeUI();

        if (eyeModeEnabled) {
            startEyeMode();
        }
    } catch (e) {
        console.error('Failed to initialize:', e);
    }

    // Listen for settings request
    window.electronAPI.onShowSettings(() => {
        showSettings();
    });

    // Create Eye Mode toggle button
    createEyeModeToggle();
}

// Create Eye Mode toggle button in header
function createEyeModeToggle() {
    const header = document.querySelector('.header');
    if (!header) return;

    const eyeBtn = document.createElement('button');
    eyeBtn.id = 'btnEyeMode';
    eyeBtn.className = 'icon-btn';
    eyeBtn.title = 'Toggle Eye Mode (AI sees your screen)';
    eyeBtn.innerHTML = '👁️';
    eyeBtn.style.opacity = eyeModeEnabled ? '1' : '0.5';

    eyeBtn.addEventListener('click', toggleEyeMode);

    // Insert before minimize button
    header.insertBefore(eyeBtn, btnMinimize);
}

// Update Eye Mode UI
function updateEyeModeUI() {
    const eyeBtn = document.getElementById('btnEyeMode');
    if (eyeBtn) {
        eyeBtn.style.opacity = eyeModeEnabled ? '1' : '0.5';
        eyeBtn.style.background = eyeModeEnabled ? 'rgba(74, 222, 128, 0.2)' : 'transparent';
    }
}

// Toggle Eye Mode
async function toggleEyeMode() {
    eyeModeEnabled = !eyeModeEnabled;
    await window.electronAPI.setEyeMode(eyeModeEnabled);
    updateEyeModeUI();

    if (eyeModeEnabled) {
        startEyeMode();
        addMessage('👁️ Eye Mode activated. I can now see your screen and offer proactive help.', 'assistant');
    } else {
        stopEyeMode();
        addMessage('👁️ Eye Mode deactivated.', 'assistant');
    }
}

// Start Eye Mode - periodic screen analysis
function startEyeMode() {
    if (eyeModeInterval) return;

    // Do an immediate analysis
    analyzeScreenAndRespond();

    // Set up periodic analysis
    eyeModeInterval = setInterval(analyzeScreenAndRespond, EYE_MODE_INTERVAL_MS);
}

// Stop Eye Mode
function stopEyeMode() {
    if (eyeModeInterval) {
        clearInterval(eyeModeInterval);
        eyeModeInterval = null;
    }
}

// Analyze screen and provide proactive response
async function analyzeScreenAndRespond() {
    if (!eyeModeEnabled || isLoading) return;

    try {
        // Capture screen
        const captureResult = await window.electronAPI.captureScreen();

        if (!captureResult.success) {
            console.error('Screen capture failed:', captureResult.error);
            return;
        }

        // Analyze with vision API
        const analysisResult = await window.electronAPI.analyzeScreen(
            captureResult.image_base64,
            captureResult.mime_type
        );

        if (analysisResult.success && analysisResult.suggestion) {
            // Show proactive suggestion
            showProactiveSuggestion(analysisResult.suggestion, captureResult.window_name);
        }
    } catch (error) {
        console.error('Eye Mode analysis error:', error);
    }
}

// Show proactive suggestion as a special message
function showProactiveSuggestion(suggestion, windowName) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant proactive';
    messageDiv.innerHTML = `
        <div class="proactive-header">
            <span class="eye-icon">👁️</span>
            <span class="context">Seeing: ${windowName || 'your screen'}</span>
        </div>
        <div class="proactive-content">${suggestion}</div>
    `;

    // Remove welcome message if present
    const welcome = messagesContainer.querySelector('.welcome-message');
    if (welcome) {
        welcome.remove();
    }

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
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
