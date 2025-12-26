# 🤖 Personal AI Clone Bot

A self-learning chatbot that mimics your personality, texting style, and communication patterns. Train it with your chat exports and watch it become your digital twin!

![AI Clone Banner](https://via.placeholder.com/800x200?text=AI+Clone+Bot+Replicating+YOU)

## ✨ Features

- **🎭 Personality Learning** - Learns your texting style, emoji usage, and common phrases
- **💬 Real-time Chat** - Chat with your AI clone via WebSocket or HTTP
- **🤖 Social Autopilot** - **NEW!** Auto-reply on Discord and Telegram when you're away
- **🕰️ Semantic Timeline** - **NEW!** Visualize what your clone has learned over time
- **📊 Analytics Dashboard** - **NEW!** Track conversation stats, response times, and confidence
- **💾 Auto-Backup** - **NEW!** Protect your training data with one-click backups
- **📤 Import Chat Data** - Upload exports from WhatsApp, Discord, and Instagram
- **🎓 Training Corner** - Interactive training where you correct the bot's responses
- **🧠 Continuous Learning** - Gets better the more you interact with it
- **🌙 Beautiful Dark UI** - Modern, glassmorphic design

## 🏗️ Architecture

The app uses a dual-mode architecture to separate "training" conversations from "acting" conversations.

```mermaid
graph TD
    User[User] -->|Chat Mode| FE[Frontend]
    User -->|Training Mode| FE
    
    FE -->|WebSocket/HTTP| API[Flask Backend]
    
    subgraph "Brain Core"
        API -->|Route| ChatService
        ChatService -->|Context| Memory[MemoryService (ChromaDB)]
        ChatService -->|Style| Personality[PersonalityService]
        ChatService -->|Learn| Learning[LearningService]
        
        Memory -->|Vector Search| Chroma[(ChromaDB)]
        Personality -->|Profile| JSON[(Profile JSON)]
    end
    
    subgraph "Autopilot"
        Discord[Discord Bot] -->|Events| ChatService
        Telegram[Telegram Bot] -->|Events| ChatService
    end
```

## 🔄 Two-Mode Architecture

1. **Chat Tab (The "Actor")**:
   - Uses frozen memory to reply.
   - Mimics you perfectly for others.
   - Does **not** learn (prevents pollution from random chats).

2. **Training Corner (The "Student")**:
   - You talk to the bot.
   - You correct its answers.
   - It **actively learns** new facts and patterns from this interaction.

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
cd "c:\Github\New folder"
```

### 2. Set up Python environment

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and configure your keys:

```bash
copy .env.example .env
```

**Required Keys:**

```env
GEMINI_API_KEY=your_key_here
BOT_NAME=YourName
```

**Optional (for Autopilot):**

```env
DISCORD_BOT_TOKEN=your_discord_token
TELEGRAM_BOT_TOKEN=your_telegram_token
```

### 4. Run the application

```bash
python app.py
```

### 5. Open in browser

Navigate to **<http://localhost:5000>**

---

## 🤖 Social Autopilot Setup

Your clone can live on social platforms!

### Discord Bot

1. Create App at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create Bot User -> Copy Token -> Paste in `.env`
3. Enable "Message Content Intent"
4. Invite bot to server.
5. Go to **Autopilot Tab** in app -> Start Discord Bot.

### Telegram Bot

1. Chat with `@BotFather` on Telegram.
2. `/newbot` -> Name it -> Copy Token -> Paste in `.env`.
3. Go to **Autopilot Tab** in app -> Start Telegram Bot.

---

## 📊 Analytics & Backups

Check the **Profile Tab** for:

- **Conversation Stats**: Total chats, avg response time.
- **Top Topics**: What people talk to your clone about.
- **Backups**: Create snapshots of your clone's brain.
- **Export**: Download your personality profile as JSON.

---

## 📁 Project Structure

```
├── backend/
│   ├── app.py                 # Main entry point
│   ├── config.py              # Settings
│   ├── services/
│   │   ├── chat_service.py    # Core logic
│   │   ├── memory_service.py  # ChromaDB wrapper
│   │   ├── discord_bot.py     # Discord integration
│   │   └── ...
│   └── routes/                # API Endpoints
│
└── frontend/
    ├── index.html            # Main UI
    ├── css/styles.css        # Glassmorphic styles
    └── js/app.js             # Frontend logic
```

## 📝 License

MIT License - feel free to use and modify!

---

Built with 💜 to help you create your digital twin
