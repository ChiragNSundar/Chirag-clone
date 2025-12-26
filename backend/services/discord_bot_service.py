"""
Discord Bot Service - Autopilot for Discord DMs and mentions.
"""
import os
import asyncio
import threading
from typing import Optional
from datetime import datetime

# Discord.py is optional - only import if available
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None
    commands = None


class DiscordBotService:
    """Discord bot that auto-replies using your AI clone."""
    
    def __init__(self, chat_service):
        self.chat_service = chat_service
        self.bot = None
        self.is_running = False
        self.thread = None
        self.loop = None
        self.token = os.getenv('DISCORD_BOT_TOKEN', '')
        self.auto_reply_dms = True
        self.auto_reply_mentions = True
        self.reply_log = []  # Log of auto-replies
        
    def is_configured(self) -> bool:
        """Check if Discord bot is configured."""
        return DISCORD_AVAILABLE and bool(self.token)
    
    def start(self) -> bool:
        """Start the Discord bot in a background thread."""
        if not self.is_configured():
            print("Discord bot not configured. Set DISCORD_BOT_TOKEN in .env")
            return False
        
        if self.is_running:
            return True
        
        self.thread = threading.Thread(target=self._run_bot, daemon=True)
        self.thread.start()
        return True
    
    def stop(self):
        """Stop the Discord bot."""
        if self.bot and self.loop:
            asyncio.run_coroutine_threadsafe(self.bot.close(), self.loop)
        self.is_running = False
    
    def _run_bot(self):
        """Run the bot in its own event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        
        self.bot = commands.Bot(command_prefix='!clone ', intents=intents)
        
        @self.bot.event
        async def on_ready():
            print(f'Discord Autopilot connected as {self.bot.user}')
            self.is_running = True
        
        @self.bot.event
        async def on_message(message):
            # Don't reply to ourselves
            if message.author == self.bot.user:
                return
            
            should_reply = False
            
            # Check if DM
            if isinstance(message.channel, discord.DMChannel) and self.auto_reply_dms:
                should_reply = True
            
            # Check if mentioned
            if self.bot.user in message.mentions and self.auto_reply_mentions:
                should_reply = True
            
            if should_reply:
                async with message.channel.typing():
                    try:
                        # Generate response using chat service
                        response = self.chat_service.generate_response(
                            user_message=message.content,
                            conversation_history=[],
                            training_mode=False
                        )
                        
                        # Log the reply
                        self._log_reply(
                            platform='discord',
                            user=str(message.author),
                            message=message.content,
                            response=response
                        )
                        
                        await message.reply(response)
                    except Exception as e:
                        print(f"Discord reply error: {e}")
            
            await self.bot.process_commands(message)
        
        try:
            self.loop.run_until_complete(self.bot.start(self.token))
        except Exception as e:
            print(f"Discord bot error: {e}")
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
        # Keep only last 50 replies
        if len(self.reply_log) > 50:
            self.reply_log = self.reply_log[-50:]
    
    def get_status(self) -> dict:
        """Get bot status."""
        return {
            'configured': self.is_configured(),
            'running': self.is_running,
            'auto_reply_dms': self.auto_reply_dms,
            'auto_reply_mentions': self.auto_reply_mentions,
            'recent_replies': len(self.reply_log)
        }
    
    def get_reply_log(self) -> list:
        """Get recent reply log."""
        return list(reversed(self.reply_log))


# Singleton instance
_discord_bot = None

def get_discord_bot_service(chat_service=None):
    """Get or create the Discord bot service."""
    global _discord_bot
    if _discord_bot is None and chat_service:
        _discord_bot = DiscordBotService(chat_service)
    return _discord_bot
