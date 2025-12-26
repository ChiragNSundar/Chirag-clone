"""
Memory Service - Vector database operations using ChromaDB for conversation memory.
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Tuple
import json
import hashlib
from datetime import datetime
from config import Config


class MemoryService:
    """Service for managing conversation memory using ChromaDB."""
    
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=Config.CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Collection for training conversations
        self.training_collection = self.client.get_or_create_collection(
            name="training_conversations",
            metadata={"description": "Conversation examples for few-shot learning"}
        )
        
        # Collection for ongoing conversations
        self.conversation_collection = self.client.get_or_create_collection(
            name="conversations",
            metadata={"description": "Recent conversation history"}
        )
    
    def _generate_id(self, text: str) -> str:
        """Generate a unique ID for a piece of text."""
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    def add_training_example(
        self,
        context: str,
        response: str,
        source: str = "manual",
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Add a training example (context -> response pair).
        
        Args:
            context: The context/prompt that led to the response
            response: Your actual response
            source: Where this came from (whatsapp, discord, manual, etc.)
            metadata: Additional metadata
            
        Returns:
            The ID of the added example
        """
        doc_id = self._generate_id(context + response)
        
        # Combine context and response for embedding
        full_text = f"Context: {context}\nResponse: {response}"
        
        meta = {
            "source": source,
            "context": context,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        if metadata:
            meta.update(metadata)
        
        try:
            self.training_collection.add(
                documents=[full_text],
                ids=[doc_id],
                metadatas=[meta]
            )
        except Exception as e:
            # Might already exist, try update
            self.training_collection.update(
                documents=[full_text],
                ids=[doc_id],
                metadatas=[meta]
            )
        
        return doc_id
    
    def add_training_examples_batch(
        self,
        examples: List[Tuple[str, str]],
        source: str = "import"
    ) -> int:
        """
        Add multiple training examples at once.
        
        Args:
            examples: List of (context, response) tuples
            source: Source of the examples
            
        Returns:
            Number of examples added
        """
        if not examples:
            return 0
        
        documents = []
        ids = []
        metadatas = []
        
        for context, response in examples:
            doc_id = self._generate_id(context + response)
            full_text = f"Context: {context}\nResponse: {response}"
            
            documents.append(full_text)
            ids.append(doc_id)
            metadatas.append({
                "source": source,
                "context": context,
                "response": response,
                "timestamp": datetime.now().isoformat()
            })
        
        # Add in batches to avoid issues
        batch_size = 100
        added = 0
        
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            batch_meta = metadatas[i:i+batch_size]
            
            try:
                self.training_collection.add(
                    documents=batch_docs,
                    ids=batch_ids,
                    metadatas=batch_meta
                )
                added += len(batch_docs)
            except Exception as e:
                print(f"Error adding batch: {e}")
                # Try adding individually
                for j, (doc, doc_id, meta) in enumerate(zip(batch_docs, batch_ids, batch_meta)):
                    try:
                        self.training_collection.add(
                            documents=[doc],
                            ids=[doc_id],
                            metadatas=[meta]
                        )
                        added += 1
                    except:
                        pass  # Skip duplicates
        
        return added
    
    def find_similar_examples(
        self,
        query: str,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Find similar training examples for few-shot learning.
        
        Args:
            query: The current conversation context
            n_results: Number of examples to retrieve
            
        Returns:
            List of similar examples with context and response
        """
        try:
            results = self.training_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            examples = []
            if results and results['metadatas']:
                for meta in results['metadatas'][0]:
                    examples.append({
                        'context': meta.get('context', ''),
                        'response': meta.get('response', ''),
                        'source': meta.get('source', 'unknown')
                    })
            
            return examples
        except Exception as e:
            print(f"Error finding similar examples: {e}")
            return []
    
    def add_conversation_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Add a message to conversation history.
        
        Args:
            session_id: The conversation session ID
            role: 'user' or 'assistant'
            content: Message content
        """
        doc_id = f"{session_id}_{datetime.now().timestamp()}"
        
        self.conversation_collection.add(
            documents=[content],
            ids=[doc_id],
            metadatas=[{
                "session_id": session_id,
                "role": role,
                "timestamp": datetime.now().isoformat()
            }]
        )
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get recent conversation history for a session.
        
        Args:
            session_id: The conversation session ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages in chronological order
        """
        try:
            results = self.conversation_collection.get(
                where={"session_id": session_id},
                limit=limit
            )
            
            messages = []
            if results and results['metadatas']:
                for i, meta in enumerate(results['metadatas']):
                    messages.append({
                        'role': meta.get('role', 'user'),
                        'content': results['documents'][i],
                        'timestamp': meta.get('timestamp', '')
                    })
            
            # Sort by timestamp
            messages.sort(key=lambda x: x['timestamp'])
            return messages
            
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return []
    
    def get_training_stats(self) -> Dict:
        """Get statistics about training data."""
        try:
            count = self.training_collection.count()
            
            # Sample some data for source breakdown
            sample = self.training_collection.peek(limit=100)
            sources = {}
            if sample and sample['metadatas']:
                for meta in sample['metadatas']:
                    source = meta.get('source', 'unknown')
                    sources[source] = sources.get(source, 0) + 1
            
            return {
                'total_examples': count,
                'sources': sources
            }
        except Exception as e:
            return {'total_examples': 0, 'sources': {}}
    
    def get_all_examples_with_metadata(self, limit: int = 500) -> List[Dict]:
        """
        Get all training examples with full metadata for timeline.
        
        Returns:
            List of examples with content, source, timestamp, etc.
        """
        try:
            results = self.training_collection.peek(limit=limit)
            
            examples = []
            if results and results['metadatas']:
                for i, meta in enumerate(results['metadatas']):
                    examples.append({
                        'type': 'training',
                        'content': meta.get('response', '')[:100],
                        'context': meta.get('context', '')[:100],
                        'source': meta.get('source', 'unknown'),
                        'timestamp': meta.get('timestamp', datetime.now().isoformat())
                    })
            
            return examples
        except Exception as e:
            print(f"Error getting examples: {e}")
            return []
    
    def clear_training_data(self) -> None:
        """Clear all training data (use with caution!)."""
        self.client.delete_collection("training_conversations")
        self.training_collection = self.client.get_or_create_collection(
            name="training_conversations",
            metadata={"description": "Conversation examples for few-shot learning"}
        )


# Singleton instance
_memory_service = None

def get_memory_service() -> MemoryService:
    """Get the singleton memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
