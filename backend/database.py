"""
Database Configuration - SQLModel (SQLite)
Provides persistent structured storage for training examples and metadata.
"""
from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, create_engine, Session, select
from config import Config
import logging

# Define Models
class TrainingExample(SQLModel, table=True):
    """Training example stored in relational DB."""
    id: Optional[int] = Field(default=None, primary_key=True)
    context: str
    response: str
    source: str = Field(default="manual")
    timestamp: datetime = Field(default_factory=datetime.now)
    chroma_id: Optional[str] = None  # Link to vector DB ID
    
# Database Setup
sqlite_file_name = "chirag.db"
sqlite_url = f"sqlite:///{Config.DATA_DIR}/{sqlite_file_name}"

engine = create_engine(sqlite_url)

def init_db():
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Get a new DB session."""
    with Session(engine) as session:
        yield session
