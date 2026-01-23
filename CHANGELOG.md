# Changelog

## [v3.0.2] - 2026-01-23

### ⚡ Performance & Robustness

- **Hybrid Database**: Migrated training data source-of-truth to **SQLite** (via SQLModel) while keeping ChromaDB for semantic search. This ensures data integrity and easier management.
- **Persistent Caching**: Switched from in-memory cache to **DiskCache**, allowing the cache to survive server restarts and share state across worker processes.
- **Structured Logging**: Implemented **Structlog** for production-grade JSON logging, making observability and debugging significantly easier.
- **Optimized Serialization**: Switched to `orjson` for faster API response encoding.
- **Frontend Optimization**: Configured Vite manual chunk splitting to reduce initial load times for large dependencies (Three.js, React).

### 🐛 Fixes

- Fixed potential data loss in training examples by backing them with a relational DB.
- Improved Docker caching layers.

---

## [v3.0.1] - 2025-01-21

### 🔐 Security & Testing

- **OAuth2 Authentication**:
  - Full Google OAuth2 flow using `authlib`.
  - JWT-based session management with secure HttpOnly cookies.
  - Admin whitelist (`ALLOWED_ADMIN_EMAILS`) for sensitive training routes.
- **Testing Architecture**:
  - Added comprehensive testing guide (`testing.md`).
  - Unit tests for Auth, Voice, RAG, and Security logic.
  - Integration tests for core workflows.
  - Frontend E2E tests using Playwright.
- **Robustness**:
  - Added `install_deps.py` for smarter dependency management.
  - Updated `Dockerfile` with non-root user and security hardening.

### 🐛 Fixes

- Fixed `onnxruntime` compatibility issues with Python 3.12+ (downgraded base image to 3.11-slim).
- Fixed `pydantic` v2 validator deprecation warnings.
- Resolved circular imports in service layer.

---

## [v3.0.0] - 2025-01-20

### 🚀 Major Feature Release

#### 🧠 Cognitive Upgrades

- **Notion Sync**: Bi-directional knowledge syncing with Notion workspaces.
- **Daily Briefing**: Audio briefings summarizing calendar, emails, and system status.
- **Memory Garden**: New UI for visualizing and editing core memories.
- **Active Learning**: Bot proactively asks questions to fill knowledge gaps.

#### 🎙️ Voice & Autopilot

- **Wake Word**: "Hey Chirag" activation (using `openWakeWord`).
- **Calendar Agent**: Autonomous meeting negotiation and scheduling.
- **Slack Integration**: Auto-draft replies for DMs and thread mentions.
- **Voice Cloning**: Clone your voice directly from the UI (ElevenLabs integration).

#### 🛠️ Technical Improvements

- **GraphRAG**: Integrated Knowledge Graphs for better multi-hop reasoning.
- **Agentic Browsing**: Using `playwright` for autonomous web research.
- **Local Fine-Tuning**: Export dataset for local Llama/Phi-3 training.

---

## [v2.0.0] - 2025-01-10

### 🔄 Architecture Overhaul (The "Big Refactor")

#### 🏗️ Backend

- **FastAPI Migration**: Completely rewrote the backend from Flask to **FastAPI**.
  - **Type Safety**: Full Pydantic v2 integration.
  - **Async/Await**: High-concurrency support using `asyncio`.
  - **Dependency Injection**: Modular service architecture.
- **Modular Routing**: Split monolithic `app.py` into dedicated routers:
  - `auth`, `chat`, `voice`, `training`, `dashboard`, `autopilot`.
- **Service Layer Pattern**: Extracted logic into 25+ specialized services:
  - `LLMService`: Unified wrapper for Gemini/OpenAI with fallback.
  - `MemoryService`: ChromaDB vector storage abstraction.
  - `RealtimeVoiceService`: WebSocket handling for low-latency audio.
  - `AutopilotService`: Social media automation (Twitter, LinkedIn, Discord).

#### ⚛️ Frontend

- **React 18 + Vite**: Migrated from vanilla JS/HTML to a modern React SPA.
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
