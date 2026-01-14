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

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite default port
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
