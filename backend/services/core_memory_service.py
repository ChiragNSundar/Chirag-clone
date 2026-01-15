"""
Core Memory Service - Long-term memory summarization for the digital clone.
Runs nightly jobs to summarize conversations into "Core Memories" like:
"User mentioned they hate spinach on 2024-01-14"
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import json
import re
import chromadb
from chromadb.config import Settings

from config import Config
from .llm_service import get_llm_service
from .memory_service import get_memory_service
from .logger import get_logger

logger = get_logger(__name__)


class CoreMemoryService:
    """Service for managing long-term summarized memories (Core Memories)."""
    
    def __init__(self):
        self.llm = get_llm_service()
        self.memory = get_memory_service()
        
        # Initialize ChromaDB collection for core memories
        self.client = chromadb.PersistentClient(
            path=Config.CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.core_memories = self.client.get_or_create_collection(
            name="core_memories",
            metadata={"description": "Long-term summarized memories about the user"}
        )
        
        # Categories for core memories
        self.MEMORY_CATEGORIES = [
            "preferences",      # Likes, dislikes, favorites
            "facts",           # Factual information about the user
            "relationships",   # People in user's life
            "experiences",     # Events, trips, milestones
            "opinions",        # Views, beliefs, opinions
            "habits",          # Routines, behaviors
            "goals",           # Aspirations, plans
        ]
    
    def summarize_recent_conversations(
        self,
        days_back: int = 1,
        min_messages: int = 5
    ) -> List[Dict]:
        """
        Summarize recent conversations into core memories.
        
        Args:
            days_back: Number of days of conversations to summarize
            min_messages: Minimum messages required to generate summaries
            
        Returns:
            List of created core memories
        """
        try:
            # Get recent conversation examples
            examples = self.memory.get_all_examples_with_metadata(limit=500)
            
            if not examples or len(examples) < min_messages:
                logger.info(f"Not enough messages to summarize: {len(examples) if examples else 0}")
                return []
            
            # Filter to recent conversations
            cutoff_date = datetime.now() - timedelta(days=days_back)
            recent_examples = []
            
            for example in examples:
                timestamp_str = example.get('timestamp', '')
                if timestamp_str:
                    try:
                        # Parse ISO format timestamp
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if timestamp.replace(tzinfo=None) >= cutoff_date:
                            recent_examples.append(example)
                    except (ValueError, TypeError):
                        recent_examples.append(example)  # Include if can't parse
            
            if not recent_examples:
                logger.info("No recent conversations to summarize")
                return []
            
            # Format conversations for summarization
            conversation_text = self._format_conversations(recent_examples)
            
            # Generate core memories using LLM
            new_memories = self._extract_core_memories(conversation_text)
            
            # Store in ChromaDB
            stored_memories = []
            for memory in new_memories:
                stored = self._store_core_memory(memory)
                if stored:
                    stored_memories.append(stored)
            
            logger.info(f"Created {len(stored_memories)} new core memories")
            return stored_memories
            
        except Exception as e:
            logger.error(f"Error summarizing conversations: {e}")
            return []
    
    def _format_conversations(self, examples: List[Dict]) -> str:
        """Format conversation examples for summarization."""
        lines = []
        for ex in examples[:100]:  # Limit to avoid token overflow
            context = ex.get('content', ex.get('context', ''))
            response = ex.get('response', '')
            if context:
                lines.append(f"Context: {context}")
            if response:
                lines.append(f"Response: {response}")
            lines.append("---")
        return "\n".join(lines)
    
    def _extract_core_memories(self, conversation_text: str) -> List[Dict]:
        """Use LLM to extract core memories from conversations."""
        prompt = f"""Analyze these conversations and extract key personal facts, preferences, and memories about the user.
        
For each memory, provide:
1. A clear, specific statement (e.g., "User hates spinach", "User's favorite movie is Inception")
2. A category: {', '.join(self.MEMORY_CATEGORIES)}
3. Importance score 1-5 (5 = core identity, 1 = minor detail)

Format as JSON array:
[
    {{"memory": "specific statement", "category": "category", "importance": 3}},
    ...
]

Only extract NEW information. Be specific, not vague. Focus on concrete facts.

Conversations:
{conversation_text}

Extract memories (JSON only):"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3
            )
            
            # Parse JSON from response
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                memories = json.loads(json_match.group())
                return memories
            return []
            
        except Exception as e:
            logger.error(f"Error extracting core memories: {e}")
            return []
    
    def _store_core_memory(self, memory: Dict) -> Optional[Dict]:
        """Store a core memory in ChromaDB."""
        try:
            memory_text = memory.get('memory', '')
            category = memory.get('category', 'facts')
            importance = memory.get('importance', 3)
            
            if not memory_text:
                return None
            
            # Check for duplicates
            existing = self.core_memories.query(
                query_texts=[memory_text],
                n_results=1
            )
            
            if existing['distances'] and existing['distances'][0] and existing['distances'][0][0] < 0.2:
                logger.debug(f"Duplicate core memory skipped: {memory_text[:50]}")
                return None
            
            # Generate unique ID
            import hashlib
            memory_id = hashlib.md5(f"{memory_text}{datetime.now().isoformat()}".encode()).hexdigest()[:16]
            
            self.core_memories.add(
                ids=[memory_id],
                documents=[memory_text],
                metadatas=[{
                    'category': category,
                    'importance': importance,
                    'created_at': datetime.now().isoformat(),
                    'source': 'conversation_summary'
                }]
            )
            
            return {
                'id': memory_id,
                'memory': memory_text,
                'category': category,
                'importance': importance
            }
            
        except Exception as e:
            logger.error(f"Error storing core memory: {e}")
            return None
    
    def get_core_memories(
        self,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Retrieve stored core memories.
        
        Args:
            category: Optional filter by category
            limit: Maximum memories to return
        """
        try:
            where_filter = {"category": category} if category else None
            
            results = self.core_memories.get(
                where=where_filter,
                limit=limit
            )
            
            memories = []
            if results and results['ids']:
                for i, id in enumerate(results['ids']):
                    memories.append({
                        'id': id,
                        'memory': results['documents'][i] if results['documents'] else '',
                        'category': results['metadatas'][i].get('category', '') if results['metadatas'] else '',
                        'importance': results['metadatas'][i].get('importance', 3) if results['metadatas'] else 3,
                        'created_at': results['metadatas'][i].get('created_at', '') if results['metadatas'] else ''
                    })
            
            # Sort by importance
            memories.sort(key=lambda x: x.get('importance', 0), reverse=True)
            return memories
            
        except Exception as e:
            logger.error(f"Error retrieving core memories: {e}")
            return []
    
    def get_relevant_memories(self, query: str, n_results: int = 5) -> List[Dict]:
        """Get core memories relevant to a query for RAG context."""
        try:
            results = self.core_memories.query(
                query_texts=[query],
                n_results=n_results
            )
            
            memories = []
            if results and results['ids'] and results['ids'][0]:
                for i, id in enumerate(results['ids'][0]):
                    memories.append({
                        'id': id,
                        'memory': results['documents'][0][i] if results['documents'] else '',
                        'category': results['metadatas'][0][i].get('category', '') if results['metadatas'] else ''
                    })
            
            return memories
            
        except Exception as e:
            logger.error(f"Error getting relevant memories: {e}")
            return []
    
    def delete_core_memory(self, memory_id: str) -> bool:
        """Delete a core memory by ID."""
        try:
            self.core_memories.delete(ids=[memory_id])
            return True
        except Exception as e:
            logger.error(f"Error deleting core memory: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get statistics about core memories."""
        try:
            count = self.core_memories.count()
            memories = self.get_core_memories(limit=500)
            
            category_counts = {}
            for mem in memories:
                cat = mem.get('category', 'unknown')
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            return {
                'total_memories': count,
                'categories': category_counts,
                'available_categories': self.MEMORY_CATEGORIES
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'total_memories': 0, 'categories': {}}


# Singleton instance
_core_memory_service: Optional[CoreMemoryService] = None


def get_core_memory_service() -> CoreMemoryService:
    """Get the singleton core memory service instance."""
    global _core_memory_service
    if _core_memory_service is None:
        _core_memory_service = CoreMemoryService()
    return _core_memory_service
