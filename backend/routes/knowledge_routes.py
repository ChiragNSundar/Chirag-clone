"""
Knowledge Routes - API endpoints for managing the knowledge base.
"""
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
from config import Config
from services.knowledge_service import get_knowledge_service

knowledge_bp = Blueprint('knowledge', __name__, url_prefix='/api/knowledge')

ALLOWED_EXTENSIONS = {'txt', 'md', 'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@knowledge_bp.route('/upload', methods=['POST'])
def upload_document():
    """
    Upload a document to the knowledge base.
    
    Form data:
    - file: The document file (txt, md, pdf)
    - title: Optional title for the document
    - category: Category (personal, work, general)
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    title = request.form.get('title', '')
    category = request.form.get('category', 'general')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400
    
    try:
        # Save to temp file for processing
        filename = secure_filename(file.filename)
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)
        
        # Add to knowledge base
        knowledge = get_knowledge_service()
        result = knowledge.add_document_from_file(
            file_path=temp_path,
            title=title or filename,
            category=category
        )
        
        # Clean up temp file
        os.remove(temp_path)
        os.rmdir(temp_dir)
        
        return jsonify({
            'success': True,
            'document': result,
            'message': f'Added {result["chunk_count"]} knowledge chunks from "{result["title"]}"'
        })
        
    except Exception as e:
        print(f"Knowledge upload error: {e}")
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/text', methods=['POST'])
def add_text():
    """
    Add raw text to the knowledge base.
    
    JSON body:
    - content: The text content
    - title: Title for the document
    - category: Category (personal, work, general)
    """
    data = request.get_json()
    
    if not data or not data.get('content'):
        return jsonify({'error': 'Content is required'}), 400
    
    content = data['content'].strip()
    title = data.get('title', 'Manual Entry')
    category = data.get('category', 'general')
    
    if len(content) < 10:
        return jsonify({'error': 'Content too short (min 10 characters)'}), 400
    
    try:
        knowledge = get_knowledge_service()
        result = knowledge.add_document(
            content=content,
            filename=f"{title}.txt",
            doc_type="txt",
            title=title,
            category=category
        )
        
        return jsonify({
            'success': True,
            'document': result,
            'message': f'Added {result["chunk_count"]} knowledge chunks'
        })
        
    except Exception as e:
        print(f"Knowledge text error: {e}")
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/documents', methods=['GET'])
def list_documents():
    """Get list of all indexed documents."""
    try:
        knowledge = get_knowledge_service()
        documents = knowledge.list_documents()
        stats = knowledge.get_stats()
        
        return jsonify({
            'documents': documents,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/documents/<doc_id>', methods=['GET'])
def get_document(doc_id: str):
    """Get metadata for a specific document."""
    try:
        knowledge = get_knowledge_service()
        doc = knowledge.get_document(doc_id)
        
        if not doc:
            return jsonify({'error': 'Document not found'}), 404
        
        return jsonify(doc)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id: str):
    """Delete a document from the knowledge base."""
    try:
        knowledge = get_knowledge_service()
        deleted = knowledge.delete_document(doc_id)
        
        if not deleted:
            return jsonify({'error': 'Document not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Document deleted'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/query', methods=['POST'])
def query_knowledge():
    """
    Query the knowledge base.
    
    JSON body:
    - query: The search query
    - n_results: Number of results (default: 3)
    - category: Optional category filter
    """
    data = request.get_json()
    
    if not data or not data.get('query'):
        return jsonify({'error': 'Query is required'}), 400
    
    query = data['query'].strip()
    n_results = data.get('n_results', 3)
    category = data.get('category')
    
    try:
        knowledge = get_knowledge_service()
        results = knowledge.query_knowledge(query, n_results, category)
        
        return jsonify({
            'query': query,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get knowledge base statistics."""
    try:
        knowledge = get_knowledge_service()
        stats = knowledge.get_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
