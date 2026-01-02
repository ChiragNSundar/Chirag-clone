"""
Personal AI Clone Bot - Main Flask Application
Enhanced with security headers, request limits, structured logging, and graceful error handling.
"""
from flask import Flask, send_from_directory, request, jsonify, g
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os

from config import Config
from routes import chat_bp, training_bp, upload_bp, visualization_bp, autopilot_bp, timeline_bp, analytics_bp, knowledge_bp, proactive_bp
from services.logger import setup_logging, request_logging_middleware, get_logger

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config.from_object(Config)

# Set max request size (10MB)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

# Setup logging
setup_logging(app, level=Config.LOG_LEVEL if hasattr(Config, 'LOG_LEVEL') else 20)
request_logging_middleware(app)
logger = get_logger(__name__)

# Enable CORS
CORS(app, origins=['*'])

# Initialize SocketIO for real-time chat
socketio = SocketIO(app, cors_allowed_origins="*")

# Register blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(training_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(visualization_bp)
app.register_blueprint(autopilot_bp)
app.register_blueprint(timeline_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(knowledge_bp)
app.register_blueprint(proactive_bp)


# Security headers middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Remove server header
    response.headers.pop('Server', None)
    return response


# Request validation middleware
@app.before_request
def validate_request():
    """Validate incoming requests."""
    # Skip validation for static files
    if not request.path.startswith('/api/'):
        return None
    
    # Validate JSON content type for POST/PUT requests
    if request.method in ['POST', 'PUT', 'PATCH']:
        if request.content_type and 'multipart/form-data' not in request.content_type:
            if request.content_length and request.content_length > 0:
                if not request.is_json and 'application/json' not in request.content_type:
                    # Allow form data for uploads
                    if 'form' not in request.content_type:
                        logger.warning(f"Invalid content type: {request.content_type}")
    
    return None


# Serve frontend
@app.route('/')
def serve_frontend():
    """Serve the main frontend page."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files."""
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


# WebSocket events for real-time chat
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info('WebSocket client connected')
    emit('connected', {'message': 'Connected to AI Clone Bot'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info('WebSocket client disconnected')


@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle incoming chat messages via WebSocket."""
    from services.chat_service import get_chat_service
    
    message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    # Input validation
    if not message or not message.strip():
        emit('error', {'message': 'Empty message'})
        return
    
    # Length limit
    if len(message) > 10000:
        emit('error', {'message': 'Message too long (max 10,000 characters)'})
        return
    
    try:
        chat_service = get_chat_service()
        response = chat_service.generate_response(message, session_id)
        
        emit('chat_response', {
            'response': response,
            'session_id': session_id
        })
    except Exception as e:
        logger.error(f"WebSocket chat error: {e}")
        emit('error', {'message': 'Failed to generate response. Please try again.'})


@socketio.on('training_feedback')
def handle_training_feedback(data):
    """Handle training feedback via WebSocket."""
    from services.chat_service import get_chat_service
    
    context = data.get('context', '')
    response = data.get('correct_response', '')
    
    # Validation
    if not context or not response:
        emit('error', {'message': 'Both context and response are required'})
        return
    
    if len(context) > 5000 or len(response) > 5000:
        emit('error', {'message': 'Content too long (max 5,000 characters each)'})
        return
    
    try:
        chat_service = get_chat_service()
        chat_service.train_from_interaction(context, response)
        emit('training_saved', {'success': True})
    except Exception as e:
        logger.error(f"Training feedback error: {e}")
        emit('error', {'message': 'Failed to save training data'})


# Enhanced health check endpoint
@app.route('/api/health')
def health_check():
    """
    Enhanced health check endpoint.
    Returns status of all service dependencies.
    """
    health = {
        'status': 'healthy',
        'service': 'AI Clone Bot',
        'checks': {}
    }
    
    # Check ChromaDB
    try:
        from services.memory_service import get_memory_service
        memory = get_memory_service()
        memory.get_training_stats()
        health['checks']['chromadb'] = 'ok'
    except Exception as e:
        health['checks']['chromadb'] = f'error: {str(e)[:50]}'
        health['status'] = 'degraded'
    
    # Check LLM availability
    try:
        from services.llm_service import get_llm_service
        llm = get_llm_service()
        if llm._init_error:
            health['checks']['llm'] = f'error: {llm._init_error[:50]}'
            health['status'] = 'degraded'
        else:
            health['checks']['llm'] = 'ok'
    except Exception as e:
        health['checks']['llm'] = f'error: {str(e)[:50]}'
        health['status'] = 'degraded'
    
    # Check filesystem
    try:
        test_file = os.path.join(Config.DATA_DIR, '.healthcheck')
        with open(test_file, 'w') as f:
            f.write('ok')
        os.remove(test_file)
        health['checks']['filesystem'] = 'ok'
    except Exception as e:
        health['checks']['filesystem'] = f'error: {str(e)[:50]}'
        health['status'] = 'degraded'
    
    status_code = 200 if health['status'] == 'healthy' else 503
    return jsonify(health), status_code


# Error handlers
@app.errorhandler(400)
def bad_request(e):
    """Handle bad request errors."""
    return jsonify({'error': 'Bad request', 'message': str(e.description) if hasattr(e, 'description') else 'Invalid request'}), 400


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(413)
def request_too_large(e):
    """Handle request too large errors."""
    return jsonify({'error': 'Request too large', 'message': 'Maximum request size is 10MB'}), 413


@app.errorhandler(429)
def rate_limit_exceeded(e):
    """Handle rate limit errors."""
    return jsonify({'error': 'Rate limit exceeded', 'message': 'Please try again later'}), 429


@app.errorhandler(500)
def server_error(e):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {e}")
    return jsonify({'error': 'Internal server error', 'message': 'An unexpected error occurred'}), 500


if __name__ == '__main__':
    import signal
    import sys
    
    logger.info("Starting Personal AI Clone Bot...")
    logger.info(f"LLM Provider: {Config.LLM_PROVIDER}")
    logger.info(f"Model: {getattr(Config, f'{Config.LLM_PROVIDER.upper()}_MODEL', 'default')}")
    logger.info(f"Bot Name: {Config.BOT_NAME}")
    logger.info("-" * 40)
    
    # Validate configuration at startup
    from config import validate_config
    config_errors = validate_config()
    if config_errors:
        for error in config_errors:
            logger.warning(f"Config warning: {error}")
    
    # Import middleware for request tracking
    from services.middleware import get_request_tracker, request_tracking_middleware
    request_tracking_middleware(app)
    
    # Graceful shutdown handler
    def graceful_shutdown(signum, frame):
        signal_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        
        tracker = get_request_tracker()
        tracker.start_shutdown()
        
        # Wait for active requests to complete (max 30s)
        active = tracker.count()
        if active > 0:
            logger.info(f"Waiting for {active} active requests to complete...")
            if tracker.wait_for_requests(timeout=30):
                logger.info("All requests completed")
            else:
                logger.warning(f"Shutdown timeout, {tracker.count()} requests still active")
        
        # Cleanup services
        try:
            from services.cache_service import get_cache_service
            cache = get_cache_service()
            stats = cache.get_stats()
            logger.info(f"Cache stats at shutdown: {stats}")
        except:
            pass
        
        logger.info("Shutdown complete")
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)
    
    # Pre-load services in background for faster first response
    import threading
    def preload_services():
        try:
            logger.info("Pre-loading AI services...")
            from services.chat_service import get_chat_service
            from services.cache_service import get_cache_service
            get_chat_service()  # This initializes LLM, Memory, and Personality
            get_cache_service()  # Initialize cache
            logger.info("AI services ready!")
        except Exception as e:
            logger.warning(f"Pre-loading warning: {e}")
    
    threading.Thread(target=preload_services, daemon=True).start()
    
    logger.info("Open http://localhost:5000 in your browser")
    logger.info("-" * 40)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=Config.DEBUG)

