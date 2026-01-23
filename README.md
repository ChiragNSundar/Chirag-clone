# 🧠 Chirag Clone - Personal Digital Twin

![Version](https://img.shields.io/badge/version-3.0.1-blue.svg)
![Status](https://img.shields.io/badge/status-production--ready-green.svg)
![Coverage](https://img.shields.io/badge/coverage-88%25-green.svg)
![Auth](https://img.shields.io/badge/auth-OAuth2-orange.svg)

**I am Chirag's digital brain.** A continuously learning AI system that evolves to mimic my personality, knowledge, and communication style.

---

## 🛠️ Tech Stack

### Frontend

- **Framework**: React 19 + Vite
- **Styling**: Tailwind CSS (Glassmorphism design)
- **Icons**: Lucide React
- **3D Avatar**: Three.js + React Three Fiber
- **Visualization**: Recharts + Web Audio API
- **State/Animations**: Framer Motion
- **PWA**: Vite PWA Plugin (installable, offline-capable)
- **Testing**: Vitest + Playwright E2E

### Backend

- **Framework**: FastAPI (Python 3.11)
- **AI/LLM**: Google Gemini 2.0 Flash (Primary), OpenAI (Fallback)
- **Robustness**: Circuit Breakers + Rate Limiting + Model Fallback
- **Vector DB**: ChromaDB (Local persistence)
- **Real-Time**: WebSockets for Voice & Vision
- **Auth**: OAuth2 (Google) + JWT + Admin Access Control
- **Task Management**: AsyncIO + APScheduler
- **PDF/Web Processing**: PyMuPDF + BeautifulSoup

### Security

- **Protection**: Prompt Guard + Content Security Policy (CSP)
- **Validation**: Pydantic v2 Strict Models

### Desktop Widget

- **Framework**: Electron
- **Features**: Floating window, screen capture (Eye Mode), global shortcuts

### DevOps & Infrastructure

- **Containerization**: Docker + Docker Compose (v2.3)
- **Server**: Uvicorn (ASGI)
- **Environment**: Dotenv (.env) management
- **Linting**: Pre-commit hooks (Black, Prettier, ESLint)
- **Code Quality**: Husky + lint-staged (auto-fix on commit)

---

## ✨ Key Features

### 🔐 Security & Auth (v2.6)

- **OAuth2 Login**: Secure Google social login flow.
- **Admin Access Control**: Training center restricted to authorized admins (`chiragns12@gmail.com`).
- **JWT Authentication**: Stateless, secure interactions.

### 🎙️ Duplex Voice (v2.6)

- **Barge-in Support**: Interrupt the bot mid-sentence naturally.
- **VAD Integration**: Intelligent Voice Activity Detection using WebRTC.

### 🛡️ Production Grade (v2.5)

- **Circuit Breakers**: Prevents cascading failures when APIs (OpenAI/ElevenLabs) are down.
- **Hybrid RAG**: Combines Semantic Search (Vector) + Keyword Search (BM25) with Reciprocal Rank Fusion.
- **Prompt Guard**: 5-level threat detection against prompt injection and jailbreaks.
- **Model Fallback**: Automatic failover (Gemini → GPT-4o → Local Llama) to ensure 24/7 uptime.

### 🚀 Frontier Capabilities (v2.9)

- **Voice Cloning Studio**: Clone your own voice directly from the UI (ElevenLabs integration).
- **Agentic Web Browsing**: Bot can autonomously navigate websites, read content, and take screenshots.
- **GraphRAG**: Uses Knowledge Graphs for structured, multi-hop reasoning on your documents.
- **Local Fine-Tuning**: Export your digital twin's "Brain" and fine-tune a local LLM.

### 🌟 Advanced Intelligence (v2.4)

- **Deep Research**: Autonomous multi-step web research with source citation.
- **Rewind Memory**: Temporal screen recording analysis ("What was I looking at?").
- **Local Voice**: Offline-first TTS/STT with `faster-whisper` and `piper-tts`.
- **Command Palette (⌘K)**: Quick navigation and actions.

### 🎙️ Real-Time Voice Conversation (`/chat`)

**NEW in v2.3!** Talk to your clone naturally with ultra-low latency.

- **WebSocket Streaming**: Bidirectional audio streaming for instant responses.
- **Visualizer**: Real-time frequency bars (Orb/Wave modes) reacting to your voice.
- **Interruption**: Speak anytime to interrupt the bot, just like a real call.
- **Turn-taking**: Smart silence detection to know when you've finished speaking.

### 👁️ Desktop Vision "Eye Mode"

**NEW in v2.3!** Your clone sees what you see.

- **Screen Awareness**: Toggle "Eye Mode" in the desktop widget.
- **Proactive Suggestions**: The bot watches your active window and offers relevant tips.
- **Privacy-First**: Only captures the active window, never the full desktop.

### 🧠 Brain Station (`/training`)

**NEW in v2.3!** Central command for knowledge management.

- **Knowledge Graph**: Interactive 3D visualization of your clone's memory.
- **Drag-and-Drop**: Upload PDFs, text files, and markdown notes.
- **URL Ingestion**: Feed it web pages to learn from instantly.
- **Semantic Search**: Find any fact or document with natural language queries.

### 🚀 v3.0 Features (New!)

#### 🧠 Cognitive Upgrades

- **Notion Sync**: Connect your Notion workspace to the Brain Station for automatic knowledge ingestion.
- **Daily Briefing**: Get morning audio briefings covering your calendar, drafts, and system stats.
- **Memory Garden**: Edit and merge core memories directly.

#### 🎙️ Voice & Autopilot

- **Wake Word**: Say "Hey Chirag" to activate listening mode (powered by `openWakeWord`).
- **Calendar Agent**: The bot can now negotiate meeting times, and create/update/delete events.
- **Slack Integration**: Auto-draft replies for DMs and thread mentions.

### 🏛️ Training Center

- **Chat Uploads**: Learn from WhatsApp, Instagram, Discord archives.
- **Interactive Training**: "Interview mode" where the bot asks you questions.
- **Journal**: Daily thought recording and reflection.
- **Facts**: Manual entry for key personal details.
- **Export/Import Brain**: Backup and transfer all learned data as portable JSON.

### 🤖 Social Autopilot (`/autopilot`)

Handle your socials while you sleep:

- **Slack**: Auto-drafts professional replies and summarizes threads.
- **Discord/Telegram**: Smart auto-replies to DMs.
- **Twitter/LinkedIn**: Draft tweets and professional replies in your style.
- **Gmail**: Voice-to-email drafting.
- **Review Workflow**: Nothing is posted without your approval.

---

## 🏗️ Architecture

### System Overview

```mermaid
graph TD
    User["User (You)"] -->|Web UI| Frontend["Frontend (React + Vite)"]
    User -->|Desktop| Widget["Desktop Widget (Electron)"]
    
    subgraph "Frontend Layer"
        Frontend --> Dashboard["Analytics Dashboard"]
        Frontend --> Training["Training Center + Brain Station"]
        Frontend --> Chat["Voice Chat + Visualizer"]
        Frontend --> Command["Command Palette (⌘K)"]
    end
    
    Widget -->|WebSocket| Backend
    Frontend -->|WebSocket/API| Backend["Backend (FastAPI)"]
    
    subgraph "Backend Architecture"
        Backend --> Middle["Middleware (Security, Rate Limit)"]
        Middle --> Router["Refactored API Routers"]
        
        subgraph "Router Modules"
            Router --> R_Auth["Auth"]
            Router --> R_Chat["Chat"]
            Router --> R_Voice["Voice"]
            Router --> R_Know["Knowledge"]
            Router --> R_Auto["Autopilot"]
            Router --> R_Vis["Vision"]
        end

        subgraph "Services Layer"
            R_Auth --> Auth["Auth Service"]
            R_Chat --> Fallback["Model Fallback (Gemini/OpenAI)"]
            
            R_Know --> RAG["Hybrid RAG Service"]
            RAG --> Chroma["ChromaDB (or Mock)"]
            RAG --> Redis["Redis Cache"]
            
            R_Voice --> Realtime["Realtime Voice Service"]
            R_Auto --> Social["Social Autopilot"]
            R_Vis --> Vision["Vision Service"]
        end
    end
```

### Real-Time Voice Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend (VoiceChat)
    participant W as WebSocket
    participant S as RealtimeService
    participant L as LLM
    
    U->>F: Speaks (Audio Stream)
    F->>W: Send Audio Chunks
    W->>S: Transcribe Stream (Whisper)
    S->>S: Detect Silence/Turn End
    S->>L: Update Conversation Context
    L-->>S: Generate Token Stream
    S->>W: Send Text + Audio Stream (TTS)
    W->>F: Play Audio + Visualize
    F-->>U: Hear Response
    
    Note over U,F: User can interrupt at any time
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites

- Docker Desktop installed
- [Gemini API Key](https://makersuite.google.com/app/apikey)
- [ElevenLabs API Key](https://elevenlabs.io) (for voice)

### 2. Setup & Run (Recommended)

One command to start everything:

```bash
# 1. Clone & Config
git clone https://github.com/ChiragNSundar/Chirag-clone.git
cd Chirag-clone
cp .env.example .env

# 2. Add API Keys to .env
# GEMINI_API_KEY=...
# ELEVENLABS_API_KEY=...

# 3. Install Dependencies
# This script installs both Python and Node.js dependencies automatically
python install_deps.py

# 4. Start Backend (Terminal 1)
cd backend
python3 main.py
# The server will start on http://localhost:8000

# 5. Start Frontend (Terminal 2)
# Open a new terminal window/tab
cd frontend-react
npm run dev
# The app will be available at http://localhost:5173
```

- **Frontend**: <http://localhost:5173>
- **Backend API**: <http://localhost:8000>

### Option 2: Docker Environment (Isolated)

If you prefer running in containers:

```bash
docker-compose up -d --build
```

- **Frontend**: <http://localhost:5173>
- **Backend API**: <http://localhost:8000>

### 3. Desktop Widget (Optional)

For the "Eye Mode" feature:

```bash
cd desktop-widget
npm install
npm start
```

### 4. Running Tests

**Frontend Unit Tests (Vitest):**

```bash
cd frontend-react

# Run all tests once
npm run test:run

# Watch mode (re-run on file changes)
npm run test

# With coverage report
npm run test:run -- --coverage
```

**Backend Tests (Pytest):**

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_auth.py -v

# With coverage
pytest tests/ --cov=services --cov-report=term-missing
```

**E2E Tests (Playwright):**

```bash
cd frontend-react

# Install Playwright browsers (first time)
npx playwright install

# Run E2E tests
npx playwright test

# Run with UI mode
npx playwright test --ui
```

**Code Quality (Pre-commit):**

```bash
cd frontend-react

# Initialize Husky (first time after clone)
npm run prepare

# Lint check
npm run lint

# Format check
npm run format
```

---

## 📁 Project Structure

```text
Chirag-clone/
├── .env                        # Environment Config (Secrets)
├── .pre-commit-config.yaml     # Linting Config
├── pyproject.toml              # Python Config
├── requirements.txt            # Python Dependencies
├── install_deps.py             # Robust Installer (NEW)
├── docker-compose.yml          # Container Orchestration
├── Dockerfile                  # Production Build Definition
├── CHANGELOG.md                # Project History
├── README.md                   # Documentation
├── testing.md                  # Testing Guide
│
├── backend/
│   ├── main.py                 # FastAPI Application Application & Router Registration
│   ├── config.py               # Configuration Settings
│   ├── gunicorn.conf.py        # Gunicorn Config
│   │
│   ├── routes/                 # Modular API Routes (v2.7)
│   │   ├── auth.py             # OAuth2 Routes
│   │   ├── chat.py             # Chat & Messaging
│   │   ├── training.py         # Training Center
│   │   ├── dashboard.py        # Analytics & Health
│   │   ├── autopilot.py        # Social Bots
│   │   ├── voice.py            # Real-time Voice
│   │   ├── cognitive.py        # Active Learning
│   │   ├── knowledge.py        # RAG & Documents
│   │   ├── vision.py           # Eye Mode
│   │   └── features.py         # Miscellaneous
│   │
│   ├── services/               # Business Logic Microservices
│   │   ├── accuracy_service.py     # Verification Logic
│   │   ├── active_learning_service.py # Proactive Questioning
│   │   ├── analytics_service.py    # Dashboard Metrics
│   │   ├── async_job_service.py    # Background Tasks
│   │   ├── auth_service.py         # OAuth2 & JWT Logic
│   │   ├── avatar_service.py       # 3D Avatar Logic
│   │   ├── backup_service.py       # Data Backup
│   │   ├── cache_service.py        # Redis/Local Cache
│   │   ├── calendar_service.py     # Google Calendar Integration
│   │   ├── chat_service.py         # Main Conversation Logic
│   │   ├── circuit_breaker.py      # Fault Tolerance
│   │   ├── conversation_analytics_service.py # Topic/Heatmap Analysis
│   │   ├── core_memory_service.py  # Long-term Memory Summarization
│   │   ├── creative_service.py     # Dreams/Poems/Stories Engine
│   │   ├── deep_research.py        # Autonomous Research Agent
│   │   ├── discord_bot_service.py  # Discord Integration
│   │   ├── emotion_service.py      # Sentiment Analysis
│   │   ├── gmail_bot_service.py    # Gmail Integration
│   │   ├── http_pool.py            # Connection Pooling
│   │   ├── hybrid_rag.py           # BM25 + Semantic Search
│   │   ├── knowledge_service.py    # RAG/Document/Brain Station
│   │   ├── learning_service.py     # Training Logic
│   │   ├── linkedin_bot_service.py # LinkedIn Integration
│   │   ├── llm_service.py          # Gemini/OpenAI Wrapper
│   │   ├── logger.py               # Structured Logging
│   │   ├── memory_search_service.py # Advanced Vector Search
│   │   ├── memory_service.py       # Vector DB Wrapper (Mock supported)
│   │   ├── middleware.py           # Legacy Middleware
│   │   ├── model_fallback.py       # LLM Cascade Fallback
│   │   ├── mood_service.py         # Emotional State
│   │   ├── personality_history_service.py # Personality Drift Tracking
│   │   ├── personality_service.py  # Identity Management
│   │   ├── prompt_guard.py         # Injection Protection
│   │   ├── rate_limiter.py         # API Throttling
│   │   ├── realtime_voice_service.py # WebSocket Visualizer/Voice
│   │   ├── rewind_service.py       # Screen Memory
│   │   ├── scheduler_service.py    # Cron Jobs
│   │   ├── search_service.py       # Web Search
│   │   ├── telegram_bot_service.py # Telegram Integration
│   │   ├── thinking_service.py     # Recursive Thinking (CoT)
│   │   ├── twitter_bot_service.py  # Twitter/X Integration
│   │   ├── vision_service.py       # Image/Screen Analysis
│   │   ├── voice_service.py        # TTS/STT (ElevenLabs/Whisper)
│   │   └── whatsapp_bot_service.py # WhatsApp Integration
│   │
│   ├── middleware/             # Middleware Layer
│   │   └── security.py         # CSP & Sanitization
│   │
│   ├── models/                 # Pydantic Schemas
│   │   └── validation.py       # Request Validation
│   │
│   ├── migrations/             # Database Migrations
│   │   └── versions/
│   │
│   ├── parsers/                # Chat Parsers
│   │   ├── discord_parser.py
│   │   ├── instagram_parser.py
│   │   ├── smart_parser.py     # Heuristic/LLM Parser
│   │   └── whatsapp_parser.py
│   │
│   ├── tests/                  # Backend Tests
│   │   ├── conftest.py         # Test Fixtures
│   │   ├── test_auth.py        # Auth & Security Tests
│   │   ├── test_circuit_breaker.py
│   │   ├── test_deep_research.py
│   │   ├── test_hybrid_rag.py  # RAG Logic
│   │   ├── test_integration.py # E2E API Tests
│   │   ├── test_llm.py         # LLM Wrapper Tests
│   │   ├── test_local_voice.py # Offline Voice Tests
│   │   ├── test_main.py        # Core Routes
│   │   ├── test_parsers.py     # Chat Parsing
│   │   ├── test_prompt_guard.py # Security Guardrails
│   │   ├── test_rewind.py      # Screen Memory
│   │   ├── test_services.py    # Service Logic
│   │   ├── test_voice.py       # Realtime Voice
│   │   └── test_export_import.py # Brain Export/Import (NEW)
│   └── data/                   # Local Storage (Excluded from Git)
│
├── frontend-react/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── tsconfig.json
│   │
│   └── src/
│       ├── main.tsx            # React Entry Point
│       ├── App.tsx             # Routing & Layout
│       ├── index.css           # Global Styles
│       │
│       ├── components/         # React Components
│       │   ├── AudioVisualizer.tsx # Web Audio API Viz
│       │   ├── AutopilotPage.tsx   # Bot Control Dashboard
│       │   ├── Avatar3D.tsx        # 3D Avatar with Lip-Sync
│       │   ├── ChatInterface.tsx   # Main Chat UI + Avatar
│       │   ├── CommandPalette.tsx  # Quick Actions
│       │   ├── Dashboard.tsx       # Analytics Home
│       │   ├── ErrorBoundary.tsx   # React Error Boundary
│       │   ├── Layout.tsx          # Navigation Wrapper
│       │   ├── LoginPage.tsx       # Social Login
│       │   ├── MemoryGraph.tsx     # Interactive Knowledge Graph
│       │   ├── ProfilePage.tsx     # Bot Profile Settings
│       │   ├── SettingsPanel.tsx   # Preferences & Theme
│       │   ├── Skeleton.tsx        # Loading States
│       │   ├── ThinkingBubble.tsx  # CoT Visualization
│       │   ├── Toast.tsx           # Notifications
│       │   ├── TrainingCenter.tsx  # Brain Station + Training
│       │   ├── VoiceChat.tsx       # Live Voice Streaming
│       │   │
│       │   ├── __tests__/          # Component Tests
│       │   │   ├── Dashboard.test.tsx
│       │   │   ├── LoginPage.test.tsx
│       │   │   └── VoiceChat.test.tsx
│       │
│       ├── hooks/              # Custom React Hooks
│       ├── services/           # Frontend Services (API)
│       ├── utils/              # Utilities
│       └── e2e/                # Playwright Tests
│
└── desktop-widget/             # Electron App
    ├── main.js
    ├── preload.js
    ├── index.html
    └── renderer.js
```

## API Reference

### Health & System

- `GET /api/health`: System status, version, and service health checks (supports `?detailed=true`).
- `GET /api/system/metrics`: Cache stats, memory usage, connection pool status.
- `GET /api/profile`: Get the bot's personality profile and stats.

### 🧠 Brain Station (Knowledge)

- `GET /api/knowledge/stats`: Knowledge base statistics.
- `GET /api/knowledge/documents`: List indexed documents.
- `POST /api/knowledge/upload`: Upload PDF/TXT/MD files.
- `POST /api/knowledge/text`: Ingest raw text facts.
- `POST /api/knowledge/url`: Ingest content from a URL.
- `POST /api/knowledge/query`: Semantic search against the knowledge base.
- `DELETE /api/knowledge/document/{doc_id}`: Remove a document.

### 🎙️ Real-Time Voice

- `GET /api/voice/status`: Check TTS/STT service availability.
- `WS /api/voice/stream`: Bidirectional WebSocket for low-latency voice chat.
- `GET /api/voice/realtime/status/{session_id}`: Check status of a voice session.
- `POST /api/voice/listen`: Upload audio blob for transcription (STT).
- `POST /api/voice/speak`: Generate audio from text (TTS).
- `GET /api/voice/voices`: List available voice models.

### 👁️ Desktop Vision

- `POST /api/vision/desktop`: "Eye Mode" - Analyze active window content.
- `POST /api/vision/analyze`: General image analysis endpoint.

### 💬 Chat & Conversation

- `POST /api/chat/message`: Main conversation endpoint (with memory).
- `GET /api/visualization/graph`: Interactive memory graph data.
- `GET /api/dashboard/stats`: Dashboard analytics.
- `GET /api/analytics/conversations`: Conversation history.
- `GET /api/analytics/topics`: Topic clusters and heatmaps.
- `GET /api/creative/types`: Available creative modes (poems, dreams, etc).
- `POST /api/creative/generate`: Generate creative content.
- `GET /api/creative/prompt`: Get current creative prompt.
- `GET /api/drafts/all`: List all pending drafts from all platforms.
- `GET /api/analytics/detailed`: Detailed system analytics.

### 🧩 Cognitive Services

- `GET /api/cognitive/core-memories`: List long-term core memories.
- `POST /api/cognitive/trigger-summarization`: Force memory summarization.
- `GET /api/cognitive/active-learning/suggestions`: Get proactive questions.
- `POST /api/cognitive/active-learning/answer`: Answer a proactive question.
- `GET /api/memory/search`: Vector search debugging.
- `GET /api/memory/stats`: Vector database statistics.
- `GET /api/accuracy/quiz`: Generate a self-test quiz.
- `GET /api/accuracy/stats`: Retrieval accuracy metrics.
- `POST /api/accuracy/submit`: Submit quiz answers.
- `POST /api/personality/snapshot`: Save current personality state.
- `GET /api/personality/history`: Track personality changes over time.
- `GET /api/personality/evolution`: Personality evolution metrics.
- `GET /api/cognitive/learning-stats`: Learning progress statistics.

### 📅 Calendar

- `GET /api/calendar/status`: Calendar integration status.
- `GET /api/calendar/events`: List upcoming events.
- `GET /api/calendar/summary`: Daily briefing summary.

### 🎓 Training & Feedback

- `POST /api/training/feedback`: Submit user feedback (thumbs up/down).
- `POST /api/training/auth`: Authenticate for Training Center.
- `POST /api/training/upload/{source}`: Upload chat logs (WhatsApp, Discord, etc).
- `POST /api/training/upload/document`: Upload a single document.
- `POST /api/training/fact`: Add a manual fact.
- `GET /api/training/facts`: List manual facts.
- `DELETE /api/training/facts/{index}`: Remove a manual fact.
- `POST /api/training/example`: Add a few-shot example.
- `POST /api/training/chat`: Chat in training mode (no memory persistence).
- `GET /api/training/chat/prompt`: Get training prompt.
- `DELETE /api/training/reset`: Reset training session.
- `POST /api/training/journal`: Add a journal entry.
- `GET /api/training/export`: Export all learned data as JSON.
- `POST /api/training/import`: Import previously exported data.

### 🤖 Autopilot Agents

- `GET /api/autopilot/status`: Overall system status.
- `GET /api/autopilot/{platform}/status`: Platform-specific status (discord, twitter, etc).
- `POST /api/autopilot/{platform}/start`: Start a platform bot.
- `POST /api/autopilot/{platform}/stop`: Stop a platform bot.
- `POST /api/autopilot/{platform}/settings`: Update bot settings.
- `POST /api/autopilot/{platform}/generate-reply`: Draft a reply for a DM/mention.
- `POST /api/autopilot/{platform}/generate-tweet`: Generate a new post (Twitter/LinkedIn).
- `GET /api/autopilot/logs`: View agent activity logs.

## �🛡️ Security

- **Local RAG**: Your uploaded documents stay on your machine.
- **Ephemeral Vision**: Eye Mode screenshots are analyzed in RAM and discarded instantly.
- **PIN Protection**: Critical training features are locked.

---

**v3.0.0 "Major Feature" Release** - [View Changelog](CHANGELOG.md)
