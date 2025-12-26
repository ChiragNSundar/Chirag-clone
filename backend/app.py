"""
Personal AI Clone Bot - Main Flask Application
"""
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os

from config import Config
from routes import chat_bp, training_bp, upload_bp, visualization_bp, autopilot_bp, timeline_bp, analytics_bp

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config.from_object(Config)

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
    print('Client connected')
    emit('connected', {'message': 'Connected to AI Clone Bot'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')


@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle incoming chat messages via WebSocket."""
    from services.chat_service import get_chat_service
    
    message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    if not message.strip():
        emit('error', {'message': 'Empty message'})
        return
    
    try:
        chat_service = get_chat_service()
        response = chat_service.generate_response(message, session_id)
        
        emit('chat_response', {
            'response': response,
            'session_id': session_id
        })
    except Exception as e:
        print(f"WebSocket chat error: {e}")
        emit('error', {'message': str(e)})


@socketio.on('training_feedback')
def handle_training_feedback(data):
    """Handle training feedback via WebSocket."""
    from services.chat_service import get_chat_service
    
    context = data.get('context', '')
    response = data.get('correct_response', '')
    
    if context and response:
        try:
            chat_service = get_chat_service()
            chat_service.train_from_interaction(context, response)
            emit('training_saved', {'success': True})
        except Exception as e:
            emit('error', {'message': str(e)})


# Health check endpoint
@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    return {'status': 'healthy', 'service': 'AI Clone Bot'}


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return {'error': 'Not found'}, 404


@app.errorhandler(500)
def server_error(e):
    return {'error': 'Internal server error'}, 500


if __name__ == '__main__':
    print("Starting Personal AI Clone Bot...")
    print(f"LLM Provider: {Config.LLM_PROVIDER}")
    print(f"Model: {getattr(Config, f'{Config.LLM_PROVIDER.upper()}_MODEL', 'default')}")
    print(f"Bot Name: {Config.BOT_NAME}")
    print("-" * 40)
    
    # Pre-load services in background for faster first response
    import threading
    def preload_services():
        try:
            print("Pre-loading AI services...")
            from services.chat_service import get_chat_service
            get_chat_service()  # This initializes LLM, Memory, and Personality
            print("AI services ready!")
        except Exception as e:
            print(f"Pre-loading warning: {e}")
    
    threading.Thread(target=preload_services, daemon=True).start()
    
    print("Open http://localhost:5000 in your browser")
    print("-" * 40)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=Config.DEBUG)
