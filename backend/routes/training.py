"""
Training Routes - Endpoints for training the AI clone.
Includes file uploads (WhatsApp, Instagram, Discord), facts, journal entries,
training examples, and training chat.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging
import asyncio

from config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/training", tags=["training"])

# ============= Request Models =============

class JournalEntry(BaseModel):
    content: str

class FactEntry(BaseModel):
    fact: str

class TrainingExample(BaseModel):
    context: str
    response: str

class TrainingChatMessage(BaseModel):
    bot_message: str
    user_response: str

class TrainingFeedback(BaseModel):
    context: str = Field(..., min_length=1, max_length=Config.MAX_MESSAGE_LENGTH)
    correct_response: Optional[str] = Field(default=None, max_length=Config.MAX_MESSAGE_LENGTH)
    bot_response: Optional[str] = Field(default=None, max_length=Config.MAX_MESSAGE_LENGTH)
    accepted: bool = False


# ============= Helper Functions =============

def _get_memory_service():
    from services.memory_service import get_memory_service
    return get_memory_service()

def _get_personality_service():
    from services.personality_service import get_personality_service
    return get_personality_service()


# ============= Auth Endpoint =============

import os
TRAINING_PIN = os.environ.get("TRAINING_PIN", "1234")

@router.post("/auth")
async def verify_training_auth(pin: str = Form(...)):
    """Verify training PIN"""
    if pin == TRAINING_PIN:
        return {"success": True, "message": "Authenticated"}
    raise HTTPException(status_code=401, detail="Invalid PIN")


# ============= File Upload Endpoints =============

@router.post("/upload/whatsapp")
async def upload_whatsapp(
    file: UploadFile = File(...),
    your_name: str = Form(...)
):
    """Upload WhatsApp chat export"""
    try:
        from parsers import WhatsAppParser
        
        content = await file.read()
        content_str = content.decode('utf-8', errors='replace')
        
        parser = WhatsAppParser(your_name)
        result = await asyncio.to_thread(parser.parse_content, content_str)
        
        memory = _get_memory_service()
        personality = _get_personality_service()
        
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


@router.post("/upload/instagram")
async def upload_instagram(
    file: UploadFile = File(...),
    your_username: str = Form(...)
):
    """Upload Instagram DM export"""
    try:
        from parsers import InstagramParser
        
        content = await file.read()
        content_str = content.decode('utf-8', errors='replace')
        
        parser = InstagramParser(your_username)
        result = await asyncio.to_thread(parser.parse_content, content_str)
        
        memory = _get_memory_service()
        personality = _get_personality_service()
        
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


@router.post("/upload/discord")
async def upload_discord(
    file: UploadFile = File(...),
    your_username: str = Form(...)
):
    """Upload Discord chat export"""
    try:
        from parsers import DiscordParser
        
        content = await file.read()
        content_str = content.decode('utf-8', errors='replace')
        
        parser = DiscordParser(your_user_id=None, your_username=your_username)
        result = await asyncio.to_thread(parser.parse_content, content_str, 'json')
        
        memory = _get_memory_service()
        personality = _get_personality_service()
        
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


@router.post("/upload/document")
async def upload_document(
    file: UploadFile = File(...)
):
    """Upload PDF or text document for learning"""
    try:
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
        memory = _get_memory_service()
        personality = _get_personality_service()
        
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


# ============= Journal & Facts Endpoints =============

@router.post("/journal")
async def add_journal_entry(entry: JournalEntry):
    """Add a journal/thought entry"""
    try:
        memory = _get_memory_service()
        personality = _get_personality_service()
        
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


@router.post("/fact")
async def add_fact(entry: FactEntry):
    """Add a personal fact"""
    try:
        personality = _get_personality_service()
        personality.add_fact(entry.fact)
        return {"success": True, "facts": personality.get_profile().facts}
    except Exception as e:
        logger.error(f"Add fact error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/facts")
async def get_facts():
    """Get all stored facts"""
    try:
        personality = _get_personality_service()
        return {"facts": personality.get_profile().facts}
    except Exception as e:
        logger.error(f"Get facts error: {e}")
        return {"facts": []}


@router.delete("/facts/{index}")
async def delete_fact(index: int):
    """Delete a fact by index"""
    try:
        personality = _get_personality_service()
        facts = personality.get_profile().facts
        if 0 <= index < len(facts):
            facts.pop(index)
            personality.save_profile()
            return {"success": True, "facts": facts}
        raise HTTPException(status_code=400, detail="Invalid index")
    except Exception as e:
        logger.error(f"Delete fact error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Training Examples Endpoints =============

@router.post("/example")
async def add_training_example(example: TrainingExample):
    """Add a direct training example"""
    try:
        memory = _get_memory_service()
        personality = _get_personality_service()
        
        memory.add_training_example(example.context, example.response, source='manual')
        personality.add_example(example.context, example.response)
        
        return {"success": True, "message": "Example added"}
    except Exception as e:
        logger.error(f"Add example error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_training_stats():
    """Get training statistics"""
    try:
        memory = _get_memory_service()
        personality = _get_personality_service().get_profile()
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


# ============= Training Chat Endpoints =============

@router.post("/chat")
async def training_chat_response(msg: TrainingChatMessage):
    """
    Train by chatting - the bot says something and user responds.
    The user's response is what gets learned.
    """
    try:
        memory = _get_memory_service()
        personality = _get_personality_service()
        
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


@router.get("/chat/prompt")
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


@router.post("/feedback")
async def training_feedback(data: TrainingFeedback):
    """Handle training feedback"""
    try:
        if data.accepted:
            # Positive reinforcement: Add to examples if not already present
            if data.context and data.bot_response:
                personality = _get_personality_service()
                personality.add_example(data.context, data.bot_response)
                
                # Also verify with memory service (add as training data)
                memory = _get_memory_service()
                memory.add_training_example(data.context, data.bot_response, source="user_feedback")
                
        elif data.correct_response:
            # Negative feedback with correction
            from services.chat_service import get_chat_service as _get_chat_service
            service = _get_chat_service()
            await asyncio.to_thread(service.train_from_interaction, data.context, data.correct_response)
            
        return {"success": True}
    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Reset Endpoint =============

@router.delete("/reset")
async def reset_all_training():
    """Reset all learning data - use with caution!"""
    try:
        memory = _get_memory_service()
        personality = _get_personality_service()
        
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


# ============= Export/Import Endpoints =============

from datetime import datetime as dt

class ImportRequest(BaseModel):
    """Request model for brain import."""
    data: dict
    merge: bool = True  # If True, merges with existing. If False, replaces.


@router.get("/export")
async def export_all_brain_data():
    """Export all learned data (training examples, personality profile) as JSON.
    
    Returns a comprehensive export file that can be imported on a fresh install
    to restore the AI's learned behavior exactly.
    """
    try:
        memory = _get_memory_service()
        personality = _get_personality_service()
        
        # Get all training examples
        training_examples = memory.export_all_training_examples()
        
        # Get complete personality profile
        personality_profile = personality.export_profile()
        
        # Get training stats for metadata
        stats = memory.get_training_stats()
        
        export_data = {
            "format_version": "1.0",
            "app_name": "Chirag-clone",
            "app_description": "AI Digital Twin Training Data Export",
            "exported_at": dt.now().isoformat(),
            "metadata": {
                "total_training_examples": len(training_examples),
                "total_facts": len(personality_profile.get('facts', [])),
                "total_response_examples": len(personality_profile.get('response_examples', [])),
                "sources": stats.get('sources', {}),
                "personality_name": personality_profile.get('name', 'Unknown')
            },
            "personality_profile": personality_profile,
            "training_examples": training_examples
        }
        
        logger.info(f"Exported brain data: {len(training_examples)} examples, "
                   f"{len(personality_profile.get('facts', []))} facts")
        
        return export_data
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_brain_data(file: UploadFile = File(...), merge: bool = Form(True)):
    """Import previously exported brain data.
    
    Args:
        file: JSON file from a previous export
        merge: If True (default), merges with existing data. If False, replaces all data.
    
    Returns:
        Import status with counts of imported items
    """
    import json as json_module
    
    try:
        # Read and parse the file
        content = await file.read()
        try:
            data = json_module.loads(content.decode('utf-8'))
        except json_module.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")
        
        # Validate format version
        format_version = data.get('format_version', '')
        if not format_version:
            raise HTTPException(status_code=400, detail="Invalid export file: missing format_version")
        
        if format_version not in ['1.0']:
            raise HTTPException(status_code=400, 
                detail=f"Unsupported format version: {format_version}. Supported: 1.0")
        
        memory = _get_memory_service()
        personality = _get_personality_service()
        
        results = {
            "success": True,
            "format_version": format_version,
            "merge_mode": merge,
            "imported": {}
        }
        
        # Import personality profile
        if 'personality_profile' in data:
            personality.import_profile(data['personality_profile'], merge=merge)
            profile = personality.get_profile()
            results["imported"]["personality"] = {
                "name": profile.name,
                "facts": len(profile.facts),
                "response_examples": len(profile.response_examples),
                "typing_quirks": len(profile.typing_quirks)
            }
        
        # Import training examples
        if 'training_examples' in data:
            examples = data['training_examples']
            imported_count = memory.import_training_examples(examples, clear_existing=not merge)
            results["imported"]["training_examples"] = imported_count
        
        # Log the import
        logger.info(f"Imported brain data: {results['imported']}")
        
        results["message"] = "Brain data imported successfully"
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

