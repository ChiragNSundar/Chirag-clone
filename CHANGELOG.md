# Changelog

All notable changes to the "Chirag Clone" project will be documented in this file.

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
  - **Source Analysis**: Pie charts showing data provenance (WhatsApp vs Discord vs Manual).
  - **Learning Velocity**: Area charts tracking knowledge acquisition over time.
  - **Metric Cards**: At-a-glance stats for Facts, Quirks, and Emojis.
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
- **Cleanup**: Removed legacy Flask routes and app entry points (`app.py`).

---

## [1.0.0] - 2025-12-25 (Legacy)

### Added

- Basic Flask backend.
- Simple HTML/JS frontend.
- Integration with Gemini 1.5 Flash.
- Basic "Personality Profile" JSON storage.
- Simple keyword-based memory retrieval.
- Initial Docker support.
