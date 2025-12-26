"""
Configuration settings for the Personal AI Clone Bot.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration."""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # LLM Provider Settings
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini')  # 'gemini', 'openai', 'anthropic', 'ollama'
    
    # Gemini (Primary)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
    
    # OpenAI (Fallback)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    
    # Model Settings
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-3-haiku-20240307')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama2')
    
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


# Create directories if they don't exist
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.CHROMA_DB_PATH, exist_ok=True)
os.makedirs(Config.UPLOADS_DIR, exist_ok=True)
