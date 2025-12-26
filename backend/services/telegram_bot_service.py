"""
Telegram Bot Service - Autopilot for Telegram messages.
"""
import os
import asyncio
import threading
from typing import Optional
from datetime import datetime

# python-telegram-bot is optional
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Update = None
    Application = None


class TelegramBotService:
    """Telegram bot that auto-replies using your AI clone."""
    
    def __init__(self, chat_service):
        self.chat_service = chat_service
        self.app = None
        self.is_running = False
        self.thread = None
        self.loop = None
        self.token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.auto_reply_enabled = True
        self.reply_log = []
        
    def is_configured(self) -> bool:
        """Check if Telegram bot is configured."""
        return TELEGRAM_AVAILABLE and bool(self.token)
    
    def start(self) -> bool:
        """Start the Telegram bot in a background thread."""
        if not self.is_configured():
            print("Telegram bot not configured. Set TELEGRAM_BOT_TOKEN in .env")
            return False
        
        if self.is_running:
            return True
        
        self.thread = threading.Thread(target=self._run_bot, daemon=True)
        self.thread.start()
        return True
    
    def stop(self):
        """Stop the Telegram bot."""
        if self.app and self.loop:
            asyncio.run_coroutine_threadsafe(self.app.stop(), self.loop)
        self.is_running = False
    
    def _run_bot(self):
        """Run the bot in its own event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle /start command."""
            await update.message.reply_text(
                "Hi! I'm an AI clone. Send me a message and I'll respond!"
            )
        
        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle incoming messages."""
            if not self.auto_reply_enabled:
                return
            
            user_message = update.message.text
            user_name = update.effective_user.first_name or "Unknown"
            
            try:
                # Generate response
                response = self.chat_service.generate_response(
                    user_message=user_message,
                    conversation_history=[],
                    training_mode=False
                )
                
                # Log the reply
                self._log_reply(
                    platform='telegram',
                    user=user_name,
                    message=user_message,
                    response=response
                )
                
                await update.message.reply_text(response)
            except Exception as e:
                print(f"Telegram reply error: {e}")
                await update.message.reply_text("Sorry, I couldn't process that right now.")
        
        async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle /status command."""
            status = "🟢 Autopilot Active" if self.auto_reply_enabled else "🔴 Autopilot Paused"
            await update.message.reply_text(status)
        
        try:
            self.app = Application.builder().token(self.token).build()
            
            # Add handlers
            self.app.add_handler(CommandHandler("start", start_command))
            self.app.add_handler(CommandHandler("status", status_command))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            
            print("Telegram Autopilot starting...")
            self.is_running = True
            
            self.loop.run_until_complete(self.app.run_polling(allowed_updates=Update.ALL_TYPES))
        except Exception as e:
            print(f"Telegram bot error: {e}")
            self.is_running = False
    
    def _log_reply(self, platform: str, user: str, message: str, response: str):
        """Log an auto-reply."""
        self.reply_log.append({
            'timestamp': datetime.now().isoformat(),
            'platform': platform,
            'user': user,
            'message': message[:100],
            'response': response[:100]
        })
        if len(self.reply_log) > 50:
            self.reply_log = self.reply_log[-50:]
    
    def get_status(self) -> dict:
        """Get bot status."""
        return {
            'configured': self.is_configured(),
            'running': self.is_running,
            'auto_reply_enabled': self.auto_reply_enabled,
            'recent_replies': len(self.reply_log)
        }
    
    def get_reply_log(self) -> list:
        """Get recent reply log."""
        return list(reversed(self.reply_log))


# Singleton instance
_telegram_bot = None

def get_telegram_bot_service(chat_service=None):
    """Get or create the Telegram bot service."""
    global _telegram_bot
    if _telegram_bot is None and chat_service:
        _telegram_bot = TelegramBotService(chat_service)
    return _telegram_bot
