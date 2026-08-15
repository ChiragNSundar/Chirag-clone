# Changelog

## [v3.1.0] - 2026-01-25

### 🚀 Major Upgrades
- **Multimodal Chat**: Added support for drag-and-drop image analysis using `VisionService` (Gemini Vision).
- **Granular RBAC**: Implemented role-based access control (`Owner`, `Admin`, `Editor`, `Viewer`) for sensitive endpoints.
- **Local AI**: Integrated `OllamaService` for private, offline inference.
- **OpenTelemetry**: Added distributed tracing across `FastAPI` and core services.
- **Dynamic Moods**: implemented `MoodContext` for UI theming based on AI emotion.
- **Mutation Testing**: Configured `mutmut` for robust test validation.
- **Visual Regression**: Added Playwright tests for UI consistency.

### 🛡️ Security
- Secured `/training` endpoints with `@require_role`.
- Enhanced JWT payload with role information.

---

## [v3.0.2] - 2026-01-23

### ⚡ Performance & Robustness

#### 💾 Hybrid Database (SQLite + ChromaDB)

- **Dual-Write Architecture**: Training examples are now written to **SQLite** (via `SQLModel`) as the primary source of truth, while simultaneously indexed in **ChromaDB** for semantic search. This decoupling prevents vector store corruption from causing data loss.
- **Auto-Migration**: Implemented `MemoryService._migrate_chroma_to_sql()` which automatically backfills the SQLite database from existing ChromaDB vectors on startup if the SQL DB is empty.
- **Relational Schema**: Defined `TrainingExample` model in `backend/database.py` with proper timestamps and source tracking.

#### ⚡ Persistent Caching

- **Disk-Backed Cache**: Replaced the ephemeral in-memory dictionary in `CacheService` with **DiskCache** (SQLite-based).
  - **Impact**: Cache entries now survive server restarts and redeployments.
  - **Concurrency**: Cache is now process-safe, allowing multiple Gunicorn/Uvicorn workers to share the same cache state.
  - **Docker Volumes**: Added `chirag_cache` volume to `docker-compose.yml` to persist cache data across container rebuilds.

#### 📊 Structured Logging

- **Structlog Integration**: Replaced standard python logging with **Structlog**.
  - **Production**: Logs are output as structured JSON objects for easy parsing by log aggregators (e.g., Datadog, ELK).
  - **Development**: Logs use a colored console renderer for readability.
  - **Context**: Logs now automatically include timestamps, log levels, and stack traces in a consistent format.

#### 🚀 API Optimization

- **High-Performance Serialization**: Switched FastAPI's default response class to `ORJSONResponse`.
  - **Speed**: `orjson` allows for 2-5x faster JSON serialization compared to the standard library, significantly reducing latency for large payloads (e.g., chat history).

### 🐛 Fixes

- **Data Integrity**: Fixed potential data loss in training examples by backing them with a relational DB.
- **Frontend Build**: Configured Vite manual chunk splitting to reduce initial load times for large dependencies (Three.js, React).
- **Docker**: Improved Docker caching layers for faster builds.

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
