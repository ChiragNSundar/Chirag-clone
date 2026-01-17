"""
Strict Pydantic Input Validation Models - Ensure all API inputs are validated.
Uses Pydantic v2 with strict mode for maximum safety.
"""
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# ============= Chat Models =============

class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User message to send"
    )
    session_id: Optional[str] = Field(
        default=None,
        pattern=r'^[a-zA-Z0-9_-]{1,64}$',
        description="Optional session identifier"
    )
    training_mode: bool = Field(
        default=False,
        description="Enable training mode for feedback"
    )
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        # Strip whitespace
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        return v


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    response: str
    session_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    thinking_steps: Optional[List[str]] = None
    sources: Optional[List[str]] = None


# ============= Feedback Models =============

class FeedbackRequest(BaseModel):
    """Feedback on a chat response."""
    message_id: str = Field(
        ...,
        pattern=r'^[a-zA-Z0-9_-]{1,64}$'
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Rating from 1 (bad) to 5 (excellent)"
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=1000
    )
    feedback_type: Literal["accuracy", "tone", "relevance", "other"] = "other"


# ============= Training Models =============

class TrainingExampleRequest(BaseModel):
    """Add a training example."""
    context: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Context or question"
    )
    response: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Expected response"
    )
    category: Optional[str] = Field(
        default=None,
        pattern=r'^[a-zA-Z0-9_-]{1,32}$'
    )
    tags: Optional[List[str]] = Field(
        default=None,
        max_length=10
    )
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        # Validate each tag
        pattern = re.compile(r'^[a-zA-Z0-9_-]{1,32}$')
        for tag in v:
            if not pattern.match(tag):
                raise ValueError(f'Invalid tag format: {tag}')
        return v


# ============= Research Models =============

class DeepResearchRequest(BaseModel):
    """Request for deep research."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=5
    )
    max_sources: int = Field(
        default=10,
        ge=1,
        le=50
    )
    include_domains: Optional[List[str]] = None
    exclude_domains: Optional[List[str]] = None


# ============= Rewind Models =============

class RewindQueryRequest(BaseModel):
    """Query the rewind memory."""
    question: str = Field(
        ...,
        min_length=3,
        max_length=500
    )
    time_range_minutes: Optional[int] = Field(
        default=30,
        ge=1,
        le=1440  # Max 24 hours
    )


# ============= Upload Models =============

class FileUploadMetadata(BaseModel):
    """Metadata for file uploads."""
    filename: str = Field(
        ...,
        pattern=r'^[\w\-. ]+\.[a-zA-Z0-9]{1,10}$',
        max_length=255
    )
    content_type: str = Field(
        ...,
        pattern=r'^[a-zA-Z0-9]+/[a-zA-Z0-9.+-]+$'
    )
    size_bytes: int = Field(
        ...,
        gt=0,
        le=50 * 1024 * 1024  # Max 50MB
    )
    
    @field_validator('content_type')
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        allowed_types = {
            'text/plain',
            'text/markdown',
            'application/pdf',
            'application/json',
            'image/jpeg',
            'image/png',
            'image/webp',
        }
        if v not in allowed_types:
            raise ValueError(f'Content type not allowed: {v}')
        return v


# ============= Settings Models =============

class UpdateSettingsRequest(BaseModel):
    """Update user settings."""
    voice_enabled: Optional[bool] = None
    thinking_visible: Optional[bool] = None
    theme: Optional[Literal["dark", "light", "system"]] = None
    language: Optional[str] = Field(
        default=None,
        pattern=r'^[a-z]{2}(-[A-Z]{2})?$'
    )


# ============= Autopilot Models =============

class AutopilotConfigRequest(BaseModel):
    """Configure autopilot settings."""
    platform: Literal["discord", "telegram", "whatsapp"]
    enabled: bool
    channels: Optional[List[str]] = Field(
        default=None,
        max_length=20
    )
    response_delay_ms: int = Field(
        default=1000,
        ge=0,
        le=10000
    )
    max_responses_per_hour: int = Field(
        default=60,
        ge=1,
        le=1000
    )


# ============= API Key Models =============

class APIKeyRequest(BaseModel):
    """Request with API key validation."""
    api_key: str = Field(
        ...,
        min_length=20,
        max_length=256,
        pattern=r'^[a-zA-Z0-9_-]+$'
    )


# ============= Pagination Models =============

class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = Field(
        default=None,
        pattern=r'^[a-zA-Z_]+$'
    )
    sort_order: Literal["asc", "desc"] = "desc"


class PaginatedResponse(BaseModel):
    """Standard paginated response."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
