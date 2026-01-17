from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import uvicorn
import os
import logging
import time
from config import Config, validate_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import rate limiter


# Import robustness utilities
from services.robustness import (
    RequestValidationMiddleware,
    GlobalExceptionMiddleware,
    get_health_monitor,
    check_service_health,
    safe_service_call,
    GracefulDegradation,
    validate_input_length,
    create_robust_response
)

# Validate configuration at startup
config_warnings = validate_config()
for warning in config_warnings:
    logger.warning(f"[CONFIG] {warning}")

app = FastAPI(
    title="Chirag Clone API",
    description="Personal AI Clone Bot API - v2.3 with Real-Time Voice, Vision, and Brain Station",
    version="2.3.0"
)

# Add robustness middleware
app.add_middleware(GlobalExceptionMiddleware)
app.add_middleware(RequestValidationMiddleware, max_body_size=Config.MAX_REQUEST_SIZE_MB * 1024 * 1024)

# Add Security Headers (CSP, XSS Protection)
from middleware.security import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware, csp_policy="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' ws: wss: https:;")

# Add GZip compression for optimized response sizes (60-80% smaller)
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=500)  # Compress responses > 500 bytes

# CORS Configuration - allow all localhost ports for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:5177", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175", "http://127.0.0.1:5176", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Rate Limiting Middleware
from services.rate_limiter import rate_limit
app.middleware("http")(rate_limit)

# Startup event for initialization
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

# Serve static frontend in production
import pathlib
frontend_path = pathlib.Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_path / "assets")), name="static")
    
    @app.get("/")
    async def serve_spa():
        return FileResponse(str(frontend_path / "index.html"))
    
    @app.get("/{path:path}")
    async def serve_spa_routes(path: str):
        # Serve index.html for all non-API routes (SPA routing)
        file_path = frontend_path / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_path / "index.html"))

# Request Models with validation
class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=Config.MAX_MESSAGE_LENGTH)
    session_id: str = Field(default="default", max_length=100)
    training_mode: bool = False
    
    @validator('message')
    def sanitize_message(cls, v):
        # Strip leading/trailing whitespace
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        return v
    
    @validator('session_id')
    def sanitize_session_id(cls, v):
        # Remove any potentially dangerous characters
        import re
        v = re.sub(r'[^a-zA-Z0-9_-]', '', v)
        return v or "default"

class TrainingFeedback(BaseModel):
    context: str = Field(..., min_length=1, max_length=Config.MAX_MESSAGE_LENGTH)
    correct_response: Optional[str] = Field(default=None, max_length=Config.MAX_MESSAGE_LENGTH)
    bot_response: Optional[str] = Field(default=None, max_length=Config.MAX_MESSAGE_LENGTH)
    accepted: bool = False

# Dependencies (Lazy loading services)
async def get_chat_service():
    from services.chat_service import get_chat_service as _get_service
    return _get_service()

# --- Auth Routes ---
from routes.auth import router as auth_router
app.include_router(auth_router)

# --- Routes ---

@app.get("/api/system/metrics")
async def system_metrics():
    """
    Get system performance metrics.
    Useful for monitoring cache efficiency, memory usage, and connection pool status.
    """
    import psutil
    import os
    
    metrics = {
        "timestamp": time.time(),
        "process": {}
    }
    
    # Process memory
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        metrics["process"] = {
            "memory_mb": round(memory_info.rss / (1024 * 1024), 2),
            "cpu_percent": process.cpu_percent(),
            "threads": process.num_threads()
        }
    except Exception:
        pass
    
    # Cache stats
    try:
        from services.cache_service import get_cache_service
        cache = get_cache_service()
        metrics["cache"] = cache.get_stats()
    except Exception:
        metrics["cache"] = {"available": False}
    
    # HTTP pool stats
    try:
        from services.http_pool import get_http_pool
        pool = get_http_pool()
        if pool._session and not pool._session.closed:
            connector = pool._session.connector
            metrics["http_pool"] = {
                "active": True,
                "limit": connector.limit if connector else 0,
                "limit_per_host": connector.limit_per_host if connector else 0
            }
        else:
            metrics["http_pool"] = {"active": False}
    except Exception:
        metrics["http_pool"] = {"available": False}
    
    return metrics

@app.get("/api/health")
async def health_check(detailed: bool = False):
    """
    Health Check Endpoint.
    
    Args:
        detailed: If true, includes service-level health status
        
    Returns:
        Health status with optional service details
    """
    import asyncio
    
    health_monitor = get_health_monitor()
    
    # Basic health info
    response = {
        "status": "healthy",
        "version": "2.3.0",
        "framework": "FastAPI",
        "timestamp": time.time()
    }
    
    if detailed:
        # Check LLM service
        try:
            from services.llm_service import get_llm_service
            llm = get_llm_service()
            circuit_state = llm.get_circuit_state()
            health_monitor.update_status(
                "llm",
                not circuit_state.get("is_open", False),
                f"Circuit: {circuit_state.get('state', 'UNKNOWN')}"
            )
        except Exception as e:
            health_monitor.update_status("llm", False, str(e))
        
        # Check memory/vector service
        try:
            from services.memory_service import get_memory_service
            memory = get_memory_service()
            stats = memory.get_training_stats()
            health_monitor.update_status("memory", True, f"{stats.get('total_entries', 0)} entries")
        except Exception as e:
            health_monitor.update_status("memory", False, str(e))
        
        # Check voice service
        try:
            from services.voice_service import get_voice_service
            voice = get_voice_service()
            voice_status = voice.get_status()
            health_monitor.update_status(
                "voice",
                voice_status.get("tts_available", False) or voice_status.get("stt_available", False),
                f"TTS: {voice_status.get('tts_available')}, STT: {voice_status.get('stt_available')}"
            )
        except Exception as e:
            health_monitor.update_status("voice", False, str(e))
        
        # Check knowledge service
        try:
            from services.knowledge_service import get_knowledge_service
            knowledge = get_knowledge_service()
            doc_count = len(knowledge.list_documents()) if hasattr(knowledge, 'list_documents') else 0
            health_monitor.update_status("knowledge", True, f"{doc_count} documents")
        except Exception as e:
            health_monitor.update_status("knowledge", False, str(e))
        
        # Get overall health
        is_healthy, degraded_services, message = health_monitor.get_overall_health()
        
        response["status"] = "healthy" if is_healthy else "unhealthy"
        response["message"] = message
        response["services"] = health_monitor.get_all_status()
        
        if degraded_services:
            response["degraded_services"] = degraded_services
            if is_healthy:
                response["status"] = "degraded"
    
    return response

@app.post("/api/chat/message")

async def chat_message(data: ChatMessage):
    """Handle chat messages"""
    try:
        service = await get_chat_service()
        
        # Run synchronous service in threadpool to avoid blocking event loop
        import asyncio
        response, confidence, mood_data, thinking_data = await asyncio.to_thread(
            service.generate_response, 
            data.message, 
            data.session_id,
            True, # include_examples
            data.training_mode
        )
        
        return {
            "response": response,
            "session_id": data.session_id,
            "confidence": confidence,
            "mood": mood_data,
            "thinking": thinking_data
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/training/feedback")

async def training_feedback(data: TrainingFeedback):
    """Handle training feedback"""
    try:
        service = await get_chat_service()
        if data.accepted:
            # Positive reinforcement: Add to examples if not already present
            if data.context and data.bot_response:
                from services.personality_service import get_personality_service
                personality = get_personality_service()
                personality.add_example(data.context, data.bot_response)
                
                # Also verify with memory service (add as training data)
                from services.memory_service import get_memory_service
                memory = get_memory_service()
                memory.add_training_example(data.context, data.bot_response, source="user_feedback")
                
        elif data.correct_response:
            # Negative feedback with correction
            # Run in threadpool as it uses synchronous logic internally
            import asyncio
            await asyncio.to_thread(service.train_from_interaction, data.context, data.correct_response)
            
        return {"success": True}
    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/visualization/graph")
async def get_memory_graph():
    """Get graph data for visualization"""
    try:
        from services.personality_service import get_personality_service
        personality = get_personality_service().get_profile()
        
        # Build graph structure compatible with React Flow or similar
        nodes = []
        edges = []
        
        # Central Node
        nodes.append({"id": "root", "label": personality.name, "type": "root", "data": {"label": personality.name}})
        
        # Categories
        categories = ["Personality", "Facts", "Quirks"]
        for cat in categories:
            cat_id = f"cat_{cat.lower()}"
            nodes.append({"id": cat_id, "label": cat, "type": "category", "data": {"label": cat}})
            edges.append({"id": f"e_root_{cat_id}", "source": "root", "target": cat_id})
            
        # Add Quirks
        for i, quirk in enumerate(personality.typing_quirks[:5]):
            node_id = f"quirk_{i}"
            nodes.append({"id": node_id, "label": quirk, "type": "leaf", "data": {"label": quirk}})
            edges.append({"id": f"e_cat_quirks_{node_id}", "source": "cat_quirks", "target": node_id})
            
        # Add Facts
        for i, fact in enumerate(personality.facts[:5]):
            node_id = f"fact_{i}"
            nodes.append({"id": node_id, "label": fact[:20]+"...", "type": "leaf", "data": {"label": fact}})
            edges.append({"id": f"e_cat_facts_{node_id}", "source": "cat_facts", "target": node_id})
            
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        logger.error(f"Graph error: {e}")
        return {"nodes": [], "edges": []}

@app.get("/api/profile")
async def get_profile():
    """Get full personality profile for the About Me page"""
    try:
        from services.personality_service import get_personality_service
        from services.memory_service import get_memory_service
        
        personality = get_personality_service().get_profile()
        memory = get_memory_service()
        stats = memory.get_training_stats()
        
        # Generate AI summary
        tone_desc = []
        if personality.tone_markers.get('casual', 0) > 0.6:
            tone_desc.append("casual and laid-back")
        if personality.tone_markers.get('sarcastic', 0) > 0.4:
            tone_desc.append("witty with a hint of sarcasm")
        if personality.tone_markers.get('enthusiastic', 0) > 0.6:
            tone_desc.append("enthusiastic and energetic")
        if personality.tone_markers.get('brief', 0) > 0.6:
            tone_desc.append("concise and to-the-point")
        
        summary = f"{personality.name} communicates in a {', '.join(tone_desc) if tone_desc else 'balanced'} style. "
        if personality.typing_quirks:
            summary += f"They often use phrases like '{personality.typing_quirks[0]}'. "
        if personality.emoji_patterns:
            top_emoji = list(personality.emoji_patterns.keys())[:3]
            summary += f"Favorite emojis include {' '.join(top_emoji)}. "
        
        return {
            "name": personality.name,
            "summary": summary,
            "facts": personality.facts,
            "quirks": personality.typing_quirks,
            "emojis": personality.emoji_patterns,
            "tone_markers": personality.tone_markers,
            "avg_message_length": personality.avg_message_length,
            "training_examples": stats.get('total_examples', 0),
            "common_phrases": personality.common_phrases[:10]
        }
    except Exception as e:
        logger.error(f"Profile error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        memory = get_memory_service()
        personality = get_personality_service().get_profile()
        stats = memory.get_training_stats()
        
        return {
            "total_training_examples": stats.get('total_examples', 0),
            "facts_count": len(personality.facts),
            "quirks_count": len(personality.typing_quirks),
            "emoji_count": len(personality.emoji_patterns),
            "sources": stats.get('sources', {}),
            "personality_completion": min(100, int(
                (len(personality.facts) * 5) + 
                (len(personality.typing_quirks) * 3) + 
                (stats.get('total_examples', 0) * 0.5)
            ))
        }
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return {
            "total_training_examples": 0,
            "facts_count": 0,
            "quirks_count": 0,
            "emoji_count": 0,
            "sources": {},
            "personality_completion": 0
        }

# Training PIN (simple auth - in production use proper auth)
TRAINING_PIN = os.environ.get("TRAINING_PIN", "1234")

class JournalEntry(BaseModel):
    content: str
    
class FactEntry(BaseModel):
    fact: str

class TrainingExample(BaseModel):
    context: str
    response: str

@app.post("/api/training/auth")
async def verify_training_auth(pin: str = Form(...)):
    """Verify training PIN"""
    if pin == TRAINING_PIN:
        return {"success": True, "message": "Authenticated"}
    raise HTTPException(status_code=401, detail="Invalid PIN")

@app.post("/api/training/upload/whatsapp")
async def upload_whatsapp(
    file: UploadFile = File(...),
    your_name: str = Form(...)
):
    """Upload WhatsApp chat export"""
    try:
        import asyncio
        from parsers import WhatsAppParser
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        content = await file.read()
        content_str = content.decode('utf-8', errors='replace')
        
        parser = WhatsAppParser(your_name)
        result = await asyncio.to_thread(parser.parse_content, content_str)
        
        memory = get_memory_service()
        personality = get_personality_service()
        
        added = memory.add_training_examples_batch(result['conversation_pairs'], source='whatsapp')
        personality.analyze_messages(result['your_texts'])
        
        return {
            "success": True,
            "total_messages": result['total_messages'],
            "your_messages": result['your_messages'],
            "training_examples_added": added
        }
    except Exception as e:
        logger.error(f"WhatsApp upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/training/upload/instagram")
async def upload_instagram(
    file: UploadFile = File(...),
    your_username: str = Form(...)
):
    """Upload Instagram DM export"""
    try:
        import asyncio
        from parsers import InstagramParser
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        content = await file.read()
        content_str = content.decode('utf-8', errors='replace')
        
        parser = InstagramParser(your_username)
        result = await asyncio.to_thread(parser.parse_content, content_str)
        
        memory = get_memory_service()
        personality = get_personality_service()
        
        added = memory.add_training_examples_batch(result['conversation_pairs'], source='instagram')
        personality.analyze_messages(result['your_texts'])
        
        return {
            "success": True,
            "total_messages": result['total_messages'],
            "your_messages": result['your_messages'],
            "training_examples_added": added
        }
    except Exception as e:
        logger.error(f"Instagram upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/training/upload/discord")
async def upload_discord(
    file: UploadFile = File(...),
    your_username: str = Form(...)
):
    """Upload Discord chat export"""
    try:
        import asyncio
        from parsers import DiscordParser
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        content = await file.read()
        content_str = content.decode('utf-8', errors='replace')
        
        parser = DiscordParser(your_user_id=None, your_username=your_username)
        result = await asyncio.to_thread(parser.parse_content, content_str, 'json')
        
        memory = get_memory_service()
        personality = get_personality_service()
        
        added = memory.add_training_examples_batch(result['conversation_pairs'], source='discord')
        personality.analyze_messages(result['your_texts'])
        
        return {
            "success": True,
            "total_messages": result['total_messages'],
            "your_messages": result['your_messages'],
            "training_examples_added": added
        }
    except Exception as e:
        logger.error(f"Discord upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/training/journal")
async def add_journal_entry(entry: JournalEntry):
    """Add a journal/thought entry"""
    try:
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        memory = get_memory_service()
        personality = get_personality_service()
        
        # Store as training example with generic context
        memory.add_training_example(
            context="What are you thinking about?",
            response=entry.content,
            source="journal"
        )
        personality.analyze_messages([entry.content])
        
        return {"success": True, "message": "Journal entry saved"}
    except Exception as e:
        logger.error(f"Journal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/training/fact")
async def add_fact(entry: FactEntry):
    """Add a personal fact"""
    try:
        from services.personality_service import get_personality_service
        personality = get_personality_service()
        personality.add_fact(entry.fact)
        return {"success": True, "facts": personality.get_profile().facts}
    except Exception as e:
        logger.error(f"Add fact error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/training/facts")
async def get_facts():
    """Get all stored facts"""
    try:
        from services.personality_service import get_personality_service
        personality = get_personality_service()
        return {"facts": personality.get_profile().facts}
    except Exception as e:
        logger.error(f"Get facts error: {e}")
        return {"facts": []}

@app.delete("/api/training/facts/{index}")
async def delete_fact(index: int):
    """Delete a fact by index"""
    try:
        from services.personality_service import get_personality_service
        personality = get_personality_service()
        facts = personality.get_profile().facts
        if 0 <= index < len(facts):
            facts.pop(index)
            personality.save_profile()
            return {"success": True, "facts": facts}
        raise HTTPException(status_code=400, detail="Invalid index")
    except Exception as e:
        logger.error(f"Delete fact error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/training/example")
async def add_training_example(example: TrainingExample):
    """Add a direct training example"""
    try:
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        memory = get_memory_service()
        personality = get_personality_service()
        
        memory.add_training_example(example.context, example.response, source='manual')
        personality.add_example(example.context, example.response)
        
        return {"success": True, "message": "Example added"}
    except Exception as e:
        logger.error(f"Add example error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/training/stats")
async def get_training_stats():
    """Get training statistics"""
    try:
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        memory = get_memory_service()
        personality = get_personality_service().get_profile()
        stats = memory.get_training_stats()
        
        return {
            "total_examples": stats.get('total_examples', 0),
            "sources": stats.get('sources', {}),
            "facts_count": len(personality.facts),
            "quirks_count": len(personality.typing_quirks)
        }
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        return {"total_examples": 0, "sources": {}, "facts_count": 0, "quirks_count": 0}

@app.post("/api/training/upload/document")
async def upload_document(
    file: UploadFile = File(...)
):
    """Upload PDF or text document for learning"""
    try:
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        content = await file.read()
        filename = file.filename or "document"
        
        text_content = ""
        
        if filename.lower().endswith('.pdf'):
            # Extract text from PDF
            try:
                import fitz  # PyMuPDF
                import io
                pdf_doc = fitz.open(stream=content, filetype="pdf")
                for page in pdf_doc:
                    text_content += page.get_text()
                pdf_doc.close()
            except Exception as e:
                logger.error(f"PDF parsing error: {e}")
                raise HTTPException(status_code=400, detail="Failed to parse PDF")
        else:
            # Plain text file
            text_content = content.decode('utf-8', errors='replace')
        
        if not text_content.strip():
            raise HTTPException(status_code=400, detail="Document is empty")
        
        # Store document content as training data
        memory = get_memory_service()
        personality = get_personality_service()
        
        # Split into chunks and analyze
        chunks = [text_content[i:i+500] for i in range(0, min(len(text_content), 5000), 500)]
        for chunk in chunks:
            memory.add_training_example(
                context="From my documents",
                response=chunk.strip(),
                source="document"
            )
        
        personality.analyze_messages([text_content[:5000]])
        
        return {
            "success": True,
            "filename": filename,
            "characters_processed": len(text_content),
            "message": f"Processed document: {filename}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TrainingChatMessage(BaseModel):
    bot_message: str
    user_response: str

@app.post("/api/training/chat")
async def training_chat_response(msg: TrainingChatMessage):
    """
    Train by chatting - the bot says something and user responds.
    The user's response is what gets learned.
    """
    try:
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        memory = get_memory_service()
        personality = get_personality_service()
        
        # Store user's response as training data
        memory.add_training_example(
            context=msg.bot_message,
            response=msg.user_response,
            source="training_chat"
        )
        personality.analyze_messages([msg.user_response])
        personality.add_example(msg.bot_message, msg.user_response)
        
        return {"success": True, "message": "Response learned"}
    except Exception as e:
        logger.error(f"Training chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/training/chat/prompt")
async def get_training_prompt():
    """Get a random prompt for training chat"""
    import random
    prompts = [
        "Hey, what's up?",
        "How was your day?",
        "What are you working on?",
        "Any plans for the weekend?",
        "Did you watch anything good lately?",
        "What's on your mind?",
        "How do you feel about that?",
        "Tell me something interesting",
        "What do you think about AI?",
        "What's your favorite thing to do?",
        "How would you describe yourself?",
        "What motivates you?",
        "What's something you learned recently?",
        "If you could do anything today, what would it be?",
        "What's your opinion on social media?",
    ]
    return {"prompt": random.choice(prompts)}

@app.delete("/api/training/reset")
async def reset_all_training():
    """Reset all learning data - use with caution!"""
    try:
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        memory = get_memory_service()
        personality = get_personality_service()
        
        # Clear training data
        memory.clear_training_data()
        
        # Clear personality profile
        profile = personality.get_profile()
        profile.facts = []
        profile.typing_quirks = []
        profile.emoji_patterns = {}
        profile.response_examples = []
        profile.common_phrases = []
        personality.save_profile()
        
        logger.warning("All training data reset by user request")
        return {"success": True, "message": "All learning data has been reset"}
    except Exception as e:
        logger.error(f"Reset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/detailed")
async def get_detailed_analytics():
    """Get detailed analytics for dashboard visualizations"""
    try:
        from services.memory_service import get_memory_service
        from services.personality_service import get_personality_service
        
        memory = get_memory_service()
        personality = get_personality_service().get_profile()
        stats = memory.get_training_stats()
        
        return {
            "training": {
                "total_examples": stats.get('total_examples', 0),
                "sources": stats.get('sources', {}),
                "recent_activity": stats.get('recent_activity', [])
            },
            "personality": {
                "facts_count": len(personality.facts),
                "quirks_count": len(personality.typing_quirks),
                "emoji_count": len(personality.emoji_patterns),
                "avg_message_length": personality.avg_message_length,
                "tone_markers": personality.tone_markers,
                "common_phrases": personality.common_phrases[:20],
                "top_emojis": dict(sorted(personality.emoji_patterns.items(), key=lambda x: x[1], reverse=True)[:10])
            },
            "learning_progress": {
                "personality_score": min(100, int(
                    (len(personality.facts) * 5) + 
                    (len(personality.typing_quirks) * 3) + 
                    (stats.get('total_examples', 0) * 0.5)
                )),
                "data_sources_count": len(stats.get('sources', {}))
            }
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return {
            "training": {"total_examples": 0, "sources": {}, "recent_activity": []},
            "personality": {"facts_count": 0, "quirks_count": 0, "emoji_count": 0, "avg_message_length": 0, "tone_markers": {}, "common_phrases": [], "top_emojis": {}},
            "learning_progress": {"personality_score": 0, "data_sources_count": 0}
        }

# ============= AUTOPILOT ENDPOINTS =============

# Lazy bot instances
_discord_bot = None
_telegram_bot = None

def _get_bots():
    """Get bot instances lazily."""
    global _discord_bot, _telegram_bot
    
    if _discord_bot is None:
        from services.discord_bot_service import get_discord_bot_service
        from services.telegram_bot_service import get_telegram_bot_service
        from services.chat_service import get_chat_service
        
        chat_service = get_chat_service()
        _discord_bot = get_discord_bot_service(chat_service)
        _telegram_bot = get_telegram_bot_service(chat_service)
    
    return _discord_bot, _telegram_bot

@app.get("/api/autopilot/status")
async def get_autopilot_status():
    """Get status of all autopilot bots."""
    try:
        discord_bot, telegram_bot = _get_bots()
        
        return {
            "discord": discord_bot.get_status() if discord_bot else {"configured": False, "running": False},
            "telegram": telegram_bot.get_status() if telegram_bot else {"configured": False, "running": False}
        }
    except Exception as e:
        logger.error(f"Autopilot status error: {e}")
        return {
            "discord": {"configured": False, "running": False, "error": str(e)},
            "telegram": {"configured": False, "running": False}
        }

@app.post("/api/autopilot/discord/start")
async def start_discord_autopilot():
    """Start the Discord autopilot."""
    try:
        discord_bot, _ = _get_bots()
        
        if not discord_bot:
            return {"success": False, "error": "Discord bot not available"}
        
        success = discord_bot.start()
        return {
            "success": success,
            "message": "Discord autopilot started" if success else "Failed to start - check DISCORD_BOT_TOKEN in .env",
            "status": discord_bot.get_status()
        }
    except Exception as e:
        logger.error(f"Discord start error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/autopilot/discord/stop")
async def stop_discord_autopilot():
    """Stop the Discord autopilot."""
    try:
        discord_bot, _ = _get_bots()
        
        if discord_bot:
            discord_bot.stop()
        
        return {"success": True, "message": "Discord autopilot stopped"}
    except Exception as e:
        logger.error(f"Discord stop error: {e}")
        return {"success": False, "error": str(e)}

class AutopilotSettings(BaseModel):
    auto_reply_dms: bool = None
    auto_reply_mentions: bool = None
    auto_reply_enabled: bool = None

@app.post("/api/autopilot/discord/settings")
async def update_discord_settings(settings: AutopilotSettings):
    """Update Discord bot settings."""
    try:
        discord_bot, _ = _get_bots()
        
        if discord_bot:
            if settings.auto_reply_dms is not None:
                discord_bot.auto_reply_dms = settings.auto_reply_dms
            if settings.auto_reply_mentions is not None:
                discord_bot.auto_reply_mentions = settings.auto_reply_mentions
        
        return {"success": True, "status": discord_bot.get_status() if discord_bot else {}}
    except Exception as e:
        logger.error(f"Discord settings error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/autopilot/telegram/start")
async def start_telegram_autopilot():
    """Start the Telegram autopilot."""
    try:
        _, telegram_bot = _get_bots()
        
        if not telegram_bot:
            return {"success": False, "error": "Telegram bot not available"}
        
        success = telegram_bot.start()
        return {
            "success": success,
            "message": "Telegram autopilot started" if success else "Failed to start - check TELEGRAM_BOT_TOKEN in .env",
            "status": telegram_bot.get_status()
        }
    except Exception as e:
        logger.error(f"Telegram start error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/autopilot/telegram/stop")
async def stop_telegram_autopilot():
    """Stop the Telegram autopilot."""
    try:
        _, telegram_bot = _get_bots()
        
        if telegram_bot:
            telegram_bot.stop()
        
        return {"success": True, "message": "Telegram autopilot stopped"}
    except Exception as e:
        logger.error(f"Telegram stop error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/autopilot/telegram/settings")
async def update_telegram_settings(settings: AutopilotSettings):
    """Update Telegram bot settings."""
    try:
        _, telegram_bot = _get_bots()
        
        if telegram_bot and settings.auto_reply_enabled is not None:
            telegram_bot.auto_reply_enabled = settings.auto_reply_enabled
        
        return {"success": True, "status": telegram_bot.get_status() if telegram_bot else {}}
    except Exception as e:
        logger.error(f"Telegram settings error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/autopilot/logs")
async def get_autopilot_logs():
    """Get recent auto-reply logs from all platforms."""
    try:
        discord_bot, telegram_bot = _get_bots()
        
        logs = []
        if discord_bot:
            logs.extend(discord_bot.get_reply_log())
        if telegram_bot:
            logs.extend(telegram_bot.get_reply_log())
        
        # Sort by timestamp
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {"logs": logs[:50]}
    except Exception as e:
        logger.error(f"Autopilot logs error: {e}")
        return {"logs": []}

# ============= COGNITIVE ENHANCEMENT ENDPOINTS =============

class ActiveLearningAnswer(BaseModel):
    question: str
    answer: str
    domain: str = ""

@app.get("/api/cognitive/core-memories")
async def get_core_memories(category: Optional[str] = None, limit: int = 50):
    """Get all stored core memories."""
    try:
        from services.core_memory_service import get_core_memory_service
        service = get_core_memory_service()
        memories = service.get_core_memories(category=category, limit=limit)
        stats = service.get_stats()
        return {"memories": memories, "stats": stats}
    except Exception as e:
        logger.error(f"Core memories error: {e}")
        return {"memories": [], "stats": {}}

@app.delete("/api/cognitive/core-memories/{memory_id}")
async def delete_core_memory(memory_id: str):
    """Delete a core memory by ID."""
    try:
        from services.core_memory_service import get_core_memory_service
        service = get_core_memory_service()
        success = service.delete_core_memory(memory_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Delete core memory error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/cognitive/trigger-summarization")
async def trigger_memory_summarization(days_back: int = 1):
    """Manually trigger memory summarization."""
    try:
        import asyncio
        from services.core_memory_service import get_core_memory_service
        service = get_core_memory_service()
        
        # Run in threadpool to avoid blocking
        new_memories = await asyncio.to_thread(
            service.summarize_recent_conversations,
            days_back=days_back
        )
        
        return {
            "success": True,
            "new_memories_count": len(new_memories),
            "new_memories": new_memories
        }
    except Exception as e:
        logger.error(f"Summarization error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/cognitive/active-learning/suggestions")
async def get_active_learning_suggestions(max_questions: int = 3):
    """Get proactive questions to fill knowledge gaps."""
    try:
        from services.active_learning_service import get_active_learning_service
        service = get_active_learning_service()
        questions = service.generate_proactive_questions(max_questions=max_questions)
        stats = service.get_learning_stats()
        return {"questions": questions, "stats": stats}
    except Exception as e:
        logger.error(f"Active learning error: {e}")
        return {"questions": [], "stats": {}}

@app.post("/api/cognitive/active-learning/answer")
async def submit_active_learning_answer(data: ActiveLearningAnswer):
    """Submit an answer to a proactive question."""
    try:
        import asyncio
        from services.active_learning_service import get_active_learning_service
        service = get_active_learning_service()
        
        result = await asyncio.to_thread(
            service.process_answer,
            data.question,
            data.answer,
            data.domain
        )
        
        return result
    except Exception as e:
        logger.error(f"Active learning answer error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/cognitive/learning-stats")
async def get_cognitive_learning_stats():
    """Get comprehensive learning statistics."""
    try:
        from services.active_learning_service import get_active_learning_service
        from services.core_memory_service import get_core_memory_service
        
        active_service = get_active_learning_service()
        core_service = get_core_memory_service()
        
        return {
            "active_learning": active_service.get_learning_stats(),
            "core_memories": core_service.get_stats()
        }
    except Exception as e:
        logger.error(f"Learning stats error: {e}")
        return {"active_learning": {}, "core_memories": {}}

# ============= NEW AUTOPILOT INTEGRATIONS =============

class DraftRequest(BaseModel):
    text: str
    topic: str = ""

# Twitter/X Endpoints
@app.get("/api/autopilot/twitter/status")
async def get_twitter_status():
    """Get Twitter autopilot status."""
    try:
        from services.twitter_bot_service import get_twitter_bot_service
        service = get_twitter_bot_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Twitter status error: {e}")
        return {"platform": "twitter", "configured": False, "error": str(e)}

@app.get("/api/autopilot/twitter/drafts")
async def get_twitter_drafts(status: Optional[str] = None):
    """Get Twitter draft queue."""
    try:
        from services.twitter_bot_service import get_twitter_bot_service
        service = get_twitter_bot_service()
        return {"drafts": service.get_drafts(status)}
    except Exception as e:
        logger.error(f"Twitter drafts error: {e}")
        return {"drafts": []}

@app.post("/api/autopilot/twitter/generate-tweet")
async def generate_tweet_draft(request: DraftRequest):
    """Generate a tweet draft."""
    try:
        from services.twitter_bot_service import get_twitter_bot_service
        service = get_twitter_bot_service()
        draft = service.generate_tweet_draft(request.topic)
        return draft
    except Exception as e:
        logger.error(f"Generate tweet error: {e}")
        return {"error": str(e)}

@app.post("/api/autopilot/twitter/generate-reply")
async def generate_twitter_reply(request: DraftRequest):
    """Generate a reply draft."""
    try:
        from services.twitter_bot_service import get_twitter_bot_service
        service = get_twitter_bot_service()
        draft = service.generate_reply_draft(request.text)
        return draft
    except Exception as e:
        logger.error(f"Generate reply error: {e}")
        return {"error": str(e)}

# LinkedIn Endpoints
@app.get("/api/autopilot/linkedin/status")
async def get_linkedin_status():
    """Get LinkedIn autopilot status."""
    try:
        from services.linkedin_bot_service import get_linkedin_bot_service
        service = get_linkedin_bot_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"LinkedIn status error: {e}")
        return {"platform": "linkedin", "configured": False, "error": str(e)}

@app.get("/api/autopilot/linkedin/drafts")
async def get_linkedin_drafts(status: Optional[str] = None):
    """Get LinkedIn draft queue."""
    try:
        from services.linkedin_bot_service import get_linkedin_bot_service
        service = get_linkedin_bot_service()
        return {"drafts": service.get_drafts(status)}
    except Exception as e:
        logger.error(f"LinkedIn drafts error: {e}")
        return {"drafts": []}

@app.post("/api/autopilot/linkedin/generate-reply")
async def generate_linkedin_reply(request: DraftRequest):
    """Generate a LinkedIn reply draft."""
    try:
        from services.linkedin_bot_service import get_linkedin_bot_service
        service = get_linkedin_bot_service()
        draft = service.generate_reply_draft(request.text)
        return draft
    except Exception as e:
        logger.error(f"Generate LinkedIn reply error: {e}")
        return {"error": str(e)}

# Gmail Endpoints
@app.get("/api/autopilot/gmail/status")
async def get_gmail_status():
    """Get Gmail autopilot status."""
    try:
        from services.gmail_bot_service import get_gmail_bot_service
        service = get_gmail_bot_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Gmail status error: {e}")
        return {"platform": "gmail", "configured": False, "error": str(e)}

@app.get("/api/autopilot/gmail/drafts")
async def get_gmail_drafts(status: Optional[str] = None):
    """Get Gmail draft queue."""
    try:
        from services.gmail_bot_service import get_gmail_bot_service
        service = get_gmail_bot_service()
        return {"drafts": service.get_drafts(status)}
    except Exception as e:
        logger.error(f"Gmail drafts error: {e}")
        return {"drafts": []}

class EmailReplyRequest(BaseModel):
    subject: str
    body: str
    sender_name: str = "Someone"

@app.post("/api/autopilot/gmail/generate-reply")
async def generate_gmail_reply(request: EmailReplyRequest):
    """Generate an email reply draft."""
    try:
        from services.gmail_bot_service import get_gmail_bot_service
        service = get_gmail_bot_service()
        draft = service.generate_reply_draft(
            email_subject=request.subject,
            email_body=request.body,
            sender_name=request.sender_name
        )
        return draft
    except Exception as e:
        logger.error(f"Generate email reply error: {e}")
        return {"error": str(e)}

# ============= VOICE ENDPOINTS =============

class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None

class STTRequest(BaseModel):
    audio_base64: str
    audio_format: str = "webm"

@app.get("/api/voice/status")
async def get_voice_status():
    """Get voice service status."""
    try:
        from services.voice_service import get_voice_service
        service = get_voice_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Voice status error: {e}")
        return {"tts_enabled": False, "stt_enabled": False, "error": str(e)}

@app.post("/api/voice/speak")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech audio."""
    try:
        import asyncio
        from services.voice_service import get_voice_service
        service = get_voice_service()
        
        result = await asyncio.to_thread(
            service.text_to_speech,
            request.text,
            request.voice_id
        )
        return result
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"error": str(e)}

@app.post("/api/voice/listen")
async def speech_to_text(request: STTRequest):
    """Convert speech audio to text."""
    try:
        import asyncio
        from services.voice_service import get_voice_service
        service = get_voice_service()
        
        result = await asyncio.to_thread(
            service.speech_to_text_base64,
            request.audio_base64,
            request.audio_format
        )
        return result
    except Exception as e:
        logger.error(f"STT error: {e}")
        return {"error": str(e)}

@app.get("/api/voice/voices")
async def get_available_voices():
    """Get list of available TTS voices."""
    try:
        from services.voice_service import get_voice_service
        service = get_voice_service()
        voices = service.get_available_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error(f"Voices list error: {e}")
        return {"voices": []}


# ============= REAL-TIME VOICE STREAMING =============

class RealtimeAudioChunk(BaseModel):
    audio_base64: str
    audio_format: str = "webm"
    session_id: str = "default"

class RealtimeProcessRequest(BaseModel):
    session_id: str = "default"

@app.websocket("/api/voice/stream")
async def realtime_voice_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice streaming.
    
    Protocol:
    - Client sends JSON: {"type": "audio", "audio_base64": "...", "format": "webm"}
    - Client sends JSON: {"type": "end_turn"} to indicate they've stopped speaking
    - Client sends JSON: {"type": "interrupt"} to stop bot speech
    - Server sends JSON: {"type": "status", "is_bot_speaking": bool, "is_user_speaking": bool}
    - Server sends JSON: {"type": "transcript", "text": "..."}
    - Server sends JSON: {"type": "response", "text": "...", "audio_base64": "...", "format": "mp3"}
    """
    await websocket.accept()
    
    session_id = f"ws_{id(websocket)}"
    
    try:
        from services.realtime_voice_service import get_realtime_voice_service
        service = get_realtime_voice_service()
        
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "status": service.get_session_status(session_id)
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")
                
                if msg_type == "audio":
                    # Handle incoming audio chunk
                    result = await service.handle_audio_chunk(
                        session_id,
                        data.get("audio_base64", ""),
                        data.get("format", "webm")
                    )
                    
                    if result.get("status") == "interrupted":
                        await websocket.send_json({
                            "type": "interrupted",
                            "message": result.get("message", "")
                        })
                    
                elif msg_type == "end_turn":
                    # User finished speaking, process audio
                    result = await service.process_buffered_audio(session_id)
                    
                    if result.get("status") == "success":
                        # Send transcript
                        await websocket.send_json({
                            "type": "transcript",
                            "text": result.get("transcript", "")
                        })
                        
                        # Send response
                        await websocket.send_json({
                            "type": "response",
                            "text": result.get("response_text", ""),
                            "audio_base64": result.get("response_audio"),
                            "format": "mp3",
                            "confidence": result.get("confidence", 0),
                            "mood": result.get("mood", {})
                        })
                    elif result.get("status") == "error":
                        await websocket.send_json({
                            "type": "error",
                            "message": result.get("message", "Processing failed")
                        })
                
                elif msg_type == "interrupt":
                    # User interrupts bot speech
                    service.mark_bot_speech_complete(session_id)
                    await websocket.send_json({
                        "type": "interrupted",
                        "message": "Bot speech stopped"
                    })
                
                elif msg_type == "status":
                    # Send current status
                    await websocket.send_json({
                        "type": "status",
                        **service.get_session_status(session_id)
                    })
                
                elif msg_type == "bot_speech_complete":
                    # Client signals bot audio playback finished
                    service.mark_bot_speech_complete(session_id)
                
            except Exception as e:
                logger.error(f"WebSocket message error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up session
        try:
            from services.realtime_voice_service import get_realtime_voice_service
            service = get_realtime_voice_service()
            service.end_session(session_id)
        except Exception:
            pass

@app.post("/api/voice/realtime/chunk")
async def handle_realtime_audio_chunk(request: RealtimeAudioChunk):
    """HTTP fallback for sending audio chunks (for browsers without WebSocket)."""
    try:
        from services.realtime_voice_service import get_realtime_voice_service
        service = get_realtime_voice_service()
        
        result = await service.handle_audio_chunk(
            request.session_id,
            request.audio_base64,
            request.audio_format
        )
        return result
    except Exception as e:
        logger.error(f"Realtime chunk error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/voice/realtime/process")
async def process_realtime_audio(request: RealtimeProcessRequest):
    """HTTP fallback for processing buffered audio."""
    try:
        from services.realtime_voice_service import get_realtime_voice_service
        service = get_realtime_voice_service()
        
        result = await service.process_buffered_audio(request.session_id)
        return result
    except Exception as e:
        logger.error(f"Realtime process error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/voice/realtime/status/{session_id}")
async def get_realtime_session_status(session_id: str):
    """Get status of a real-time voice session."""
    try:
        from services.realtime_voice_service import get_realtime_voice_service
        service = get_realtime_voice_service()
        return service.get_session_status(session_id)
    except Exception as e:
        logger.error(f"Realtime status error: {e}")
        return {"error": str(e)}

# ============= DESKTOP VISION ENDPOINTS =============

class DesktopVisionRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/png"

@app.post("/api/vision/desktop")
async def analyze_desktop_screen(request: DesktopVisionRequest):
    """
    Analyze a desktop screenshot for proactive assistance.
    Returns a contextual suggestion based on what the user is viewing.
    """
    try:
        import asyncio
        from services.vision_service import get_vision_service
        from services.chat_service import get_chat_service
        
        vision_service = get_vision_service()
        
        if not vision_service.is_available():
            return {
                "success": False,
                "error": "Vision service not available. Set GEMINI_API_KEY."
            }
        
        # Analyze the screen
        analysis_result = await asyncio.to_thread(
            vision_service.analyze_image,
            request.image_base64,
            "Describe what you see on this desktop screen. Focus on the main application and what task the user appears to be working on.",
            request.mime_type
        )
        
        if not analysis_result.get("success"):
            return {
                "success": False,
                "error": analysis_result.get("error", "Analysis failed")
            }
        
        screen_description = analysis_result.get("description", "")
        
        # Generate proactive suggestion using chat service
        chat_service = get_chat_service()
        
        suggestion_prompt = f"""Based on what I can see on the user's screen:
{screen_description}

As their digital twin assistant, provide ONE brief, helpful suggestion or tip related to what they're doing. Be concise (1-2 sentences max). If nothing helpful comes to mind, respond with just "null"."""

        suggestion, _, _ = await asyncio.to_thread(
            chat_service.generate_response,
            suggestion_prompt,
            session_id="vision_proactive"
        )
        
        # Don't return trivial suggestions
        if suggestion.lower().strip() in ["null", "none", "", "n/a"]:
            return {
                "success": True,
                "suggestion": None,
                "screen_context": screen_description[:200]
            }
        
        return {
            "success": True,
            "suggestion": suggestion,
            "screen_context": screen_description[:200]
        }
        
    except Exception as e:
        logger.error(f"Desktop vision error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/vision/analyze")
async def analyze_image_endpoint(request: DesktopVisionRequest):
    """General image analysis endpoint."""
    try:
        import asyncio
        from services.vision_service import get_vision_service
        
        vision_service = get_vision_service()
        
        if not vision_service.is_available():
            return {
                "success": False,
                "error": "Vision service not available"
            }
        
        result = await asyncio.to_thread(
            vision_service.analyze_image,
            request.image_base64,
            "Describe what you see in this image in detail.",
            request.mime_type
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return {"success": False, "error": str(e)}

# ============= MEMORY SEARCH ENDPOINTS =============

@app.get("/api/memory/search")
async def search_memories(query: str, limit: int = 20, collection: Optional[str] = None):
    """Search across all memories."""
    try:
        from services.memory_search_service import get_memory_search_service
        service = get_memory_search_service()
        return service.search(query, limit, collection)
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        return {"error": str(e), "results": []}

@app.get("/api/memory/stats")
async def get_memory_stats():
    """Get memory statistics."""
    try:
        from services.memory_search_service import get_memory_search_service
        service = get_memory_search_service()
        return service.get_memory_stats()
    except Exception as e:
        return {"total_memories": 0, "error": str(e)}

# ============= CREATIVE STUDIO ENDPOINTS =============

class CreativeRequest(BaseModel):
    content_type: str
    topic: str = ""
    custom_prompt: Optional[str] = None

@app.get("/api/creative/types")
async def get_creative_types():
    """Get available creative content types."""
    try:
        from services.creative_service import get_creative_service
        service = get_creative_service()
        return {"types": service.get_content_types()}
    except Exception as e:
        return {"types": []}

@app.post("/api/creative/generate")
async def generate_creative_content(request: CreativeRequest):
    """Generate creative content."""
    try:
        import asyncio
        from services.creative_service import get_creative_service
        service = get_creative_service()
        result = await asyncio.to_thread(
            service.generate,
            request.content_type,
            request.topic,
            request.custom_prompt
        )
        return result
    except Exception as e:
        logger.error(f"Creative generation error: {e}")
        return {"error": str(e)}

@app.get("/api/creative/prompt")
async def get_daily_prompt():
    """Get daily creative writing prompt."""
    try:
        from services.creative_service import get_creative_service
        service = get_creative_service()
        return {"prompt": service.generate_daily_prompt()}
    except Exception as e:
        return {"prompt": "Write about something meaningful to you."}

# ============= KNOWLEDGE MANAGEMENT ENDPOINTS =============

class KnowledgeTextRequest(BaseModel):
    content: str
    title: str = "Quick Note"
    category: str = "general"

class KnowledgeUrlRequest(BaseModel):
    url: str
    category: str = "general"

class KnowledgeQueryRequest(BaseModel):
    query: str
    n_results: int = 5
    category: Optional[str] = None

@app.get("/api/knowledge/documents")
async def list_knowledge_documents():
    """List all indexed knowledge documents."""
    try:
        from services.knowledge_service import get_knowledge_service
        service = get_knowledge_service()
        documents = service.list_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Knowledge list error: {e}")
        return {"documents": [], "error": str(e)}

@app.get("/api/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge base statistics."""
    try:
        from services.knowledge_service import get_knowledge_service
        service = get_knowledge_service()
        return service.get_stats()
    except Exception as e:
        logger.error(f"Knowledge stats error: {e}")
        return {"total_documents": 0, "total_chunks": 0, "total_characters": 0, "error": str(e)}

@app.post("/api/knowledge/upload")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    category: str = Form("general"),
    title: Optional[str] = Form(None)
):
    """Upload a document to the knowledge base."""
    try:
        from services.knowledge_service import get_knowledge_service
        
        content = await file.read()
        filename = file.filename or "document.txt"
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'txt'
        
        service = get_knowledge_service()
        
        if ext == 'pdf':
            # Extract text from PDF
            try:
                import fitz
                import io
                pdf_doc = fitz.open(stream=content, filetype="pdf")
                text_content = ""
                for page in pdf_doc:
                    text_content += page.get_text() + "\n\n"
                pdf_doc.close()
            except Exception as e:
                return {"success": False, "error": f"PDF parsing failed: {e}"}
        else:
            text_content = content.decode('utf-8', errors='replace')
        
        if not text_content.strip():
            return {"success": False, "error": "Document is empty"}
        
        result = service.add_document(
            content=text_content,
            filename=filename,
            doc_type=ext,
            title=title,
            category=category
        )
        
        return {"success": True, **result}
        
    except Exception as e:
        logger.error(f"Knowledge upload error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/knowledge/text")
async def add_knowledge_text(request: KnowledgeTextRequest):
    """Add text content directly to knowledge base."""
    try:
        from services.knowledge_service import get_knowledge_service
        
        service = get_knowledge_service()
        result = service.add_document(
            content=request.content,
            filename=f"{request.title}.txt",
            doc_type="txt",
            title=request.title,
            category=request.category
        )
        
        return {"success": True, **result}
        
    except Exception as e:
        logger.error(f"Knowledge text error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/knowledge/url")
async def add_knowledge_from_url(request: KnowledgeUrlRequest):
    """Fetch and add content from a URL to knowledge base."""
    try:
        import asyncio
        import aiohttp
        from bs4 import BeautifulSoup
        from services.knowledge_service import get_knowledge_service
        
        # Fetch URL content
        async with aiohttp.ClientSession() as session:
            async with session.get(request.url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return {"success": False, "error": f"Failed to fetch URL: HTTP {response.status}"}
                html = await response.text()
        
        # Extract text from HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text
        text = soup.get_text(separator='\n', strip=True)
        
        if not text.strip():
            return {"success": False, "error": "No text content found at URL"}
        
        # Get page title
        title = soup.title.string if soup.title else request.url
        
        service = get_knowledge_service()
        result = service.add_document(
            content=text[:50000],  # Limit to 50K chars
            filename=f"url_{hash(request.url) % 10000}.txt",
            doc_type="url",
            title=title[:100],
            category=request.category
        )
        
        return {"success": True, **result}
        
    except Exception as e:
        logger.error(f"Knowledge URL error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/knowledge/query")
async def query_knowledge_base(request: KnowledgeQueryRequest):
    """Query the knowledge base for relevant content."""
    try:
        from services.knowledge_service import get_knowledge_service
        
        service = get_knowledge_service()
        results = service.query_knowledge(
            query=request.query,
            n_results=request.n_results,
            category=request.category
        )
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Knowledge query error: {e}")
        return {"results": [], "error": str(e)}

@app.delete("/api/knowledge/document/{doc_id}")
async def delete_knowledge_document(doc_id: str):
    """Delete a document from the knowledge base."""
    try:
        from services.knowledge_service import get_knowledge_service
        
        service = get_knowledge_service()
        success = service.delete_document(doc_id)
        
        return {"success": success}
        
    except Exception as e:
        logger.error(f"Knowledge delete error: {e}")
        return {"success": False, "error": str(e)}

# ============= PERSONALITY HISTORY ENDPOINTS =============

@app.post("/api/personality/snapshot")
async def take_personality_snapshot(note: str = ""):
    """Take a snapshot of current personality."""
    try:
        from services.personality_history_service import get_personality_history_service
        service = get_personality_history_service()
        return service.take_snapshot(note)
    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        return {"error": str(e)}

@app.get("/api/personality/history")
async def get_personality_history(limit: int = 20):
    """Get personality snapshot history."""
    try:
        from services.personality_history_service import get_personality_history_service
        service = get_personality_history_service()
        return {"snapshots": service.get_snapshots(limit)}
    except Exception as e:
        return {"snapshots": []}

@app.get("/api/personality/evolution")
async def get_personality_evolution():
    """Get personality evolution trend."""
    try:
        from services.personality_history_service import get_personality_history_service
        service = get_personality_history_service()
        return service.get_evolution_trend()
    except Exception as e:
        return {"error": str(e)}

# ============= ANALYTICS ENDPOINTS =============

@app.get("/api/analytics/conversations")
async def get_conversation_analytics():
    """Get comprehensive conversation analytics."""
    try:
        from services.conversation_analytics_service import get_conversation_analytics_service
        service = get_conversation_analytics_service()
        return service.get_comprehensive_analytics()
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return {"error": str(e)}

@app.get("/api/analytics/topics")
async def get_topic_distribution(limit: int = 20):
    """Get topic distribution from conversations."""
    try:
        from services.conversation_analytics_service import get_conversation_analytics_service
        service = get_conversation_analytics_service()
        return {"topics": service.get_topic_distribution(limit)}
    except Exception as e:
        return {"topics": []}

# ============= CALENDAR ENDPOINTS =============

@app.get("/api/calendar/status")
async def get_calendar_status():
    """Get calendar service status."""
    try:
        from services.calendar_service import get_calendar_service
        service = get_calendar_service()
        return service.get_status()
    except Exception as e:
        return {"platform": "google_calendar", "connected": False, "error": str(e)}

@app.get("/api/calendar/events")
async def get_calendar_events(days: int = 7):
    """Get upcoming calendar events."""
    try:
        from services.calendar_service import get_calendar_service
        service = get_calendar_service()
        return {"events": service.get_upcoming_events(days)}
    except Exception as e:
        return {"events": []}

@app.get("/api/calendar/summary")
async def get_today_summary():
    """Get AI-generated summary of today's schedule."""
    try:
        import asyncio
        from services.calendar_service import get_calendar_service
        service = get_calendar_service()
        summary = await asyncio.to_thread(service.get_today_summary)
        return {"summary": summary}
    except Exception as e:
        return {"summary": "Unable to get calendar summary."}

# ============= WHATSAPP ENDPOINTS =============

@app.get("/api/autopilot/whatsapp/status")
async def get_whatsapp_status():
    """Get WhatsApp autopilot status."""
    try:
        from services.whatsapp_bot_service import get_whatsapp_bot_service
        service = get_whatsapp_bot_service()
        return service.get_status()
    except Exception as e:
        return {"platform": "whatsapp", "configured": False, "error": str(e)}

@app.get("/api/autopilot/whatsapp/drafts")
async def get_whatsapp_drafts(status: Optional[str] = None):
    """Get WhatsApp draft queue."""
    try:
        from services.whatsapp_bot_service import get_whatsapp_bot_service
        service = get_whatsapp_bot_service()
        return {"drafts": service.get_drafts(status)}
    except Exception as e:
        return {"drafts": []}

@app.post("/api/autopilot/whatsapp/generate-reply")
async def generate_whatsapp_reply(request: DraftRequest):
    """Generate a WhatsApp reply draft."""
    try:
        from services.whatsapp_bot_service import get_whatsapp_bot_service
        service = get_whatsapp_bot_service()
        return service.generate_reply_draft(request.text)
    except Exception as e:
        return {"error": str(e)}

# ============= ACCURACY/QUIZ ENDPOINTS =============

@app.get("/api/accuracy/quiz")
async def generate_accuracy_quiz(num_questions: int = 5):
    """Generate a clone accuracy quiz."""
    try:
        import asyncio
        from services.accuracy_service import get_accuracy_service
        service = get_accuracy_service()
        quiz = await asyncio.to_thread(service.generate_quiz, num_questions)
        return quiz
    except Exception as e:
        logger.error(f"Quiz generation error: {e}")
        return {"error": str(e)}

class QuizAnswers(BaseModel):
    quiz_id: str
    answers: Dict[str, str]

@app.post("/api/accuracy/submit")
async def submit_quiz_answers(request: QuizAnswers):
    """Submit quiz answers and get score."""
    try:
        from services.accuracy_service import get_accuracy_service
        service = get_accuracy_service()
        return service.submit_quiz_answers(request.quiz_id, request.answers)
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/accuracy/stats")
async def get_accuracy_stats():
    """Get accuracy statistics."""
    try:
        from services.accuracy_service import get_accuracy_service
        service = get_accuracy_service()
        return service.get_accuracy_stats()
    except Exception as e:
        return {"quizzes_taken": 0, "error": str(e)}

# ============= UNIFIED DRAFTS ENDPOINT =============

@app.get("/api/drafts/all")
async def get_all_drafts():
    """Get all pending drafts from all platforms."""
    all_drafts = {
        'twitter': [],
        'linkedin': [],
        'gmail': [],
        'whatsapp': [],
        'total': 0
    }
    
    try:
        from services.twitter_bot_service import get_twitter_bot_service
        all_drafts['twitter'] = get_twitter_bot_service().get_drafts('pending')
    except: pass
    
    try:
        from services.linkedin_bot_service import get_linkedin_bot_service
        all_drafts['linkedin'] = get_linkedin_bot_service().get_drafts('pending')
    except: pass
    
    try:
        from services.gmail_bot_service import get_gmail_bot_service
        all_drafts['gmail'] = get_gmail_bot_service().get_drafts('pending')
    except: pass
    
    try:
        from services.whatsapp_bot_service import get_whatsapp_bot_service
        all_drafts['whatsapp'] = get_whatsapp_bot_service().get_drafts('pending')
    except: pass
    
    all_drafts['total'] = sum(len(v) for k, v in all_drafts.items() if k != 'total')
    
    return all_drafts


# ============= Deep Research Endpoints =============

class DeepResearchQuery(BaseModel):
    query: str = Field(..., min_length=5, max_length=500)
    max_depth: int = Field(default=3, ge=1, le=5)


@app.post("/api/research/deep")

async def deep_research(data: DeepResearchQuery):
    """
    Perform deep agentic research on a query.
    Recursively searches the web, scrapes pages, and synthesizes an answer with citations.
    """
    try:
        from services.deep_research_service import get_deep_research_service
        
        service = get_deep_research_service()
        result = await service.research(data.query, data.max_depth)
        
        return {
            "success": True,
            "query": result.query,
            "answer": result.answer,
            "sources": [s.to_dict() for s in result.sources],
            "follow_up_queries": result.follow_up_queries,
            "total_sources_checked": result.total_sources_checked,
            "research_time_seconds": result.research_time_seconds
        }
    except Exception as e:
        logger.error(f"Deep research error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/api/research/stream")
async def deep_research_stream(websocket: WebSocket):
    """
    WebSocket endpoint for streaming deep research progress.
    Send: {"query": "your question", "max_depth": 3}
    Receive: Progress events and final result
    """
    await websocket.accept()
    
    try:
        data = await websocket.receive_json()
        query = data.get("query", "")
        max_depth = data.get("max_depth", 3)
        
        if not query or len(query) < 5:
            await websocket.send_json({"error": "Query too short"})
            await websocket.close()
            return
        
        from services.deep_research_service import get_deep_research_service
        service = get_deep_research_service()
        
        # Stream progress events
        async for event in service.research_stream(query, max_depth):
            await websocket.send_json(event)
        
        await websocket.close()
        
    except WebSocketDisconnect:
        logger.info("Research WebSocket disconnected")
    except Exception as e:
        logger.error(f"Research stream error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
        except:
            pass


@app.get("/api/research/status")
async def research_status():
    """Get deep research service status."""
    try:
        from services.deep_research_service import get_deep_research_service
        from services.search_service import get_search_service
        
        search = get_search_service()
        
        return {
            "available": search.is_available(),
            "search_engine": "DuckDuckGo",
            "max_depth": 5,
            "features": ["recursive_search", "page_scraping", "llm_synthesis", "citations"]
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# ============= Desktop Rewind Memory Endpoints =============

class RewindQuery(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    time_range_minutes: Optional[float] = Field(default=None, ge=0, le=30)


@app.post("/api/rewind/frame")
async def add_rewind_frame(
    image_base64: str = Form(...),
    window_name: str = Form(...),
    mime_type: str = Form(default="image/png")
):
    """
    Add a frame to the rewind buffer.
    Called by the desktop widget during continuous capture.
    """
    try:
        from services.rewind_service import get_rewind_service
        service = get_rewind_service()
        return service.add_frame(image_base64, window_name, mime_type)
    except Exception as e:
        logger.error(f"Rewind frame error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/rewind/query")

async def query_rewind(data: RewindQuery):
    """
    Query the rewind buffer.
    Answer questions like "What was I looking at 10 minutes ago?"
    """
    try:
        from services.rewind_service import get_rewind_service
        import asyncio
        
        service = get_rewind_service()
        result = await asyncio.to_thread(service.query, data.question, data.time_range_minutes)
        return result
    except Exception as e:
        logger.error(f"Rewind query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rewind/status")
async def get_rewind_status():
    """Get rewind service status."""
    try:
        from services.rewind_service import get_rewind_service
        return get_rewind_service().get_status()
    except Exception as e:
        return {"enabled": False, "error": str(e)}


@app.get("/api/rewind/timeline")
async def get_rewind_timeline(limit: int = 20):
    """Get timeline of recent frames."""
    try:
        from services.rewind_service import get_rewind_service
        return {"timeline": get_rewind_service().get_timeline(limit)}
    except Exception as e:
        return {"timeline": [], "error": str(e)}


@app.post("/api/rewind/pause")
async def pause_rewind():
    """Pause rewind capture."""
    from services.rewind_service import get_rewind_service
    return get_rewind_service().pause()


@app.post("/api/rewind/resume")
async def resume_rewind():
    """Resume rewind capture."""
    from services.rewind_service import get_rewind_service
    return get_rewind_service().resume()


@app.delete("/api/rewind/clear")
async def clear_rewind():
    """Clear rewind buffer (privacy)."""
    from services.rewind_service import get_rewind_service
    return get_rewind_service().clear()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

