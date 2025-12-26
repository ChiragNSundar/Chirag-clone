"""
Upload Routes - API endpoints for uploading and processing chat exports.
Now supports async processing and smart parsing.
"""
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
from config import Config
from parsers import WhatsAppParser, DiscordParser, InstagramParser, SmartParser
from services.memory_service import get_memory_service
from services.personality_service import get_personality_service
from services.async_job_service import get_async_job_service, JobStatus

upload_bp = Blueprint('upload', __name__, url_prefix='/api/upload')

ALLOWED_EXTENSIONS = {'txt', 'json', 'csv'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
def upload_whatsapp():
    """Upload a WhatsApp chat export (sync for small files)."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    your_name = request.form.get('your_name', '')
    async_mode = request.form.get('async', 'false').lower() == 'true'
    
    if not your_name:
        return jsonify({'error': 'Your name is required'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Use .txt'}), 400
    
    try:
        content = file.read().decode('utf-8')
        
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
        
    except Exception as e:
        print(f"WhatsApp upload error: {e}")
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/discord', methods=['POST'])
def upload_discord():
    """Upload a Discord chat export."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    your_username = request.form.get('your_username', '')
    your_user_id = request.form.get('your_user_id', '')
    async_mode = request.form.get('async', 'false').lower() == 'true'
    
    if not your_username and not your_user_id:
        return jsonify({'error': 'Either username or user ID is required'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Use .json or .csv'}), 400
    
    try:
        content = file.read().decode('utf-8')
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
                    os.remove(temp_path)
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
            os.remove(temp_path)
        
        return jsonify(process_upload(result, 'discord'))
        
    except Exception as e:
        print(f"Discord upload error: {e}")
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/instagram', methods=['POST'])
def upload_instagram():
    """Upload an Instagram DM export."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    your_username = request.form.get('your_username', '')
    async_mode = request.form.get('async', 'false').lower() == 'true'
    
    if not your_username:
        return jsonify({'error': 'Your username is required'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Invalid file type. Use .json'}), 400
    
    try:
        content = file.read().decode('utf-8')
        
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
        
    except Exception as e:
        print(f"Instagram upload error: {e}")
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/smart', methods=['POST'])
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
    your_identifier = request.form.get('your_identifier', '')
    use_llm = request.form.get('use_llm', 'false').lower() == 'true'
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        content = file.read().decode('utf-8')
        parser = SmartParser(your_identifier)
        
        if use_llm:
            from services.llm_service import get_llm_service
            llm = get_llm_service()
            result = parser.parse_with_llm(content, llm)
        else:
            result = parser.parse_content(content)
        
        return jsonify(process_upload(result, 'smart_import'))
        
    except Exception as e:
        print(f"Smart upload error: {e}")
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/text', methods=['POST'])
def upload_text_examples():
    """Upload raw text examples directly."""
    data = request.get_json()
    
    if not data or 'examples' not in data:
        return jsonify({'error': 'Examples array is required'}), 400
    
    examples = data['examples']
    if not isinstance(examples, list):
        return jsonify({'error': 'Examples must be an array'}), 400
    
    try:
        memory = get_memory_service()
        personality = get_personality_service()
        
        pairs = []
        responses = []
        
        for ex in examples:
            context = ex.get('context', '').strip()
            response = ex.get('response', '').strip()
            if context and response:
                pairs.append((context, response))
                responses.append(response)
        
        added = memory.add_training_examples_batch(pairs, source='manual')
        personality.analyze_messages(responses)
        
        return jsonify({
            'success': True,
            'examples_added': added,
            'message': f'Added {added} training examples'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/status/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    """Get the status of an async upload job."""
    job_service = get_async_job_service()
    job = job_service.get_job(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job.to_dict())
