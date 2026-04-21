# AGENTS.md — Universal AI Context File
# ======================================
# This file is the single source of truth for any AI coding assistant working on this project.
# It is automatically discovered by: Cursor, Claude Code, Gemini, Antigravity, Windsurf, Copilot, Aider, and others.
# ALWAYS read this file FIRST before making any changes. NEVER skip it.

---

## 🧠 Project Identity

- **Name**: Chirag Clone — Personal Digital Twin
- **Version**: 3.1.0 (see `CHANGELOG.md` for history)
- **Owner**: Chirag N Sundar (`chiragns12@gmail.com`)
- **Repo**: `ChiragNSundar/Chirag-clone`
- **License**: Private
- **Purpose**: A continuously-learning AI system that mimics Chirag's personality, knowledge, and communication style. It is NOT a generic chatbot — it is a Digital Twin.

---

## 🏗️ Architecture Overview

This is a **full-stack monorepo** with three components:

```
Chirag-clone/
├── backend/          # Python — FastAPI REST + WebSocket API
├── frontend-react/   # TypeScript — React 19 + Vite SPA
└── desktop-widget/   # JavaScript — Electron floating widget
```

### Backend (Python / FastAPI)

| Layer | Location | Purpose |
|-------|----------|---------|
| Entry Point | `backend/main.py` | FastAPI app, middleware stack, router registration |
| Config | `backend/config.py` | All env vars loaded via `python-dotenv`, validated at startup |
| Database | `backend/database.py` | SQLModel (SQLite) — `TrainingExample` table, `chirag.db` |
| Routes | `backend/routes/*.py` | 13 modular API routers (auth, chat, voice, training, dashboard, autopilot, cognitive, knowledge, vision, agent, features, finetune, local_training) |
| Services | `backend/services/*.py` | 60+ business-logic services (see Service Catalog below) |
| Middleware | `backend/middleware/security.py` | CSP headers, XSS protection |
| Models | `backend/models/validation.py` | Pydantic v2 request/response schemas |
| Parsers | `backend/parsers/*.py` | Chat log parsers (WhatsApp, Discord, Instagram, Smart) |
| Tests | `backend/tests/*.py` | 21 test files, pytest, `conftest.py` for fixtures |
| Data | `backend/data/` | Local storage (SQLite DB, ChromaDB, uploads) — **gitignored** |

### Frontend (TypeScript / React + Vite)

| Layer | Location | Purpose |
|-------|----------|---------|
| Entry | `frontend-react/src/main.tsx` | React entry point |
| Routing | `frontend-react/src/App.tsx` | React Router — all page routes |
| Styles | `frontend-react/src/index.css` | Tailwind CSS + global styles |
| Components | `frontend-react/src/components/*.tsx` | 22 components (Chat, Dashboard, VoiceChat, TrainingCenter, Avatar3D, etc.) |
| Hooks | `frontend-react/src/hooks/` | Custom React hooks (useDebounce, useLocalStorage, etc.) |
| Services | `frontend-react/src/services/` | API client layer |
| Tests | `frontend-react/src/components/__tests__/` + inline `*.test.tsx` | Vitest + React Testing Library |
| E2E | `frontend-react/e2e/` | Playwright end-to-end tests |

### Desktop Widget (Electron)

| File | Purpose |
|------|---------|
| `desktop-widget/main.js` | Electron main process |
| `desktop-widget/preload.js` | Preload script (IPC bridge) |
| `desktop-widget/renderer.js` | Renderer logic |
| `desktop-widget/index.html` | Widget UI |

---

## 🔧 Tech Stack (Exact Versions Matter)

### Backend
- **Python**: 3.11+ (currently running on 3.14 on dev machine)
- **Framework**: FastAPI with ORJSONResponse (fast serialization)
- **ORM**: SQLModel (SQLAlchemy + Pydantic)
- **Database**: SQLite (`backend/data/chirag.db`)
- **Vector DB**: ChromaDB (optional — falls back to in-memory mock if not installed)
- **Cache**: DiskCache (SQLite-backed, persistent across restarts)
- **LLM**: Google Gemini 2.0 Flash (primary), OpenAI GPT-4o (fallback), Ollama (local)
- **Voice**: ElevenLabs (cloud), faster-whisper + piper-tts (local, optional)
- **Logging**: Structlog (JSON in prod, colored console in dev)
- **Tracing**: OpenTelemetry
- **Auth**: Google OAuth2 + JWT (via `authlib` + `PyJWT`)
- **ASGI Server**: Uvicorn

### Frontend
- **Framework**: React 19 + Vite 7
- **Language**: TypeScript
- **Styling**: Tailwind CSS (glassmorphism design system)
- **Icons**: Lucide React
- **3D**: Three.js + React Three Fiber (Avatar3D)
- **Charts**: Recharts
- **Animations**: Framer Motion
- **PWA**: Vite PWA Plugin
- **Testing**: Vitest + Playwright

### Code Quality
- **Python Formatting**: Black (line-length=100)
- **Python Imports**: isort (profile=black)
- **Python Linting**: flake8
- **JS/TS Formatting**: Prettier (see `.prettierrc`)
- **JS/TS Linting**: ESLint 9
- **Git Hooks**: Husky + lint-staged
- **Pre-commit**: See `.pre-commit-config.yaml`

---

## 📂 Critical Files Map

> **Read these files when you need context on a specific area.**

| File | What It Contains |
|------|-----------------|
| `README.md` | Full feature list, architecture diagrams, API reference, project structure |
| `CHANGELOG.md` | Version history from v1.0 → v3.1 with detailed change descriptions |
| `testing.md` | Testing strategy, all 14 test suites explained, mocking patterns |
| `training.md` | Local fine-tuning guide (LoRA, Unsloth, Ollama integration) |
| `.env.example` | All 40+ environment variables with descriptions |
| `backend/config.py` | `Config` class — all settings, defaults, and validation logic |
| `backend/main.py` | App setup, middleware stack order, all 13 router registrations |
| `backend/database.py` | SQLModel schema (`TrainingExample`), engine setup |
| `pyproject.toml` | Black, isort, pytest config, project metadata |
| `pytest.ini` | Test paths, pythonpath, markers, async mode |
| `setup.cfg` | mutmut (mutation testing) config |
| `.prettierrc` | JS/TS formatting rules |
| `.pre-commit-config.yaml` | All pre-commit hooks (Black, isort, flake8, Prettier, ESLint) |
| `.gitignore` | What's excluded (data/, .env, node_modules, dist, etc.) |
| `install_deps.py` | Smart dependency installer — handles problematic packages, venv-aware |

---

## 🧩 Service Catalog (backend/services/)

These are the core business-logic modules. Each is a singleton accessed via `get_*_service()` factory functions.

### AI & LLM
| Service | File | Purpose |
|---------|------|---------|
| `LLMService` | `llm_service.py` | Unified Gemini/OpenAI wrapper with circuit breaker |
| `OllamaService` | `ollama_service.py` | Local LLM via Ollama API |
| `ModelFallbackManager` | `model_fallback.py` | Gemini → OpenAI → Ollama cascade |
| `ThinkingService` | `thinking_service.py` | Chain-of-Thought recursive reasoning |

### Memory & Knowledge
| Service | File | Purpose |
|---------|------|---------|
| `MemoryService` | `memory_service.py` | ChromaDB vector store wrapper (with SQLite dual-write) |
| `KnowledgeService` | `knowledge_service.py` | Document upload, URL ingestion, Brain Station |
| `HybridRAG` | `hybrid_rag.py` | BM25 + Semantic search with Reciprocal Rank Fusion |
| `GraphService` | `graph_service.py` | NetworkX knowledge graph for GraphRAG |
| `CoreMemoryService` | `core_memory_service.py` | Long-term memory summarization |
| `MemorySearchService` | `memory_search_service.py` | Advanced vector search |

### Conversation
| Service | File | Purpose |
|---------|------|---------|
| `ChatService` | `chat_service.py` | Main conversation orchestrator |
| `PersonalityService` | `personality_service.py` | Identity management, profile JSON |
| `EmotionService` | `emotion_service.py` | Sentiment analysis |
| `MoodService` | `mood_service.py` | Dynamic UI mood theming |
| `CreativeService` | `creative_service.py` | Poems, dreams, stories engine |

### Voice & Vision
| Service | File | Purpose |
|---------|------|---------|
| `VoiceService` | `voice_service.py` | ElevenLabs TTS/STT |
| `RealtimeVoiceService` | `realtime_voice_service.py` | WebSocket bidirectional audio |
| `LocalVoiceService` | `local_voice_service.py` | Offline whisper/piper |
| `VoiceCloningService` | `voice_cloning_service.py` | ElevenLabs voice cloning |
| `VisionService` | `vision_service.py` | Gemini Vision image analysis |
| `WakeWordService` | `wake_word_service.py` | "Hey Chirag" detection |

### Social Autopilot
| Service | File | Purpose |
|---------|------|---------|
| `DiscordBotService` | `discord_bot_service.py` | Discord auto-replies |
| `TelegramBotService` | `telegram_bot_service.py` | Telegram integration |
| `TwitterBotService` | `twitter_bot_service.py` | Twitter/X drafting |
| `LinkedInBotService` | `linkedin_bot_service.py` | LinkedIn integration |
| `GmailBotService` | `gmail_bot_service.py` | Gmail drafting |
| `WhatsAppBotService` | `whatsapp_bot_service.py` | WhatsApp integration |
| `SlackBotService` | `slack_bot_service.py` | Slack auto-replies |

### Infrastructure
| Service | File | Purpose |
|---------|------|---------|
| `CacheService` | `cache_service.py` | DiskCache persistent cache |
| `CircuitBreaker` | `circuit_breaker.py` | Fault tolerance (CLOSED→OPEN→HALF_OPEN) |
| `RateLimiter` | `rate_limiter.py` | Per-IP request throttling |
| `PromptGuard` | `prompt_guard.py` | 5-level prompt injection detection |
| `AuthService` | `auth_service.py` | OAuth2, JWT, RBAC |
| `HTTPPool` | `http_pool.py` | Connection pooling |
| `SchedulerService` | `scheduler_service.py` | APScheduler cron jobs |
| `Telemetry` | `telemetry.py` | OpenTelemetry setup |
| `Logger` | `logger.py` | Structlog configuration |
| `Robustness` | `robustness.py` | Request validation + global exception middleware |

### Analytics & Learning
| Service | File | Purpose |
|---------|------|---------|
| `AnalyticsService` | `analytics_service.py` | Dashboard metrics |
| `ConversationAnalyticsService` | `conversation_analytics_service.py` | Topic/heatmap analysis |
| `LearningService` | `learning_service.py` | Training logic |
| `ActiveLearningService` | `active_learning_service.py` | Proactive questioning |
| `AccuracyService` | `accuracy_service.py` | Self-test quiz generation |
| `PersonalityHistoryService` | `personality_history_service.py` | Personality drift tracking |

### External Integrations
| Service | File | Purpose |
|---------|------|---------|
| `NotionSyncService` | `notion_sync_service.py` | Notion workspace sync |
| `CalendarService` | `calendar_service.py` | Google Calendar agent |
| `DailyBriefingService` | `daily_briefing_service.py` | Morning audio briefings |
| `DeepResearchService` | `deep_research_service.py` | Autonomous web research |
| `BrowserService` | `browser_service.py` | Playwright web browsing |
| `SearchService` | `search_service.py` | DuckDuckGo web search |
| `RewindService` | `rewind_service.py` | Screen memory/recording |

### Training & Fine-Tuning
| Service | File | Purpose |
|---------|------|---------|
| `FineTuneService` | `finetune_service.py` | Dataset export (ChatML JSONL) |
| `LocalTrainingService` | `local_training_service.py` | LoRA training job management |
| `BackupService` | `backup_service.py` | Brain export/import |

---

## 🚀 How to Run (Local Development)

### Prerequisites
- Python 3.11+ with pip
- Node.js 18+ with npm
- (Optional) Ollama for local AI

### Setup
```bash
# 1. Clone & configure
git clone https://github.com/ChiragNSundar/Chirag-clone.git
cd Chirag-clone
cp .env.example .env
# Edit .env → add GEMINI_API_KEY at minimum

# 2. Install dependencies
python install_deps.py

# 3. Start backend (Terminal 1)
cd backend
python -m uvicorn main:app --reload --port 8000

# 4. Start frontend (Terminal 2)
cd frontend-react
npm run dev
```

### URLs
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (FastAPI Swagger)
- **Health Check**: http://localhost:8000/api/health

### Important: PYTHONPATH
When running from the repo root (not from `backend/`), set:
```bash
PYTHONPATH=./backend python backend/main.py
```
The `backend/main.py` uses `from backend.database import ...` which requires the parent directory in the path.

### Virtual Environment
A `.venv/` exists in the project root. Use it:
```bash
.venv/Scripts/python.exe   # Windows
.venv/bin/python            # Linux/Mac
```

---

## ⚠️ Critical Gotchas & Known Issues

### 1. ChromaDB is Optional
ChromaDB requires C++ build tools and often fails to install on Windows. The app gracefully falls back to an **in-memory mock** (`MemoryService` handles this). Do NOT treat ChromaDB import errors as fatal.

### 2. Import Path: `backend.database`
`backend/main.py` line 30 uses `from backend.database import init_db`. This means when running from inside the `backend/` directory, you need `PYTHONPATH` set to the parent. When running via `python -m uvicorn main:app` from within `backend/`, the `pytest.ini` sets `pythonpath = backend`.

### 3. Circular Import Risk
The `backend/services/__init__.py` eagerly imports `LLMService`, `PersonalityService`, `MemoryService`, and `ChatService`. These services import each other. Adding new imports to `__init__.py` can trigger circular import chains. Use lazy imports inside functions when adding new cross-service dependencies.

### 4. Structlog Logging
The project uses **structlog**, NOT standard `logging`. Use:
```python
from services.logger import get_logger
logger = get_logger(__name__)
```
Do NOT use `import logging; logging.getLogger()`.

### 5. No Docker
Docker support was **intentionally removed**. Do not add Dockerfile or docker-compose.yml back. The project runs locally only.

### 6. `numpy` Incompatibility
`numpy==1.26.2` (pinned in requirements.txt) does not build on Python 3.14. This causes pip batch install warnings. It's non-fatal — numpy is only needed by optional ML packages.

### 7. Windows-Specific
- Use `npm.cmd` not `npm` in scripts (PowerShell execution policy)
- `uvloop` is Linux-only and is excluded via markers in requirements.txt
- `faster-whisper` and `piper-tts` have complex native deps — they're in `PROBLEMATIC_PACKAGES` in `install_deps.py`

### 8. Middleware Stack Order
The middleware in `main.py` is applied in **reverse order** (last added = first executed). The current order is critical for security:
1. Rate Limiter (outermost)
2. CORS
3. GZip
4. Security Headers (CSP)
5. Request Validation
6. Global Exception Handler (innermost)

### 9. OpenTelemetry
OTel is initialized in `services/telemetry.py` and applied via `setup_telemetry(app)`. If `opentelemetry` packages are missing, the app will crash on import. These are in the essential packages list in `install_deps.py`.

---

## 🧪 Testing

### Backend (pytest)
```bash
cd backend
pytest tests/ -v                                    # All tests
pytest tests/test_auth.py -v                        # Specific suite
pytest tests/ --cov=services --cov-report=term-missing  # Coverage
```

**Key markers**: `@pytest.mark.voice`, `@pytest.mark.vision`, `@pytest.mark.knowledge`, `@pytest.mark.asyncio`

**Config**: `pytest.ini` (root) + `pyproject.toml` [tool.pytest.ini_options]

### Frontend (Vitest)
```bash
cd frontend-react
npm run test:run    # Run once
npm run test        # Watch mode
```

### E2E (Playwright)
```bash
cd frontend-react
npx playwright install   # First time
npx playwright test      # Run E2E
```

### Mutation Testing
```bash
mutmut run              # Inject faults
mutmut results          # See survivors
```
Config in `setup.cfg`.

---

## 📐 Code Style & Conventions

### Python
- **Line length**: 100 characters (Black)
- **Import order**: isort with black profile
- **Type hints**: Use Pydantic v2 models for all API schemas
- **Service pattern**: Singleton via `get_*_service()` factory with `@lru_cache`
- **Error handling**: Never crash — catch and log, return graceful error responses
- **Async**: Use `async def` for all route handlers; services can be sync or async

### TypeScript/React
- **Semicolons**: Yes
- **Quotes**: Single quotes
- **Tab width**: 2 spaces
- **Trailing commas**: ES5
- **Component style**: Functional components with hooks
- **State**: React hooks + Context API (no Redux)

### Git
- **Branch strategy**: Direct to main (personal project)
- **Commits**: Conventional commits encouraged but not enforced
- **Pre-commit hooks**: Black + isort + flake8 + Prettier + ESLint

---

## 🔑 Environment Variables (Quick Reference)

> Full list with descriptions: `.env.example`

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | **Yes** (for AI) | Primary LLM provider key |
| `LLM_PROVIDER` | No (default: `gemini`) | `gemini`, `openai`, `ollama` |
| `GEMINI_MODEL` | No (default: `gemini-2.0-flash`) | Which Gemini model |
| `OPENAI_API_KEY` | No | Fallback LLM |
| `OLLAMA_BASE_URL` | No (default: `localhost:11434`) | Local Ollama server |
| `BOT_NAME` | No (default: `Chirag`) | The clone's identity |
| `ELEVENLABS_API_KEY` | No | Voice synthesis |
| `GOOGLE_CLIENT_ID` | No | OAuth2 login |
| `JWT_SECRET` | No (has default) | JWT signing key |
| `ALLOWED_ADMIN_EMAILS` | No (default: `chiragns12@gmail.com`) | Training center access |
| `TRAINING_PASSCODE` | No (default: `1234`) | Training PIN |
| `DEBUG` | No (default: `True`) | Dev mode |

---

## 🗺️ API Route Map

All routes are prefixed with `/api/`. Full reference in `README.md`.

| Router | Prefix | Key Endpoints |
|--------|--------|---------------|
| `auth` | `/api/auth/` | Google OAuth2 flow |
| `chat` | `/api/chat/` | `POST /message` — main conversation |
| `training` | `/api/training/` | Upload logs, facts, journal, export/import brain |
| `dashboard` | `/api/` | `GET /health`, `GET /dashboard/stats`, `GET /profile` |
| `autopilot` | `/api/autopilot/` | Start/stop social bots, generate replies |
| `voice` | `/api/voice/` | TTS, STT, `WS /stream` for realtime |
| `cognitive` | `/api/cognitive/` | Core memories, active learning |
| `knowledge` | `/api/knowledge/` | Upload docs, semantic search |
| `vision` | `/api/vision/` | Image analysis, desktop Eye Mode |
| `agent` | `/api/agent/` | Agentic web browsing |
| `features` | `/api/` | Creative, personality history, calendar, research, rewind |
| `finetune` | `/api/finetune/` | Dataset export for local training |
| `local_training` | `/api/training/local/` | LoRA training job management |

---

## 📋 Checklist Before Making Changes

1. **Read this file first.** You are doing that now. Good.
2. **Check `CHANGELOG.md`** to understand what changed recently.
3. **Check `.env.example`** if touching config or adding new env vars.
4. **Run tests** after changes: `pytest backend/tests/ -v`
5. **Don't break the mock fallbacks** — ChromaDB, voice services, etc. must degrade gracefully.
6. **Don't add Docker** — it was intentionally removed.
7. **Use structlog** — not standard logging.
8. **Preserve all existing comments and docstrings** unless they're incorrect.
9. **Add type hints** to new Python code.
10. **Update this file** if you make architectural changes (new services, routes, or major refactors).

---

## 🔗 Cross-References

For AI agents that support file linking:

- Architecture & Features → `README.md`
- Version History → `CHANGELOG.md`
- Testing Guide → `testing.md`
- Fine-Tuning Guide → `training.md`
- Environment Config → `.env.example`
- Python Config → `backend/config.py`
- App Entry Point → `backend/main.py`
- Database Schema → `backend/database.py`
- Dependency Installer → `install_deps.py`
- Python Tooling → `pyproject.toml`
- Test Config → `pytest.ini`
- Mutation Testing → `setup.cfg`
- Pre-commit Hooks → `.pre-commit-config.yaml`
- Prettier Config → `.prettierrc`
- Git Exclusions → `.gitignore`

---

*Last updated: 2026-04-21 by AI agent. Update this file when making architectural changes.*
