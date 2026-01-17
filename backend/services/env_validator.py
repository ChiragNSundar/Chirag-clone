"""
Environment Validator - Validate required environment variables on startup.
"""
import os
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


@dataclass
class EnvVar:
    """Environment variable definition."""
    name: str
    severity: Severity = Severity.REQUIRED
    description: str = ""
    default: Optional[str] = None
    secret: bool = False  # Mask value in logs
    validator: Optional[callable] = None


@dataclass
class ValidationResult:
    """Result of environment validation."""
    valid: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    loaded: dict = field(default_factory=dict)


# Define all environment variables
ENV_VARS = [
    # Required
    EnvVar("GOOGLE_API_KEY", Severity.REQUIRED, "Google Gemini API key", secret=True),
    
    # Recommended
    EnvVar("OPENAI_API_KEY", Severity.RECOMMENDED, "OpenAI API key for STT", secret=True),
    EnvVar("ELEVENLABS_API_KEY", Severity.RECOMMENDED, "ElevenLabs API key for TTS", secret=True),
    
    # Optional
    EnvVar("DISCORD_BOT_TOKEN", Severity.OPTIONAL, "Discord bot token", secret=True),
    EnvVar("TELEGRAM_BOT_TOKEN", Severity.OPTIONAL, "Telegram bot token", secret=True),
    EnvVar("DATABASE_PATH", Severity.OPTIONAL, "SQLite database path", default="data/clone.db"),
    EnvVar("LOG_LEVEL", Severity.OPTIONAL, "Logging level", default="INFO"),
    
    # Local voice
    EnvVar("LOCAL_WHISPER_MODEL", Severity.OPTIONAL, "Whisper model size", default="base"),
    EnvVar("LOCAL_PIPER_VOICE", Severity.OPTIONAL, "Piper TTS voice", default="en_US-lessac-medium"),
    
    # Performance
    EnvVar("CACHE_TTL_SECONDS", Severity.OPTIONAL, "Default cache TTL", default="300"),
    EnvVar("MAX_WORKERS", Severity.OPTIONAL, "Thread pool workers", default="4"),
]


def validate_environment() -> ValidationResult:
    """
    Validate all environment variables.
    
    Returns:
        ValidationResult with errors, warnings, and loaded values.
    """
    result = ValidationResult()
    
    for var in ENV_VARS:
        value = os.environ.get(var.name, var.default)
        
        if value:
            # Run custom validator if present
            if var.validator:
                try:
                    var.validator(value)
                except Exception as e:
                    result.errors.append(f"{var.name}: validation failed - {e}")
                    result.valid = False
                    continue
            
            # Store (masked if secret)
            result.loaded[var.name] = "***" if var.secret else value
            
        elif var.severity == Severity.REQUIRED:
            result.errors.append(f"Missing required: {var.name} - {var.description}")
            result.valid = False
            
        elif var.severity == Severity.RECOMMENDED:
            result.warnings.append(f"Missing recommended: {var.name} - {var.description}")
    
    return result


def print_validation_report(result: ValidationResult):
    """Print a formatted validation report."""
    print("\n" + "=" * 50)
    print("Environment Validation Report")
    print("=" * 50)
    
    if result.errors:
        print("\n❌ ERRORS:")
        for error in result.errors:
            print(f"   • {error}")
    
    if result.warnings:
        print("\n⚠️  WARNINGS:")
        for warning in result.warnings:
            print(f"   • {warning}")
    
    print("\n✅ LOADED:")
    for name, value in result.loaded.items():
        print(f"   • {name} = {value}")
    
    print("\n" + "-" * 50)
    status = "PASS ✓" if result.valid else "FAIL ✗" 
    print(f"Status: {status}")
    print("=" * 50 + "\n")


def get_env(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """
    Get environment variable with optional requirement.
    
    Args:
        name: Variable name
        default: Default value if not set
        required: Raise error if not set
    
    Returns:
        Variable value or default
    
    Raises:
        ValueError if required and not set
    """
    value = os.environ.get(name, default)
    
    if required and not value:
        raise ValueError(f"Required environment variable not set: {name}")
    
    return value


def get_env_bool(name: str, default: bool = False) -> bool:
    """Get environment variable as boolean."""
    value = os.environ.get(name, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


def get_env_int(name: str, default: int = 0) -> int:
    """Get environment variable as integer."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_list(name: str, default: list = None, separator: str = ',') -> list:
    """Get environment variable as list."""
    value = os.environ.get(name)
    if value is None:
        return default or []
    return [item.strip() for item in value.split(separator) if item.strip()]


# Run validation on import (in development)
if os.environ.get("VALIDATE_ENV_ON_IMPORT", "false").lower() == "true":
    result = validate_environment()
    print_validation_report(result)
    if not result.valid:
        raise RuntimeError("Environment validation failed")
