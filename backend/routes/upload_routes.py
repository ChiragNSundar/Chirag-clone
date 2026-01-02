"""
Upload Routes - API endpoints for uploading and processing chat exports.
Enhanced with file validation, size limits, and rate limiting.
"""
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import re
from config import Config
from parsers import WhatsAppParser, DiscordParser, InstagramParser, SmartParser
from services.memory_service import get_memory_service
from services.personality_service import get_personality_service
from services.async_job_service import get_async_job_service, JobStatus
from services.rate_limiter import rate_limit
from services.logger import get_logger

upload_bp = Blueprint('upload', __name__, url_prefix='/api/upload')
logger = get_logger(__name__)

# File validation constants
ALLOWED_EXTENSIONS = {'txt', 'json', 'csv'}
MAX_FILE_SIZE_MB = getattr(Config, 'MAX_UPLOAD_SIZE_MB', 5)
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_EXAMPLES_PER_UPLOAD = 1000
MAX_IDENTIFIER_LENGTH = 100


def allowed_file(filename):
    """Check if file extension is allowed."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def validate_file_upload(file):
    """
    Validate uploaded file.
    Returns (is_valid, error_message or None)
    """
    if not file:
        return False, 'No file provided'
    
    if file.filename == '' or not file.filename:
        return False, 'No file selected'
    
    if not allowed_file(file.filename):
        return False, f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
    
    # Check file size (seek to end, check position, seek back)
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Seek back to start
    
    if size > MAX_FILE_SIZE_BYTES:
        return False, f'File too large. Maximum size: {MAX_FILE_SIZE_MB}MB'
    
    if size == 0:
        return False, 'File is empty'
    
    return True, None


def sanitize_identifier(identifier: str) -> str:
    """Sanitize user identifier (name/username)."""
    if not identifier:
        return ''
    # Remove control characters and limit length
    cleaned = ''.join(char for char in identifier if char >= ' ')
    return cleaned[:MAX_IDENTIFIER_LENGTH].strip()


def process_upload(parser_result, source: str) -> dict:
    """Common processing logic for all uploads."""
    memory = get_memory_service()
    personality = get_personality_service()
    
    added = memory.add_training_examples_batch(
        parser_result['conversation_pairs'],
        source=source
    )
    
    personality.analyze_messages(parser_result['your_texts'])
    
    return {
        'success': True,
        'total_messages': parser_result['total_messages'],
        'your_messages': parser_result['your_messages'],
        'training_examples_added': added,
        'message': f'Processed {parser_result["total_messages"]} messages, added {added} training examples'
    }


@upload_bp.route('/whatsapp', methods=['POST'])
@rate_limit
def upload_whatsapp():
    """Upload a WhatsApp chat export (sync for small files)."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Validate file
    is_valid, error = validate_file_upload(file)
    if not is_valid:
        return jsonify({'error': error}), 400
    
    your_name = sanitize_identifier(request.form.get('your_name', ''))
    async_mode = request.form.get('async', 'false').lower() == 'true'
    
    if not your_name:
        return jsonify({'error': 'Your name is required'}), 400
    
    try:
        content = file.read().decode('utf-8', errors='replace')
        
        # Use async for large files
        if async_mode or len(content) > 100000:  # > 100KB
            job_service = get_async_job_service()
            job_id = job_service.create_job('whatsapp_import')
            
            def process():
                parser = WhatsAppParser(your_name)
                result = parser.parse_content(content)
                return process_upload(result, 'whatsapp')
            
            job_service.run_async(job_id, process)
            
            return jsonify({
                'async': True,
                'job_id': job_id,
                'message': 'Processing started. Check status at /api/upload/status/' + job_id
            })
        
        # Sync processing for small files
        parser = WhatsAppParser(your_name)
        result = parser.parse_content(content)
        return jsonify(process_upload(result, 'whatsapp'))
        
    except UnicodeDecodeError as e:
        logger.warning(f"WhatsApp file encoding error: {e}")
        return jsonify({'error': 'File encoding error. Please use UTF-8 encoded files.'}), 400
    except Exception as e:
        logger.error(f"WhatsApp upload error: {e}")
        return jsonify({'error': 'Failed to process WhatsApp export'}), 500


@upload_bp.route('/discord', methods=['POST'])
@rate_limit
def upload_discord():
    """Upload a Discord chat export."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Validate file
    is_valid, error = validate_file_upload(file)
    if not is_valid:
        return jsonify({'error': error}), 400
    
    your_username = sanitize_identifier(request.form.get('your_username', ''))
    your_user_id = sanitize_identifier(request.form.get('your_user_id', ''))
    async_mode = request.form.get('async', 'false').lower() == 'true'
    
    if not your_username and not your_user_id:
        return jsonify({'error': 'Either username or user ID is required'}), 400
    
    try:
        content = file.read().decode('utf-8', errors='replace')
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'json'
        
        if async_mode or len(content) > 100000:
            job_service = get_async_job_service()
            job_id = job_service.create_job('discord_import')
            
            def process():
                parser = DiscordParser(your_user_id, your_username)
                if file_ext == 'json':
                    result = parser.parse_content(content, 'json')
                else:
                    temp_path = os.path.join(Config.UPLOADS_DIR, f'temp_{job_id}.csv')
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    result = parser.parse_file(temp_path)
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                return process_upload(result, 'discord')
            
            job_service.run_async(job_id, process)
            
            return jsonify({
                'async': True,
                'job_id': job_id,
                'message': 'Processing started'
            })
        
        parser = DiscordParser(your_user_id, your_username)
        if file_ext == 'json':
            result = parser.parse_content(content, 'json')
        else:
            temp_path = os.path.join(Config.UPLOADS_DIR, secure_filename(file.filename))
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            result = parser.parse_file(temp_path)
            try:
                os.remove(temp_path)
            except:
                pass
        
        return jsonify(process_upload(result, 'discord'))
        
    except UnicodeDecodeError as e:
        logger.warning(f"Discord file encoding error: {e}")
        return jsonify({'error': 'File encoding error. Please use UTF-8 encoded files.'}), 400
    except Exception as e:
        logger.error(f"Discord upload error: {e}")
        return jsonify({'error': 'Failed to process Discord export'}), 500


@upload_bp.route('/instagram', methods=['POST'])
@rate_limit
def upload_instagram():
    """Upload an Instagram DM export."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Validate file
    is_valid, error = validate_file_upload(file)
    if not is_valid:
        return jsonify({'error': error}), 400
    
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Invalid file type. Use .json'}), 400
    
    your_username = sanitize_identifier(request.form.get('your_username', ''))
    async_mode = request.form.get('async', 'false').lower() == 'true'
    
    if not your_username:
        return jsonify({'error': 'Your username is required'}), 400
    
    try:
        content = file.read().decode('utf-8', errors='replace')
        
        if async_mode or len(content) > 100000:
            job_service = get_async_job_service()
            job_id = job_service.create_job('instagram_import')
            
            def process():
                parser = InstagramParser(your_username)
                result = parser.parse_content(content)
                return process_upload(result, 'instagram')
            
            job_service.run_async(job_id, process)
            
            return jsonify({
                'async': True,
                'job_id': job_id,
                'message': 'Processing started'
            })
        
        parser = InstagramParser(your_username)
        result = parser.parse_content(content)
        return jsonify(process_upload(result, 'instagram'))
        
    except UnicodeDecodeError as e:
        logger.warning(f"Instagram file encoding error: {e}")
        return jsonify({'error': 'File encoding error. Please use UTF-8 encoded files.'}), 400
    except Exception as e:
        logger.error(f"Instagram upload error: {e}")
        return jsonify({'error': 'Failed to process Instagram export'}), 500


@upload_bp.route('/smart', methods=['POST'])
@rate_limit
def upload_smart():
    """
    Smart upload - parses any text format using heuristics and LLM.
    
    Form data:
    - file: Any text file
    - your_identifier: Your name/username in the conversation
    - use_llm: Whether to use LLM for parsing (default: false)
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Validate file
    is_valid, error = validate_file_upload(file)
    if not is_valid:
        return jsonify({'error': error}), 400
    
    your_identifier = sanitize_identifier(request.form.get('your_identifier', ''))
    use_llm = request.form.get('use_llm', 'false').lower() == 'true'
    
    try:
        content = file.read().decode('utf-8', errors='replace')
        parser = SmartParser(your_identifier)
        
        if use_llm:
            from services.llm_service import get_llm_service
            llm = get_llm_service()
            result = parser.parse_with_llm(content, llm)
        else:
            result = parser.parse_content(content)
        
        return jsonify(process_upload(result, 'smart_import'))
        
    except UnicodeDecodeError as e:
        logger.warning(f"Smart upload encoding error: {e}")
        return jsonify({'error': 'File encoding error. Please use UTF-8 encoded files.'}), 400
    except Exception as e:
        logger.error(f"Smart upload error: {e}")
        return jsonify({'error': 'Failed to process file'}), 500


@upload_bp.route('/text', methods=['POST'])
@rate_limit
def upload_text_examples():
    """Upload raw text examples directly."""
    try:
        data = request.get_json()
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    if not data or 'examples' not in data:
        return jsonify({'error': 'Examples array is required'}), 400
    
    examples = data['examples']
    if not isinstance(examples, list):
        return jsonify({'error': 'Examples must be an array'}), 400
    
    if len(examples) > MAX_EXAMPLES_PER_UPLOAD:
        return jsonify({'error': f'Too many examples. Maximum: {MAX_EXAMPLES_PER_UPLOAD}'}), 400
    
    try:
        memory = get_memory_service()
        personality = get_personality_service()
        
        pairs = []
        responses = []
        
        for ex in examples:
            if not isinstance(ex, dict):
                continue
            
            context = ex.get('context', '')
            response = ex.get('response', '')
            
            if isinstance(context, str) and isinstance(response, str):
                context = context.strip()[:5000]  # Limit length
                response = response.strip()[:5000]
                if context and response:
                    pairs.append((context, response))
                    responses.append(response)
        
        if not pairs:
            return jsonify({'error': 'No valid examples provided'}), 400
        
        added = memory.add_training_examples_batch(pairs, source='manual')
        personality.analyze_messages(responses)
        
        return jsonify({
            'success': True,
            'examples_added': added,
            'message': f'Added {added} training examples'
        })
        
    except Exception as e:
        logger.error(f"Text examples upload error: {e}")
        return jsonify({'error': 'Failed to add examples'}), 500


@upload_bp.route('/status/<job_id>', methods=['GET'])
@rate_limit
def get_job_status(job_id: str):
    """Get the status of an async upload job."""
    # Validate job_id format (should be UUID-like)
    if not job_id or len(job_id) > 50:
        return jsonify({'error': 'Invalid job ID'}), 400
    
    if not re.match(r'^[a-zA-Z0-9\-_]+$', job_id):
        return jsonify({'error': 'Invalid job ID format'}), 400
    
    job_service = get_async_job_service()
    job = job_service.get_job(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job.to_dict())
