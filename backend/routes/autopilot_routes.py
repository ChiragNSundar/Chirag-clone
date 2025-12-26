"""
Autopilot Routes - API endpoints for managing social autopilot.
"""
from flask import Blueprint, request, jsonify

autopilot_bp = Blueprint('autopilot', __name__, url_prefix='/api/autopilot')

# Lazy imports to avoid circular dependencies
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


@autopilot_bp.route('/status', methods=['GET'])
def get_status():
    """Get status of all autopilot bots."""
    discord_bot, telegram_bot = _get_bots()
    
    return jsonify({
        'discord': discord_bot.get_status() if discord_bot else {'configured': False},
        'telegram': telegram_bot.get_status() if telegram_bot else {'configured': False}
    })


@autopilot_bp.route('/discord/start', methods=['POST'])
def start_discord():
    """Start the Discord autopilot."""
    discord_bot, _ = _get_bots()
    
    if not discord_bot:
        return jsonify({'error': 'Discord bot not available'}), 400
    
    success = discord_bot.start()
    return jsonify({
        'success': success,
        'message': 'Discord autopilot started' if success else 'Failed to start Discord bot'
    })


@autopilot_bp.route('/discord/stop', methods=['POST'])
def stop_discord():
    """Stop the Discord autopilot."""
    discord_bot, _ = _get_bots()
    
    if discord_bot:
        discord_bot.stop()
    
    return jsonify({'success': True, 'message': 'Discord autopilot stopped'})


@autopilot_bp.route('/discord/settings', methods=['POST'])
def update_discord_settings():
    """Update Discord bot settings."""
    discord_bot, _ = _get_bots()
    data = request.get_json() or {}
    
    if discord_bot:
        if 'auto_reply_dms' in data:
            discord_bot.auto_reply_dms = data['auto_reply_dms']
        if 'auto_reply_mentions' in data:
            discord_bot.auto_reply_mentions = data['auto_reply_mentions']
    
    return jsonify({'success': True, 'status': discord_bot.get_status()})


@autopilot_bp.route('/telegram/start', methods=['POST'])
def start_telegram():
    """Start the Telegram autopilot."""
    _, telegram_bot = _get_bots()
    
    if not telegram_bot:
        return jsonify({'error': 'Telegram bot not available'}), 400
    
    success = telegram_bot.start()
    return jsonify({
        'success': success,
        'message': 'Telegram autopilot started' if success else 'Failed to start Telegram bot'
    })


@autopilot_bp.route('/telegram/stop', methods=['POST'])
def stop_telegram():
    """Stop the Telegram autopilot."""
    _, telegram_bot = _get_bots()
    
    if telegram_bot:
        telegram_bot.stop()
    
    return jsonify({'success': True, 'message': 'Telegram autopilot stopped'})


@autopilot_bp.route('/telegram/settings', methods=['POST'])
def update_telegram_settings():
    """Update Telegram bot settings."""
    _, telegram_bot = _get_bots()
    data = request.get_json() or {}
    
    if telegram_bot and 'auto_reply_enabled' in data:
        telegram_bot.auto_reply_enabled = data['auto_reply_enabled']
    
    return jsonify({'success': True, 'status': telegram_bot.get_status()})


@autopilot_bp.route('/logs', methods=['GET'])
def get_logs():
    """Get recent auto-reply logs from all platforms."""
    discord_bot, telegram_bot = _get_bots()
    
    logs = []
    if discord_bot:
        logs.extend(discord_bot.get_reply_log())
    if telegram_bot:
        logs.extend(telegram_bot.get_reply_log())
    
    # Sort by timestamp
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({'logs': logs[:50]})
