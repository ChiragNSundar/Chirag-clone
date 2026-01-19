"""
Autopilot Routes - Bot integrations for Discord, Telegram, Twitter, LinkedIn, Gmail, WhatsApp.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


# ============= Request Models =============

class AutopilotSettings(BaseModel):
    auto_reply_dms: Optional[bool] = None
    auto_reply_mentions: Optional[bool] = None
    auto_reply_enabled: Optional[bool] = None

class DraftRequest(BaseModel):
    text: str
    topic: str = ""

class EmailReplyRequest(BaseModel):
    subject: str
    body: str
    sender_name: str = "Someone"


# ============= Bot Instance Management =============

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


# ============= Status Endpoint =============

@router.get("/status")
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


# ============= Discord Endpoints =============

@router.post("/discord/start")
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


@router.post("/discord/stop")
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


@router.post("/discord/settings")
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


# ============= Telegram Endpoints =============

@router.post("/telegram/start")
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


@router.post("/telegram/stop")
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


@router.post("/telegram/settings")
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


# ============= Logs Endpoint =============

@router.get("/logs")
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


# ============= Twitter/X Endpoints =============

@router.get("/twitter/status")
async def get_twitter_status():
    """Get Twitter autopilot status."""
    try:
        from services.twitter_autopilot import get_twitter_autopilot
        service = get_twitter_autopilot()
        return service.get_status()
    except Exception as e:
        logger.error(f"Twitter status error: {e}")
        return {"configured": False, "error": str(e)}


@router.get("/twitter/drafts")
async def get_twitter_drafts(status: Optional[str] = None):
    """Get Twitter draft queue."""
    try:
        from services.twitter_autopilot import get_twitter_autopilot
        service = get_twitter_autopilot()
        return {"drafts": service.get_drafts(status=status)}
    except Exception as e:
        logger.error(f"Twitter drafts error: {e}")
        return {"drafts": []}


@router.post("/twitter/draft/tweet")
async def generate_tweet_draft(request: DraftRequest):
    """Generate a tweet draft."""
    try:
        from services.twitter_autopilot import get_twitter_autopilot
        service = get_twitter_autopilot()
        draft = service.generate_draft(topic=request.topic or request.text)
        return {"success": True, "draft": draft}
    except Exception as e:
        logger.error(f"Twitter draft error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/twitter/draft/reply")
async def generate_twitter_reply(request: DraftRequest):
    """Generate a reply draft."""
    try:
        from services.twitter_autopilot import get_twitter_autopilot
        service = get_twitter_autopilot()
        draft = service.generate_reply(original_text=request.text, topic=request.topic)
        return {"success": True, "draft": draft}
    except Exception as e:
        logger.error(f"Twitter reply error: {e}")
        return {"success": False, "error": str(e)}


# ============= LinkedIn Endpoints =============

@router.get("/linkedin/status")
async def get_linkedin_status():
    """Get LinkedIn autopilot status."""
    try:
        from services.linkedin_autopilot import get_linkedin_autopilot
        service = get_linkedin_autopilot()
        return service.get_status()
    except Exception as e:
        logger.error(f"LinkedIn status error: {e}")
        return {"configured": False, "error": str(e)}


@router.get("/linkedin/drafts")
async def get_linkedin_drafts(status: Optional[str] = None):
    """Get LinkedIn draft queue."""
    try:
        from services.linkedin_autopilot import get_linkedin_autopilot
        service = get_linkedin_autopilot()
        return {"drafts": service.get_drafts(status=status)}
    except Exception as e:
        logger.error(f"LinkedIn drafts error: {e}")
        return {"drafts": []}


@router.post("/linkedin/draft/reply")
async def generate_linkedin_reply(request: DraftRequest):
    """Generate a LinkedIn reply draft."""
    try:
        from services.linkedin_autopilot import get_linkedin_autopilot
        service = get_linkedin_autopilot()
        draft = service.generate_reply(original_text=request.text, topic=request.topic)
        return {"success": True, "draft": draft}
    except Exception as e:
        logger.error(f"LinkedIn reply error: {e}")
        return {"success": False, "error": str(e)}


# ============= Gmail Endpoints =============

@router.get("/gmail/status")
async def get_gmail_status():
    """Get Gmail autopilot status."""
    try:
        from services.gmail_autopilot import get_gmail_autopilot
        service = get_gmail_autopilot()
        return service.get_status()
    except Exception as e:
        logger.error(f"Gmail status error: {e}")
        return {"configured": False, "error": str(e)}


@router.get("/gmail/drafts")
async def get_gmail_drafts(status: Optional[str] = None):
    """Get Gmail draft queue."""
    try:
        from services.gmail_autopilot import get_gmail_autopilot
        service = get_gmail_autopilot()
        return {"drafts": service.get_drafts(status=status)}
    except Exception as e:
        logger.error(f"Gmail drafts error: {e}")
        return {"drafts": []}


@router.post("/gmail/draft/reply")
async def generate_gmail_reply(request: EmailReplyRequest):
    """Generate an email reply draft."""
    try:
        from services.gmail_autopilot import get_gmail_autopilot
        service = get_gmail_autopilot()
        draft = service.generate_reply(
            subject=request.subject,
            body=request.body,
            sender_name=request.sender_name
        )
        return {"success": True, "draft": draft}
    except Exception as e:
        logger.error(f"Gmail reply error: {e}")
        return {"success": False, "error": str(e)}


# ============= WhatsApp Endpoints =============

@router.get("/whatsapp/status")
async def get_whatsapp_status():
    """Get WhatsApp autopilot status."""
    try:
        from services.whatsapp_autopilot import get_whatsapp_autopilot
        service = get_whatsapp_autopilot()
        return service.get_status()
    except Exception as e:
        logger.error(f"WhatsApp status error: {e}")
        return {"configured": False, "error": str(e)}


@router.get("/whatsapp/drafts")
async def get_whatsapp_drafts(status: Optional[str] = None):
    """Get WhatsApp draft queue."""
    try:
        from services.whatsapp_autopilot import get_whatsapp_autopilot
        service = get_whatsapp_autopilot()
        return {"drafts": service.get_drafts(status=status)}
    except Exception as e:
        logger.error(f"WhatsApp drafts error: {e}")
        return {"drafts": []}


@router.post("/whatsapp/draft/reply")
async def generate_whatsapp_reply(request: DraftRequest):
    """Generate a WhatsApp reply draft."""
    try:
        from services.whatsapp_autopilot import get_whatsapp_autopilot
        service = get_whatsapp_autopilot()
        draft = service.generate_reply(original_text=request.text, topic=request.topic)
        return {"success": True, "draft": draft}
    except Exception as e:
        logger.error(f"WhatsApp reply error: {e}")
        return {"success": False, "error": str(e)}


# ============= Unified Drafts Endpoint =============

@router.get("/drafts/all")
async def get_all_drafts():
    """Get all pending drafts from all platforms."""
    all_drafts = {}
    
    # Twitter
    try:
        from services.twitter_autopilot import get_twitter_autopilot
        twitter = get_twitter_autopilot()
        all_drafts["twitter"] = twitter.get_drafts(status="pending")
    except Exception:
        all_drafts["twitter"] = []
    
    # LinkedIn
    try:
        from services.linkedin_autopilot import get_linkedin_autopilot
        linkedin = get_linkedin_autopilot()
        all_drafts["linkedin"] = linkedin.get_drafts(status="pending")
    except Exception:
        all_drafts["linkedin"] = []
    
    # Gmail
    try:
        from services.gmail_autopilot import get_gmail_autopilot
        gmail = get_gmail_autopilot()
        all_drafts["gmail"] = gmail.get_drafts(status="pending")
    except Exception:
        all_drafts["gmail"] = []
    
    # WhatsApp
    try:
        from services.whatsapp_autopilot import get_whatsapp_autopilot
        whatsapp = get_whatsapp_autopilot()
        all_drafts["whatsapp"] = whatsapp.get_drafts(status="pending")
    except Exception:
        all_drafts["whatsapp"] = []
    
    # Calculate total
    total = sum(len(drafts) for drafts in all_drafts.values())
    
    return {"drafts": all_drafts, "total_pending": total}
