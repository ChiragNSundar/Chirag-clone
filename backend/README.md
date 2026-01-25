# Chirag Clone API - v3.0

The backend for the Chirag Clone Digital Twin, built with FastAPI.

## New Features (v3.0)
- **Local AI (Ollama)**: Full support for local LLM inference using Ollama.
- **Multimodal Support**: Use Gemini/Vision models to analyze uploaded images in chat.
- **Granular RBAC**: Role-Based Access Control (`Owner`, `Admin`, `Editor`, `Viewer`) for sensitive endpoints.
- **OpenTelemetry**: Integrated tracing for identifying performance bottlenecks.
- **Mutation Testing**: `mutmut` configuration for robustness testing.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Copy `.env.example` to `.env` and set:
   - `OLLAMA_BASE_URL`: URL for local Ollama (default: http://localhost:11434)
   - `GEMINI_API_KEY`: For vision capabilities
   - `JWT_SECRET`: For authentication

3. **Run Server**:
   ```bash
   python main.py
   ```

## Development

- **Run Tests**: `pytest`
- **Mutation Tests**: `mutmut run`
- **Linting**: `flake8 .`

## Architecture
See [ARCHITECTURE.md](../ARCHITECTURE.md) for details.
