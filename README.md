# 🧠 Chirag Clone - Personal Digital Twin

**I am Chirag's digital brain.** A continuously learning AI system that evolves to mimic my personality, knowledge, and communication style.

---

## 🛠️ Tech Stack

### Frontend

- **Framework**: React 18 + Vite
- **Styling**: Tailwind CSS (Glassmorphism design)
- **Icons**: Lucide React
- **Visualization**: Recharts
- **State/Animations**: Framer Motion

### Backend

- **Framework**: FastAPI (Python 3.11)
- **AI/LLM**: Google Gemini 2.0 Flash (Primary), OpenAI (Fallback)
- **Vector DB**: ChromaDB (Local persistence)
- **Task Management**: AsyncIO + threading
- **PDF Processing**: PyMuPDF

### DevOps & Infrastructure

- **Containerization**: Docker + Docker Compose
- **Server**: Uvicorn (ASGI)
- **Environment**: Dotenv (.env) management

---

## ✨ Key Features

### 🏛️ extensive Training Center (`/training`)

Teach your clone how to be you through multiple modalities:

- **Chat Uploads**: Learn from your real conversations (WhatsApp, Instagram, Discord)
- **Train by Chatting**: Interactive interview mode where the bot learns from your answers
- **Documents**: Upload PDFs, resumes, and text files for RAG-based knowledge
- **Journal**: Feed your thoughts and daily reflections
- **Facts**: Manually add key facts about yourself

### 📊 Analytics Dashboard (`/`)

Visual insights into your clone's development:

- **Personality Completion Ring**: Track how "complete" your clone is
- **Data Sources**: See where your clone is learning from
- **Learning Curve**: Track progress over time
- **Knowledge Metrics**: Stats on facts, quirks, and emoji usage

### 🤖 Social Autopilot (`/autopilot`)

Let your clone handle your socials when you're away:

- **Discord Bot**: Auto-reply to DMs and mentions
- **Telegram Bot**: Smart auto-responses
- **Control Panel**: Start/stop bots and view reply logs in real-time

### Other Capabilities

- **👁️ Vision**: Send images and I'll react like you would
- **🔍 Web Search**: Real-time information access
- **🛡️ Robust Security**: Rate limiting, localized data, PIN protection

---

## 🏗️ Architecture

### System Overview

```mermaid
graph TD
    User[You] -->|Web UI| Frontend[React + Vite]
    
    subgraph "Frontend Layer"
        Frontend --> Dashboard[Analytics Dashboard]
        Frontend --> Training[Training Center]
        Frontend --> Autopilot[Autopilot Control]
        Frontend --> Chat[Chat Interface]
    end
    
    Frontend -->|API/WebSocket| Backend[FastAPI Backend]
    
    subgraph "Backend Services"
        Backend --> Router[API Router]
        Router --> ChatService[Chat Service]
        Router --> TrainingService[Training Service]
        Router --> AutopilotService[Autopilot Service]
        
        ChatService --> Brain[LLM (Gemini/OpenAI)]
        ChatService --> Memory[ChromaDB Vector Store]
        ChatService --> Personality[Personality Profile]
        
        AutopilotService --> Discord[Discord Bot]
        AutopilotService --> Telegram[Telegram Bot]
    end
```

### Autopilot Workflow

```mermaid
sequenceDiagram
    participant D as Discord/Telegram
    participant B as Bot Service
    participant C as Chat Service
    participant M as Memory (RAG)
    participant L as LLM
    
    D->>B: User Message (DM/Mention)
    B->>C: Generate Response
    C->>M: Retrieve Context (Facts/Style)
    M-->>C: Relevant Context
    C->>L: Prompt with Persona & Context
    L-->>C: Generated Reply (in your style)
    C-->>B: Final Response
    B->>D: Send Reply
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- [Google Gemini API Key](https://makersuite.google.com/app/apikey)

### 2. Setup (Local Development)

#### Backend Setup

```bash
cd backend
python -m venv venv
# Activate venv:
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env  # Configure your keys in .env
```

#### Frontend Setup

```bash
cd frontend-react
npm install
```

### 3. Running the App

**Terminal 1 (Backend):**

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

**Terminal 2 (Frontend):**

```bash
cd frontend-react
npm run dev
```

Open **<http://localhost:5173>** (or the port shown in terminal) to access the UI.

---

## 🐳 Docker Deployment

Run the entire stack with a single command.

### Option A: Docker Compose (Recommended)

This sets up optimized containers for backend and frontend.

```bash
# 1. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# 2. Start services
docker-compose up -d --build

# 3. View logs
docker-compose logs -f
```

Access app at `http://localhost:5173` (Frontend) and `http://localhost:8000` (Backend API).

### 🧪 Running Tests

To verify the installation and backend logic:

```bash
cd backend
python -m pip install pytest httpx
python -m pytest tests/test_main.py
```

### Option B: Manual Docker Run

```bash
# Build image
docker build -t chirag-clone .

# Run container
docker run -p 8000:8000 --env-file backend/.env chirag-clone
```

---

## 🔧 Bot Configuration

To enable **Social Autopilot**, you need to configure bot tokens in your `.env` file:

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a New Application -> Bot
3. Enable **Message Content Intent** under Privileges
4. Copy Token to `.env`: `DISCORD_BOT_TOKEN=your_token`
5. Invite bot to server using OAuth2 URL Generator (scopes: `bot`, permissions: `Read Messages`, `Send Messages`)

### Telegram Bot Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy Token to `.env`: `TELEGRAM_BOT_TOKEN=your_token`
4. Start a chat with your new bot

---

## 📁 Project Structure

```text
Chirag-clone/
├── backend/
│   ├── main.py                     # FastAPI Application Entry Point
│   ├── config.py                   # Configuration Settings
│   ├── requirements.txt            # Python Dependencies
│   │
│   ├── services/                   # Core Business Logic
│   │   ├── __init__.py
│   │   ├── analytics_service.py    # Dashboard Metrics
│   │   ├── async_job_service.py    # Background Tasks
│   │   ├── backup_service.py       # Data Backup
│   │   ├── cache_service.py        # Redis/Local Cache
│   │   ├── chat_service.py         # Main Conversation Logic
│   │   ├── discord_bot_service.py  # Discord Integration
│   │   ├── knowledge_service.py    # RAG/Document Handling
│   │   ├── learning_service.py     # Training Logic
│   │   ├── llm_service.py          # Gemini/OpenAI Wrapper
│   │   ├── logger.py               # Structured Logging
│   │   ├── memory_service.py       # Vector DB Wrapper
│   │   ├── middleware.py           # Request Processing
│   │   ├── mood_service.py         # Emotional State
│   │   ├── personality_service.py  # Identity Management
│   │   ├── rate_limiter.py         # API Throttling
│   │   ├── scheduler_service.py    # Cron Jobs
│   │   ├── search_service.py       # Web Search
│   │   ├── telegram_bot_service.py # Telegram Integration
│   │   └── vision_service.py       # Image Processing
│   │
│   ├── parsers/                    # Chat Log Parsers
│   │   ├── __init__.py
│   │   ├── discord_parser.py       # Discord JSON Parser
│   │   ├── instagram_parser.py     # Instagram JSON Parser
│   │   ├── smart_parser.py         # Auto-format Detector
│   │   └── whatsapp_parser.py      # WhatsApp Text Parser
│   │
│   └── data/                       # Local Storage
│       ├── chroma_db/              # Vector Database
│       └── personality_profile.json # Learned Traits
│
├── frontend-react/
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── vite.config.ts
│   │
│   └── src/
│       ├── main.tsx                # React Entry Point
│       ├── index.css               # Global Styles/Tailwind
│       ├── App.tsx                 # Routing & Layout
│       │
│       ├── components/             # React Components
│       │   ├── AutopilotPage.tsx   # Bot Control Dashboard
│       │   ├── ChatInterface.tsx   # Main Chat UI
│       │   ├── Dashboard.tsx       # Analytics Home
│       │   ├── Layout.tsx          # Navigation Wrapper
│       │   ├── MemoryGraph.tsx     # Knowledge Visualization
│       │   ├── ProfilePage.tsx     # Bot Profile Settings
│       │   └── TrainingCenter.tsx  # Interactive Training UI
│       │
│       └── services/
│           └── api.ts              # API Client
│
├── Dockerfile                      # Production Build Definition
└── docker-compose.yml              # Container Orchestration
```

---

## 🛡️ Security & Privacy

- **Local-First**: Your personality profile and vector data are stored locally in `backend/data/`.
- **PIN Protection**: The Training Center is protected by a PIN (default: `1234`) to prevent unauthorized changes.
- **Environment Variables**: API keys are strictly managed via `.env` and never committed.
