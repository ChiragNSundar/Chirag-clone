# Changelog

## [2.7.0] - 2026-01-19

### 🏗️ Major Backend Refactoring

- **Modular Router Architecture**: Completely refactored `main.py` from 2267 lines to ~200 lines by extracting all endpoints into dedicated router modules.
  
#### New Router Files

| Router | Endpoints | Description |
|--------|-----------|-------------|
| `routes/chat.py` | `/api/chat/*` | Chat messaging |
| `routes/training.py` | `/api/training/*` | Uploads, facts, journal, examples |
| `routes/dashboard.py` | `/api/dashboard/*`, `/api/health`, `/api/profile`, `/api/analytics/*` | Stats, health, analytics |
| `routes/autopilot.py` | `/api/autopilot/*` | Discord, Telegram, Twitter, LinkedIn, Gmail, WhatsApp |
| `routes/voice.py` | `/api/voice/*` | TTS, STT, real-time WebSocket streaming |
| `routes/cognitive.py` | `/api/cognitive/*` | Core memory, active learning |
| `routes/knowledge.py` | `/api/knowledge/*` | Document management, querying |
| `routes/vision.py` | `/api/vision/*` | Desktop and image analysis |
| `routes/features.py` | Creative, calendar, quiz, research, rewind | Miscellaneous features |

### 🔧 Code Quality

- **Improved Logging**: Replaced `print()` statements in `smart_parser.py` with proper `logger.warning()`.
- **Cleaner Imports**: Centralized service imports within each router module.
- **Better Testability**: Isolated router modules are easier to unit test.

### 📁 File Changes

- **Modified**: `backend/main.py` (reduced from 2267 to ~200 lines)
- **Modified**: `backend/parsers/smart_parser.py` (improved logging)
- **Added**: 9 new router files in `backend/routes/`
- **Added**: `install_deps.py` (robust verified cross-platform installer)
- **Modified**: `requirements.txt` (cleaned BOM and problematic packages)

### 📦 Dependency Management

- **Reliable Installer**: New `install_deps.py` script replaces fragile manual installs.
  - **Batch Installation**: ~10x faster installation using internal pip concurrency.
  - **Cross-Platform**: Automatically handles Windows-specific issues (encoding, binary wheels).
  - **Fault Tolerance**: Skips problematic packages (`chromadb` on Windows) while keeping app functional.
- **Mock Services**: Implemented `MockMemoryService` to allow backend to run without vector DB if installation fails.

---

## [2.6.0] - 2026-01-17

### 🛠️ Developer Experience

- **Pre-commit Hooks**: Added `.pre-commit-config.yaml` with Black, isort, Prettier, ESLint.
- **pyproject.toml**: Centralized Python tooling configuration.
- **Prettier/ESLint**: Consistent frontend code formatting.

### 🎙️ Voice Enhancements

- **Duplex Voice**: Added barge-in capability for interrupting bot mid-speech.
- **VAD Integration**: Voice Activity Detection using `webrtcvad` with energy-based fallback.
- **VoiceState Enum**: Enhanced state machine for conversation tracking.

### 🔐 Security & Auth

- **Google-Only Auth**: Simplified authentication to exclusively use Google OAuth2 (GitHub removed), ensuring stricter access control.
- **Circuit Breakers**: Added `CircuitBreaker` pattern to `backend/services/circuit_breaker.py` preventing cascading failures.
- **Hybrid RAG**: Implemented Reciprocal Rank Fusion combining BM25 keyword search with semantic vector search.
- **Prompt Guard**: 5-level threat detection system identifying prompt injection.

### 🧪 Test Suite Expansion

- **Backend Coverage**: Added comprehensive tests for `auth_service`, `realtime_voice_service`, `prompt_guard`, `hybrid_rag`, and `circuit_breaker`.
- **Frontend Tests**: Added Vitest mocks and component tests for `VoiceChat`, `Dashboard`, and `LoginPage`.
- **Reliability**: Implemented mocks for complex services (WebSocket, MediaRecorder, OpenAI).

---

## [2.5.0] - 2026-01-17

### 🚀 Major Features

- **Production Robustness**: Introduced a comprehensive suite of reliability features.
  - **Circuit Breakers**: Added `CircuitBreaker` pattern to `backend/services/circuit_breaker.py` preventing cascading failures from external API outages.
  - **Hybrid RAG**: Implemented Reciprocal Rank Fusion combining BM25 keyword search with semantic vector search in `backend/services/hybrid_rag.py`.
  - **Model Fallback**: Automated fallback system (Gemini → GPT-4o → Local) in `backend/services/model_fallback.py`.

### 🔒 Security

- **Prompt Guard**: 5-level threat detection system identifying prompt injection, role-playing attacks, and jailbreaks.
- **Security Middleware**: Added CSP, XSS protection, and SQL injection detection in `backend/middleware/security.py`.
- **Strict Validation**: Migrated all data models to strict Pydantic v2 schemas in `backend/models/validation.py`.

### 🏗️ Infrastructure

- **Docker Compose**: Enhanced stack with Redis (caching) and ChromaDB (vector storage) services.
- **E2E Testing**: Added Playwright test suite (`frontend-react/e2e/`) covering navigation, chat, and accessibility.
- **Migrations**: Setup Alembic for database migrations.

## [2.4.2] - 2026-01-17

### ⚡ Performance & UX

- **Command Palette**: Added `Cmd+K` interface for global navigation and quick actions.
- **Lazy Loading**: Implemented code-splitting for all major routes (Dashboard, Training, etc.) reducing initial bundle size.
- **Settings Panel**: New centralized settings UI with theme toggle (Dark/Light/System) and preference persistence.
- **Async Caching**: Added request coalescing decorator to prevent "thundering herd" issues on high-traffic endpoints.

## [2.4.1] - 2026-01-17

### 🧪 Quality Assurance

- **Frontend Tests**: Added Vitest unit tests for Dashboard, ChatInterface, and ThinkingBubble.
- **Components**: Added `ErrorBoundary`, `Toast` notifications, and accessible `Skeleton` loaders.
- **Hooks**: Added `useUtilities` collection (debounce, localStorage, mediaQuery).

## [2.4.0] - 2026-01-17

### 🌟 Core Capabilities

- **Deep Research**: Agentic web research capable of recursive searching and report generation.
- **Rewind Memory**: Desktop screen recording buffer allowing "What was I looking at?" queries.
- **Local Voice**: Offline-first TTS/STT using `faster-whisper` and `piper-tts`.
- **Performance Monitor**: Middleware for tracking API latency and error rates.

## [2.3.1] - 2026-01-16

### 🛡️ Robustness & Parsing

- **Advanced Chat Parsers**:
  - **WhatsApp**: Compiled Regex for 4x speed, improved partial multi-line handling, and removal of invisible control characters (LTR/RTL marks).
  - **Discord**: Robust JSON/CSV handling, attachment placeholders (instead of skipping), and strict timestamps.
  - **Instagram**: Automatic fix for "Mojibake" (Latin-1/UTF-8 encoding errors) and proper handling of shared media/posts.
  - **Smart Parser (LLM)**: Self-healing JSON logic to repair broken LLM outputs and improved heuristics for unformatted text.

### 🐳 Infrastructure Updates

- **Production Dockerfile**:
  - Switched from `python:3.11` to `python:3.11-slim` (reduced image size).
  - Added `curl` for reliable healthchecks.
  - **Performance Tuning**: Added `uvloop` (Linux/Mac) and `httptools` for faster asyncio event loop.
  - **Memory Safety**: Tuned `MALLOC_ARENA_MAX=2` to prevent memory fragmentation in long-running containers.

### ⚡ Performance

- **Optimized Uvicorn**: Enabled `uvloop` for 2-3x throughput increase on Linux.
- **Logging**: Added structured JSON logging via Docker options for better observability.

### 🧠 Major Update: The "Brain Station" Release

This update transforms the clone from a chatbot into a proactive, seeing, and listening digital twin.

#### 🎙️ Real-Time Voice Conversation

- **WebSocket Streaming**: Replaced request-response audio with full duplex WebSockets for sub-second latency.
- **Live Mode**: Toggle switch in Chat UI to enable open-mic conversation.
- **Smart Interruption**: Speak over the bot to stop it instantly (half-duplex emulation).
- **Turn-Taking Logic**: `RealtimeVoiceService` manages conversational flow and silence detection.
- **Visualizer**: New `AudioVisualizer` component using Web Audio API for "Siri-like" frequency matching.

#### 👁️ Desktop Vision Widget ("Eye Mode")

- **Active Window Awareness**: The desktop widget now captures the currently focused application window.
- **Proactive Suggestions**: Periodically analyzes screen content to offer relevant context or help.
- **Privacy Design**: Captures only the active window (not full screen), processes in-memory, and discards immediately.
- **Electron Integration**: Uses `desktopCapturer` API with secure IPC bridges.

#### 🏛️ Brain Station (Knowledge Management)

- **Centralized Knowledge Hub**: New tab in Training Center for managing RAG data.
- **Multi-Modal Ingestion**:
  - **Drag-and-Drop**: Upload PDF, TXT, MD files directly.
  - **URL Ingestion**: Paste a link to scrape and index web content.
  - **Quick Notes**: Add raw text facts on the fly.
- **Interactive Knowledge Graph**:
  - Completely rewritten `MemoryGraph` with interactive nodes.
  - Click-to-view details, search filtering, and MiniMap navigation.
  - Physics-based clustering of related concepts.

### 📡 New Microservices

- `realtime_voice_service.py`: Dedicated WebSocket handler for audio streaming.
- `AudioVisualizer.tsx`: React component for frequency analysis.
- `MemoryGraph.tsx` (Rewrite): Interactive ReactFlow implementation.

### 📦 New Dependencies

- `aiohttp`, `beautifulsoup4`, `lxml`: For URL fetching and parsing.
- `libmupdf-dev`: Added to Dockerfile for robust PDF processing.

### 🔧 Improvements

- **Docker**: Bumped to v2.3, enabled WebSocket support in Uvicorn command.
- **Memory**: Increased container memory limits to 3GB to handle vision tasks.
- **UI**: Added "Live" indicators and improved glassmorphism on graphs.

### 🛡️ Robustness & Reliability

- **`robustness.py` (NEW)**: FastAPI middleware for request validation, global exception handling, and graceful degradation.
- **Health Monitor**: `ServiceHealthMonitor` class tracks status of all dependent services (LLM, memory, voice, knowledge).
- **Enhanced `/api/health`**: Now supports `?detailed=true` query param for full service status including circuit breaker state.
- **Input Validation**: Enhanced Pydantic models with length limits, sanitization, and validators.
- **Startup Checks**: New `startup_event` validates configuration and pre-warms critical services.
- **Graceful Degradation**: `safe_service_call` decorator and `GracefulDegradation` context manager for fault-tolerant service calls.
- **Request Timing**: All responses now include `X-Response-Time` header.
- **Global Exception Handler**: Catches unhandled exceptions and returns user-friendly error messages.

### ⚡ Performance Optimizations

- **GZip Compression**: All responses >500 bytes are compressed (60-80% bandwidth savings).
- **`http_pool.py` (NEW)**: Connection pooling for external HTTP requests with automatic retry and exponential backoff.
- **Async Caching**: New `async_cached` decorator supports both sync and async functions with TTL-based invalidation.
- **System Metrics**: New `/api/system/metrics` endpoint for monitoring cache hit rates, memory usage, and connection pool status.
- **Graceful Shutdown**: Proper cleanup of HTTP connections and cache on server shutdown.

---

## [2.2.0] - 2026-01-15

### 🚀 Major Enhancements

#### Voice & Emotion

- **Voice I/O**: Integrated ElevenLabs TTS and OpenAI Whisper STT for full voice conversations.
- **Thinking Process UI**: Visual "Chain of Thought" bubble showing the AI's reasoning steps before responding.
- **Emotion Detection**: Real-time sentiment analysis (14 categories) that adapts the bot's response tone.
- **VoiceChat Component**: Reactive UI with microphone recording, audio visualization, and playback controls.

#### Memory & Knowledge

- **Memory Search**: Full-text search engine across all stored memories, documents, and conversations.
- **Personality Timeline**: Tracks evolution of the clone's personality profile with snapshot comparisons.
- **Growth Metrics**: Analytics for knowledge acquisition rate and personality drift.

#### 🎨 Creative Studio

- **Generative Modes**: specialized engines for Poems, Haikus, Stories, Journal Entries, and Dreams in user's style.
- **Accuracy Service**: A/B testing framework and self-assessment quizzes to measure clone authenticity.
- **Daily Prompts**: AI-generated writing prompts to fuel the creative engine.

#### 🤖 Integrations Expansion

- **WhatsApp Autopilot**: Business API integration for generating auto-reply drafts.
- **Calendar Assistant**: Google Calendar integration for schedule summaries and meeting suggestions.
- **Unified Drafts Dashboard**: Single view for managing Twitter, LinkedIn, Gmail, and WhatsApp drafts.
- **Conversation Analytics**: Topic extraction, activity heatmaps, and response time tracking.

### 📡 New Microservices

- `voice_service.py`: Handling audio stream processing.
- `emotion_service.py`: NLP classification for emotional context.
- `memory_search_service.py`: Advanced ChromaDB querying.
- `creative_service.py`: Specialized LLM prompting for creative content.
- `accuracy_service.py`: Statistical verification of clone quality.
- `calendar_service.py`: Google Workspace integration logic.

### 🔧 Configuration

- Added keys for ElevenLabs, Google Calendar, and WhatsApp to `.env.example`.
- Updated API types for `ThinkingData` and `Emotion` in frontend.

---

## [2.1.0] - 2026-01-15

### 🎭 3D Avatar with Lip-Sync

A new interactive 3D avatar that speaks with you:

- **Avatar3D Component**: Three.js-powered 3D avatar using React Three Fiber
- **Ready Player Me Integration**: Load any Ready Player Me GLB model
- **Real-time Lip-Sync**: Viseme-based mouth animation synced to responses
- **Expandable View**: Toggle between compact and full avatar modes
- **Customizable**: Settings panel to change avatar URL
- **Backend Support**: `avatar_service.py` for text-to-viseme conversion

### 🧠 Cognitive Enhancements (Deep Brain)

Three new intelligent systems for smarter interactions:

#### Long-term Memory Summarization

- **Core Memory Service**: Summarizes conversations into lasting facts
- **Example outputs**: "User hates spinach", "User's favorite movie is Inception"
- **Dedicated ChromaDB collection**: `core_memories` for persistent storage
- **7 Categories**: preferences, facts, relationships, experiences, opinions, habits, goals
- **Nightly processing**: Automatic summarization via scheduler

#### Recursive Thinking (Inner Monologue)

- **Thinking Service**: Chain-of-thought reasoning before complex answers
- **Complexity Detection**: Automatically triggers for difficult questions
- **Structured Steps**: Returns thinking process in numbered steps
- **Keywords**: Triggers on "why", "how", "explain", "compare", "should I", etc.

#### Active Learning

- **Knowledge Gap Detection**: Analyzes 8 domain areas for missing info
- **Proactive Questions**: Generates targeted questions to fill gaps
- **Priority Scoring**: Ranks questions by importance and domain weight
- **Fact Extraction**: Automatically extracts facts from user answers
- **Progress Tracking**: Coverage percentages per domain

### 🖥️ Desktop Widget (Electron)

A new floating desktop app for quick access:

- **Floating Window**: 320x450px always-on-top widget
- **Frameless Design**: Modern glassmorphism dark theme
- **Global Shortcut**: `Cmd+Shift+C` (macOS) to toggle visibility
- **System Tray**: Icon with context menu for show/hide/settings/quit
- **Quick Chat**: Full chat functionality without opening browser
- **Configurable Backend**: Settings panel for custom API URL
- **Electron Store**: Persists window position and preferences
- **macOS Packaging**: Build script for `.dmg` distribution

**Files Created:**

- `desktop-widget/package.json` - Electron dependencies
- `desktop-widget/main.js` - Main process (window, tray, shortcuts)
- `desktop-widget/preload.js` - Secure IPC bridge
- `desktop-widget/index.html` - Widget HTML structure
- `desktop-widget/renderer.js` - Frontend chat logic
- `desktop-widget/styles.css` - Glassmorphism CSS theme

### 🤖 New Autopilot Integrations

Three new platforms for your digital clone:

#### Twitter/X Integration

- **Draft Tweets**: Generate tweets in your style on any topic
- **Draft Replies**: Respond to tweets authentically
- **Draft Queue**: Review before posting (no auto-posting)
- **Tweepy Library**: Official Twitter API v2 support
- **Credentials**: `TWITTER_CLIENT_ID`, `TWITTER_CLIENT_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`

#### LinkedIn Integration

- **DM Responses**: Professional reply drafting
- **Connection Notes**: Generate personalized connection requests
- **Draft Queue**: Approve/reject before sending
- **linkedin-api Library**: Unofficial API integration
- **Credentials**: `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`

#### Gmail Integration

- **Email Reply Drafts**: Generate replies in your voice
- **OAuth 2.0**: Secure Google authentication
- **Gmail API**: Official Google API support
- **Actual Drafts**: Can create drafts directly in Gmail
- **Credentials**: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`

### 📡 New API Endpoints

15+ new endpoints added:

**Cognitive Endpoints:**

- `GET /api/cognitive/core-memories` - List core memories
- `DELETE /api/cognitive/core-memories/{id}` - Delete a memory
- `POST /api/cognitive/trigger-summarization` - Manual summarization
- `GET /api/cognitive/active-learning/suggestions` - Get proactive questions
- `POST /api/cognitive/active-learning/answer` - Submit an answer
- `GET /api/cognitive/learning-stats` - Comprehensive stats

**Twitter Endpoints:**

- `GET /api/autopilot/twitter/status` - Service status
- `GET /api/autopilot/twitter/drafts` - Draft queue
- `POST /api/autopilot/twitter/generate-tweet` - Create tweet draft
- `POST /api/autopilot/twitter/generate-reply` - Create reply draft

**LinkedIn Endpoints:**

- `GET /api/autopilot/linkedin/status` - Service status
- `GET /api/autopilot/linkedin/drafts` - Draft queue
- `POST /api/autopilot/linkedin/generate-reply` - Create reply draft

**Gmail Endpoints:**

- `GET /api/autopilot/gmail/status` - Service status
- `GET /api/autopilot/gmail/drafts` - Draft queue
- `POST /api/autopilot/gmail/generate-reply` - Create email draft

### 📦 New Dependencies

**Backend (requirements.txt):**

- `tweepy>=4.14.0` - Twitter API
- `linkedin-api>=2.0.0` - LinkedIn API
- `google-auth-oauthlib>=1.0.0` - Gmail OAuth

**Frontend (package.json):**

- `three` - 3D rendering engine
- `@react-three/fiber` - React renderer for Three.js
- `@react-three/drei` - Useful helpers for R3F
- `@types/three` - TypeScript definitions

**Desktop Widget (package.json):**

- `electron` - Desktop app framework
- `electron-builder` - Packaging and distribution
- `electron-store` - Persistent settings

### 🔧 Configuration Updates

**New .env variables:**

```bash
# Twitter/X
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=

# LinkedIn
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=

# Gmail
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
```

### 📚 Documentation

- **README.md**: Completely updated with new features
- **Mermaid Diagrams**: New architecture diagrams including cognitive flow
- **Project Structure**: Updated with all new files (marked with NEW)
- **Setup Instructions**: Added desktop widget installation
- **Bot Configuration**: Added Twitter, LinkedIn, Gmail setup guides

---

## [2.0.0] - 2026-01-14

### 🚀 Major Features

- **Training Center**: A comprehensive suite for teaching the bot.
  - **Chat Uploads**: Support for parsing WhatsApp, Instagram, and Discord export files.
  - **Train by Chatting**: Interactive interview mode where the bot learns style and facts from direct conversation.
  - **Document Support**: RAG implementation for PDF and text file uploads.
  - **Journal System**: Dedicated interface for day-to-day thought recording.
  - **PIN Security**: Protected training routes (default PIN: 1234).
- **Advanced Model Switching**:
  - Implemented cascading fallback: Gemma 2 27b -> Gemini 2.0 (Flash Lite/Flash/Pro).
  - OpenAI fallback support.
  - Removed Anthropic/Claude support.

### 🧪 Testing

- Added comprehensive test suite for FastAPI endpoints (`tests/test_main.py`).
- Added robust error handling and logging.
  - **Enhanced Analytics Dashboard**:
    - **Source Analysis**: Pie charts showing data provenance (WhatsApp vs Discord vs Manual).
    - **Learning Velocity**: Area charts tracking knowledge acquisition over time.
    - **Activity Heatmap**: Visualizing interaction times.
    - **Metric Cards**: At-a-glance stats for Facts, Quirks, and Emojis.
    - **Topic Distribution**: Analysis of conversation themes.
- **Social Autopilot**: Platform integration system.
  - **Discord Bot**: Fully functional bot with DM and mention auto-replies.
  - **Telegram Bot**: Integration for automated chat responses.
  - **Control Panel**: Web UI to start/stop bots and view real-time reply logs.

### 🏗️ Infrastructure & Architecture

- **Backend Migration**: Complete transition from Flask (v1) to **FastAPI** (v2).
  - Asynchronous request handling for better scalability.
  - Pydantic models for strict data validation.
  - Type-safe endpoints with auto-generated documentation.
- **Frontend Modernization**: Rebuilt using **React + Vite**.
  - Component-based architecture for maintainability.
  - **Tailwind CSS** for responsive, glassmorphic design.
  - Real-time updates using WebSockets/Polling.
- **DevOps**:
  - Multi-stage **Docker** build process.
  - **Docker Compose** orchestration for easy deployment.
  - Environment variable management via `.env`.

### 🔧 Fixes & Optimizations

- **CORS Handling**: Configured to support multiple development ports (5173-5177).
- **Memory Optimization**: Improved vector store (ChromaDB) management.
- **Robustness**: Added circuit breakers and rate limiting services.
- **Cleanup**:
  - Removed legacy Flask routes and app entry points (`app.py`).
  - Updated `.gitignore` to strictly exclude sensitive files and build artifacts.

---

## [1.0.0] - 2025-12-25 (Legacy)

### Added

- Basic Flask backend.
- Simple HTML/JS frontend.
- Integration with Gemini 1.5 Flash.
- Basic "Personality Profile" JSON storage.
- Simple keyword-based memory retrieval.
- Initial Docker support.
