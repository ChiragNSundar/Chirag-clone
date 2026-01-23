"""
Chirag Clone API - v2.3.0
Main application entry point.

This is a refactored version of the original main.py with endpoints organized into routers.
All endpoint logic has been moved to routes/ modules for better maintainability.
"""
from fastapi import FastAPI
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import logging
import time
import pathlib

from config import Config, validate_config
from services.logger import get_logger

# Configure logging using new service
logger = get_logger(__name__)

# Import robustness utilities
from services.robustness import (
    RequestValidationMiddleware,
    GlobalExceptionMiddleware,
)

from backend.database import init_db

# Validate configuration at startup
config_warnings = validate_config()
init_db()  # Initialize SQLModel DB
for warning in config_warnings:
    logger.warning(f"[CONFIG] {warning}")

# ============= Application Setup =============

app = FastAPI(
    title="Chirag Clone API",
    description="Personal AI Clone Bot API - v2.3 with Real-Time Voice, Vision, and Brain Station",
    version="2.3.0",
    default_response_class=ORJSONResponse
)

# ============= Middleware Configuration =============

# Add robustness middleware
app.add_middleware(GlobalExceptionMiddleware)
app.add_middleware(RequestValidationMiddleware, max_body_size=Config.MAX_REQUEST_SIZE_MB * 1024 * 1024)

# Add Security Headers (CSP, XSS Protection)
from middleware.security import SecurityHeadersMiddleware
app.add_middleware(
    SecurityHeadersMiddleware,
    csp_policy="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' ws: wss: https:;"
)

# Add GZip compression for optimized response sizes (60-80% smaller)
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS Configuration - allow all localhost ports for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Rate Limiting Middleware
from services.rate_limiter import rate_limit
app.middleware("http")(rate_limit)

# ============= Lifecycle Events =============

@app.on_event("startup")
async def startup_event():
    """Initialize services and log startup status."""
    logger.info("=" * 60)
    logger.info("🧠 Chirag Clone API v2.3.0 Starting...")
    logger.info("=" * 60)
    
    # Log configuration warnings
    if config_warnings:
        logger.warning(f"⚠️  {len(config_warnings)} configuration warning(s)")
    else:
        logger.info("✅ Configuration validated successfully")
    
    # Pre-warm critical services (optional, for faster first request)
    try:
        from services.personality_service import get_personality_service
        personality = get_personality_service()
        logger.info(f"✅ Personality service ready: {personality.get_profile().name}")
    except Exception as e:
        logger.warning(f"⚠️  Personality service: {e}")
    
    # Check LLM availability
    try:
        from services.llm_service import get_llm_service
        llm = get_llm_service()
        circuit_state = llm.get_circuit_state()
        logger.info(f"✅ LLM service ready: {Config.LLM_PROVIDER} (circuit: {circuit_state['state']})")
    except Exception as e:
        logger.warning(f"⚠️  LLM service: {e}")
    
    logger.info("=" * 60)
    logger.info("🚀 Server ready to accept requests")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("🛑 Chirag Clone API shutting down...")
    
    # Cleanup HTTP connection pool
    try:
        from services.http_pool import cleanup_http_pool
        await cleanup_http_pool()
        logger.info("✅ HTTP connection pool closed")
    except Exception as e:
        logger.warning(f"⚠️ HTTP pool cleanup: {e}")
    
    # Clear cache
    try:
        from services.cache_service import get_cache_service
        cache = get_cache_service()
        stats = cache.get_stats()
        cache.clear()
        logger.info(f"✅ Cache cleared (was {stats['size']} entries, {stats['hit_rate']}% hit rate)")
    except Exception as e:
        logger.warning(f"⚠️ Cache cleanup: {e}")

# ============= Router Registration =============

# Auth routes (already existed)
from routes.auth import router as auth_router
app.include_router(auth_router)

# Chat routes
from routes.chat import router as chat_router
app.include_router(chat_router)

# Training routes (includes uploads, facts, journal, examples)
from routes.training import router as training_router
app.include_router(training_router)

# Dashboard routes (includes health, stats, profile, analytics, visualization)
from routes.dashboard import router as dashboard_router
app.include_router(dashboard_router)

# Autopilot routes (Discord, Telegram, Twitter, LinkedIn, Gmail, WhatsApp)
from routes.autopilot import router as autopilot_router
app.include_router(autopilot_router)

# Voice routes (TTS, STT, real-time streaming)
from routes.voice import router as voice_router
app.include_router(voice_router)

# Cognitive routes (core memory, active learning)
from routes.cognitive import router as cognitive_router
app.include_router(cognitive_router)

# Knowledge routes (documents, querying, memory search)
from routes.knowledge import router as knowledge_router
app.include_router(knowledge_router)

# Vision routes (desktop analysis, image analysis)
from routes.vision import router as vision_router
app.include_router(vision_router)

# Agent routes (web browsing)
from routes.agent import router as agent_router
app.include_router(agent_router)

# Features routes (creative, personality history, calendar, quiz, research, rewind)
from routes.features import router as features_router
app.include_router(features_router)

# Fine-tune routes (dataset preparation)
from routes.finetune import router as finetune_router
app.include_router(finetune_router)

# Local training routes (LoRA fine-tuning, training jobs)
from routes.local_training import router as local_training_router
app.include_router(local_training_router)

# ============= Static Frontend Serving =============

frontend_path = pathlib.Path(__file__).parent.parent / "frontend-react" / "dist"
if frontend_path.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_path / "assets")), name="static")
    
    @app.get("/")
    async def serve_spa():
        return FileResponse(str(frontend_path / "index.html"))
    
    @app.get("/{path:path}")
    async def serve_spa_routes(path: str):
        # Return 404 for API routes that fell through
        if path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API endpoint not found")
            
        # Serve index.html for all non-API routes (SPA routing)
        file_path = frontend_path / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_path / "index.html"))

# ============= Entry Point =============

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
