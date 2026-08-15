"""
Configuration settings for the Personal AI Clone Bot.
Enhanced with startup validation and robustness settings.

LOCAL-FIRST: This project uses LM Studio as the sole LLM provider.
No cloud APIs (Gemini, OpenAI, Anthropic) are used.
"""
import os
import logging
from dotenv import load_dotenv
from typing import List

load_dotenv()


class Config:
    """Application configuration."""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Logging
    LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
    
    # LLM Provider Settings — LOCAL ONLY
    # LM Studio is the sole provider. If it's not running, the app falls back to RAG + context files.
    LLM_PROVIDER = 'lmstudio'
    
    # LM Studio (Primary & Only LLM)
    LMSTUDIO_BASE_URL = os.getenv('LMSTUDIO_BASE_URL', 'http://localhost:1234')
    LMSTUDIO_MODEL = os.getenv('LMSTUDIO_MODEL', 'auto')  # 'auto' = detect loaded model
    
    # Personality Settings
    BOT_NAME = os.getenv('BOT_NAME', 'Chirag')
    USER_NAME = os.getenv('USER_NAME', 'User')
    
    # Database Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    CHROMA_DB_PATH = os.path.join(DATA_DIR, 'chroma_db')
    PERSONALITY_FILE = os.path.join(DATA_DIR, 'personality_profile.json')
    UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')
    
    # Context Files (Offline RAG)
    CONTEXT_FILES_DIR = os.getenv('CONTEXT_FILES_DIR', os.path.join(DATA_DIR, 'context'))
    
    # Embedding Settings (local sentence-transformers)
    EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
    
    # Chat Settings
    MAX_CONTEXT_MESSAGES = 10
    MAX_FEW_SHOT_EXAMPLES = 5
    TEMPERATURE = 0.8
    MAX_TOKENS = 4096  # Bumped from 256 — local LLMs can handle more
    
    # Robustness Settings
    MAX_MESSAGE_LENGTH = 10000           # Max characters per chat message
    MAX_UPLOAD_SIZE_MB = 5               # Max file upload size in MB
    MAX_REQUEST_SIZE_MB = 10             # Max total request size in MB
    LLM_REQUEST_TIMEOUT = 120            # Seconds for LLM timeout (local models can be slow)
    LLM_RETRY_COUNT = 2                  # Number of retries for LLM failures
    CIRCUIT_BREAKER_THRESHOLD = 5        # Failures before circuit opens
    CIRCUIT_BREAKER_TIMEOUT = 60         # Seconds before circuit resets
    
    # Rate Limiting
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    RATE_LIMIT_CHAT = 30                 # Requests per minute for chat
    RATE_LIMIT_DEFAULT = 100             # Default requests per minute
    
    # Local Training Settings
    LOCAL_TRAINING_ENABLED = os.getenv('LOCAL_TRAINING_ENABLED', 'true').lower() == 'true'
    LOCAL_ADAPTERS_DIR = os.getenv('LOCAL_ADAPTERS_DIR', os.path.join(BASE_DIR, '..', 'adapters'))
    LOCAL_MODELS_DIR = os.getenv('LOCAL_MODELS_DIR', os.path.join(BASE_DIR, '..', 'models'))
    DEFAULT_BASE_MODEL = os.getenv('DEFAULT_BASE_MODEL', 'unsloth/phi-2-bnb-4bit')
    GPU_MEMORY_FRACTION = float(os.getenv('GPU_MEMORY_FRACTION', '0.9'))
    
    # LoRA Training Defaults
    DEFAULT_LORA_R = int(os.getenv('DEFAULT_LORA_R', '16'))
    DEFAULT_LORA_ALPHA = int(os.getenv('DEFAULT_LORA_ALPHA', '32'))
    DEFAULT_MAX_SEQ_LENGTH = int(os.getenv('DEFAULT_MAX_SEQ_LENGTH', '2048'))


def validate_config() -> List[str]:
    """
    Validate configuration at startup.
    Returns list of warning messages (empty if all OK).
    """
    warnings = []
    
    # Check LM Studio availability
    try:
        import requests
        resp = requests.get(f"{Config.LMSTUDIO_BASE_URL}/v1/models", timeout=3)
        if resp.status_code == 200:
            models = resp.json().get('data', [])
            if not models:
                warnings.append(
                    "LM Studio is running but no model is loaded. "
                    "Chat will fall back to RAG + context files only."
                )
        else:
            warnings.append(
                "LM Studio not responding. "
                "Chat will fall back to RAG + context files only."
            )
    except Exception:
        warnings.append(
            f"Cannot connect to LM Studio at {Config.LMSTUDIO_BASE_URL}. "
            "Chat will fall back to RAG + context files only. "
            "Start LM Studio and load a model for full AI functionality."
        )
    
    # Check secret key
    if Config.SECRET_KEY == 'dev-secret-key-change-in-production' and not Config.DEBUG:
        warnings.append("Using default SECRET_KEY in production mode")
    
    # Check data directories exist
    for dir_name, dir_path in [('DATA_DIR', Config.DATA_DIR), 
                                ('CHROMA_DB_PATH', Config.CHROMA_DB_PATH),
                                ('UPLOADS_DIR', Config.UPLOADS_DIR),
                                ('CONTEXT_FILES_DIR', Config.CONTEXT_FILES_DIR)]:
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
            except Exception as e:
                warnings.append(f"Cannot create {dir_name}: {e}")
    
    # Check write permissions
    try:
        test_file = os.path.join(Config.DATA_DIR, '.config_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except Exception as e:
        warnings.append(f"DATA_DIR is not writable: {e}")
    
    # Check context files
    context_dir = Config.CONTEXT_FILES_DIR
    if os.path.exists(context_dir):
        context_files = [f for f in os.listdir(context_dir) 
                        if f.endswith(('.txt', '.md', '.json'))]
        if not context_files:
            warnings.append(
                f"No context files found in {context_dir}. "
                "Add .txt/.md/.json files for offline RAG context."
            )
    
    return warnings


# Create directories if they don't exist
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.CHROMA_DB_PATH, exist_ok=True)
os.makedirs(Config.UPLOADS_DIR, exist_ok=True)
os.makedirs(Config.CONTEXT_FILES_DIR, exist_ok=True)
