"""
Configuration settings for the Personal AI Clone Bot.
Enhanced with startup validation and robustness settings.
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
    
    # LLM Provider Settings
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini')  # 'gemini', 'openai', 'anthropic', 'ollama'
    
    # Gemini (Primary)
    # Supports comma-separated keys for rotation
    GEMINI_API_KEYS = [k.strip() for k in os.getenv('GEMINI_API_KEY', '').split(',') if k.strip()]
    GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ''
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    
    # Model Hierarchy (Strictly V2+)
    # Order: Gemma 2 27b -> Gemini 2.0 Flash Lite -> Gemini 2.0 Flash -> Gemini 2.0 Pro
    GEMINI_MODELS = [
        "gemma-2-27b-it",                  # Efficient open model
        "gemini-2.0-flash-lite-preview-02-05", # Fast & cheap
        "gemini-2.0-flash",                # Balanced
        "gemini-2.0-pro-exp-02-05",        # High intelligence
        "gemini-2.0-flash-thinking-exp-1219" # Reasoning model
    ]
    
    # OpenAI (Fallback)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    
    # Ollama (Local LLM - First Class Support)
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_FIRST_CLASS = os.getenv('OLLAMA_FIRST_CLASS', 'False').lower() == 'true'
    OLLAMA_AUTO_DETECT = os.getenv('OLLAMA_AUTO_DETECT', 'True').lower() == 'true'
    
    # Model Settings
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2')
    
    # Personality Settings
    BOT_NAME = os.getenv('BOT_NAME', 'Chirag')
    USER_NAME = os.getenv('USER_NAME', 'User')
    
    # Database Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    CHROMA_DB_PATH = os.path.join(DATA_DIR, 'chroma_db')
    PERSONALITY_FILE = os.path.join(DATA_DIR, 'personality_profile.json')
    UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')
    
    # Embedding Settings
    EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
    
    # Chat Settings
    MAX_CONTEXT_MESSAGES = 10
    MAX_FEW_SHOT_EXAMPLES = 5
    TEMPERATURE = 0.8
    MAX_TOKENS = 256
    
    # Robustness Settings
    MAX_MESSAGE_LENGTH = 10000           # Max characters per chat message
    MAX_UPLOAD_SIZE_MB = 5               # Max file upload size in MB
    MAX_REQUEST_SIZE_MB = 10             # Max total request size in MB
    LLM_REQUEST_TIMEOUT = 30             # Seconds for LLM API timeout
    LLM_RETRY_COUNT = 3                  # Number of retries for LLM failures
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
    
    # Check API key configuration based on provider
    if Config.LLM_PROVIDER == 'gemini':
        if not Config.GEMINI_API_KEYS or Config.GEMINI_API_KEYS[0] == 'your-gemini-api-key-here':
            warnings.append("GEMINI_API_KEY not configured - chat will not work")
    elif Config.LLM_PROVIDER == 'openai':
        if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == 'sk-your-openai-key-here':
            warnings.append("OPENAI_API_KEY not configured - chat will not work")
    elif Config.LLM_PROVIDER == 'anthropic':
        if not Config.ANTHROPIC_API_KEY or Config.ANTHROPIC_API_KEY == 'sk-ant-your-anthropic-key-here':
            warnings.append("ANTHROPIC_API_KEY not configured - chat will not work")
    
    # Check secret key
    if Config.SECRET_KEY == 'dev-secret-key-change-in-production' and not Config.DEBUG:
        warnings.append("Using default SECRET_KEY in production mode")
    
    # Check data directories exist
    for dir_name, dir_path in [('DATA_DIR', Config.DATA_DIR), 
                                ('CHROMA_DB_PATH', Config.CHROMA_DB_PATH),
                                ('UPLOADS_DIR', Config.UPLOADS_DIR)]:
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
    
    return warnings


# Create directories if they don't exist
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.CHROMA_DB_PATH, exist_ok=True)
os.makedirs(Config.UPLOADS_DIR, exist_ok=True)
