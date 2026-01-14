from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import os
import logging
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Chirag Clone API",
    description="Personal AI Clone Bot API",
    version="2.0.0"
)

# CORS Configuration - allow all localhost ports for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:5177", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175", "http://127.0.0.1:5176"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Request Models
class ChatMessage(BaseModel):
    message: str
    session_id: str = "default"
    training_mode: bool = False

class TrainingFeedback(BaseModel):
    context: str
    correct_response: Optional[str] = None
    bot_response: Optional[str] = None
    accepted: bool = False

# Dependencies (Lazy loading services)
async def get_chat_service():
    from services.chat_service import get_chat_service as _get_service
    return _get_service()

# --- Routes ---

@app.get("/api/health")
async def health_check():
    """Health Check Endpoint"""
    return {"status": "healthy", "version": "2.0.0", "framework": "FastAPI"}

@app.post("/api/chat/message")
async def chat_message(data: ChatMessage):
    """Handle chat messages"""
    try:
        service = await get_chat_service()
        
        # Run synchronous service in threadpool to avoid blocking event loop
        import asyncio
        response, confidence, mood_data = await asyncio.to_thread(
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
            "mood": mood_data
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
