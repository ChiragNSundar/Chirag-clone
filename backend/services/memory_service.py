"""
Memory Service - Vector database operations using ChromaDB for conversation memory.
"""
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("[WARNING] ChromaDB not found. Using in-memory mock service.")

from typing import List, Dict, Optional, Tuple
import json
import hashlib
from datetime import datetime
from config import Config
from backend.database import engine, TrainingExample
from sqlmodel import Session, select
from services.logger import get_logger

logger = get_logger(__name__)


class MockCollection:
    def __init__(self, name):
        self.name = name
        self.data = {}  # id -> {document, metadata}
        
    def add(self, documents, ids, metadatas=None):
        for i, doc_id in enumerate(ids):
            self.data[doc_id] = {
                "document": documents[i],
                "metadata": metadatas[i] if metadatas else {}
            }
            
    def update(self, documents, ids, metadatas=None):
        self.add(documents, ids, metadatas)
        
    def query(self, query_texts, n_results=5):
        # fast simple keyword match for mock
        results = {"ids": [], "documents": [], "metadatas": []}
        q = query_texts[0].lower()
        
        matches = []
        for doc_id, item in self.data.items():
            if q in item["document"].lower():
                matches.append(item)
                
        # Limit results
        matches = matches[:n_results]
        
        results["metadatas"] = [[m["metadata"] for m in matches]]
        results["documents"] = [[m["document"] for m in matches]]
        return results

    def get(self, where=None, limit=None):
        # Simple mock implementation
        results = {"ids": [], "documents": [], "metadatas": []}
        items = list(self.data.items())
        if limit:
            items = items[:limit]
            
        for doc_id, item in items:
            results["ids"].append(doc_id)
            results["documents"].append(item["document"])
            results["metadatas"].append(item["metadata"])
            
        return results
        
    def count(self):
        return len(self.data)
        
    def peek(self, limit=10):
        return self.get(limit=limit)


class MemoryService:
    """Service for managing conversation memory using ChromaDB."""
    
    def __init__(self):
        if CHROMA_AVAILABLE:
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
        else:
            self.client = None
            self.training_collection = MockCollection("training_conversations")
            self.conversation_collection = MockCollection("conversations")
            
        # Migrate data if needed
        self._migrate_chroma_to_sql()
    
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
        
        # Save to SQLite (Source of Truth)
        try:
            with Session(engine) as session:
                example = TrainingExample(
                    context=context,
                    response=response,
                    source=source,
                    chroma_id=doc_id,
                    timestamp=datetime.now()
                )
                session.add(example)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to save to SQLite: {e}")

        # Save to ChromaDB (Search Index)
        try:
            self.training_collection.add(
                documents=[full_text],
                ids=[doc_id],
                metadatas=[meta]
            )
        except Exception as e:
            logger.error(f"ChromaDB insert error: {e}")
            # Might already exist, try update
            if hasattr(self.training_collection, 'update'):
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
        """Add multiple training examples at once."""
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
        """Find similar training examples for few-shot learning."""
        try:
            results = self.training_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            examples = []
            if results and results.get('metadatas'):
                # Handle mock vs real structure differences if needed
                metas = results['metadatas'][0] if isinstance(results['metadatas'], list) and len(results['metadatas']) > 0 and isinstance(results['metadatas'][0], list) else results['metadatas']
                
                # Mock returns a single list sometimes depending on implementation, real returns list of lists
                if isinstance(metas, list) and len(metas) > 0 and isinstance(metas[0], list):
                     metas = metas[0]

                for meta in metas:
                    if isinstance(meta, dict):
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
        """Add a message to conversation history."""
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
        """Get recent conversation history for a session."""
        try:
            results = self.conversation_collection.get(
                where={"session_id": session_id},
                limit=limit
            )
            
            messages = []
            if results and results.get('metadatas'):
                documents = results['documents']
                metadatas = results['metadatas']
                
                # Handling structure differences
                if isinstance(documents, list) and len(documents) > 0 and isinstance(documents[0], list):
                     documents = documents[0]
                if isinstance(metadatas, list) and len(metadatas) > 0 and isinstance(metadatas[0], list):
                     metadatas = metadatas[0]

                for i, meta in enumerate(metadatas):
                    if i < len(documents):
                         messages.append({
                             'role': meta.get('role', 'user'),
                             'content': documents[i],
                             'timestamp': meta.get('timestamp', '')
                         })
            
            # Sort by timestamp
            messages.sort(key=lambda x: x.get('timestamp', ''))
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
            
            if sample and sample.get('metadatas'):
                metadatas = sample['metadatas']
                if isinstance(metadatas, list) and len(metadatas) > 0 and isinstance(metadatas[0], list):
                     metadatas = metadatas[0]

                for meta in metadatas:
                    source = meta.get('source', 'unknown')
                    sources[source] = sources.get(source, 0) + 1
            
            return {
                'total_examples': count,
                'sources': sources
            }
        except Exception as e:
            return {'total_examples': 0, 'sources': {}}
    
    def get_all_examples_with_metadata(self, limit: int = 500) -> List[Dict]:
        """Get all training examples with full metadata for timeline."""
        try:
            results = self.training_collection.peek(limit=limit)
            
            examples = []
            if results and results.get('metadatas'):
                metadatas = results['metadatas']
                if isinstance(metadatas, list) and len(metadatas) > 0 and isinstance(metadatas[0], list):
                     metadatas = metadatas[0]

                for i, meta in enumerate(metadatas):
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
    
    def export_all_training_examples(self) -> List[Dict]:
        """Export ALL training examples with full metadata for backup/export.
        
        Returns complete data without truncation for ML training purposes.
        """
        try:
            # Get total count first
            total = self.training_collection.count()
            if total == 0:
                return []
            
            # Retrieve all examples (in batches if needed for large datasets)
            results = self.training_collection.peek(limit=max(total, 1000))
            
            examples = []
            if results and results.get('metadatas'):
                metadatas = results['metadatas']
                documents = results.get('documents', [])
                ids = results.get('ids', [])
                
                # Handle nested list structure
                if isinstance(metadatas, list) and len(metadatas) > 0 and isinstance(metadatas[0], list):
                    metadatas = metadatas[0]
                if isinstance(documents, list) and len(documents) > 0 and isinstance(documents[0], list):
                    documents = documents[0]
                if isinstance(ids, list) and len(ids) > 0 and isinstance(ids[0], list):
                    ids = ids[0]
                
                for i, meta in enumerate(metadatas):
                    example = {
                        'id': ids[i] if i < len(ids) else None,
                        'context': meta.get('context', ''),
                        'response': meta.get('response', ''),
                        'source': meta.get('source', 'unknown'),
                        'timestamp': meta.get('timestamp', ''),
                        'full_document': documents[i] if i < len(documents) else ''
                    }
                    examples.append(example)
            
            return examples
        except Exception as e:
            print(f"Error exporting training examples: {e}")
            return []
    
    def import_training_examples(self, examples: List[Dict], clear_existing: bool = False) -> int:
        """Import training examples from export data.
        
        Args:
            examples: List of training example dicts with context, response, source, timestamp
            clear_existing: If True, clears existing data before import
            
        Returns:
            Number of examples successfully imported
        """
        if clear_existing:
            self.clear_training_data()
        
        if not examples:
            return 0
        
        imported = 0
        for ex in examples:
            try:
                context = ex.get('context', '')
                response = ex.get('response', '')
                source = ex.get('source', 'import')
                timestamp = ex.get('timestamp', datetime.now().isoformat())
                
                if context and response:
                    self.add_training_example(
                        context=context,
                        response=response,
                        source=source,
                        metadata={'original_timestamp': timestamp}
                    )
                    imported += 1
            except Exception as e:
                print(f"Error importing example: {e}")
                continue
        
        return imported
    
    def _migrate_chroma_to_sql(self):
        """Migrate existing ChromaDB data to SQLite if SQLite is empty."""
        try:
            with Session(engine) as session:
                count = session.query(TrainingExample).count()
                if count > 0:
                    return  # Already has data
            
            logger.info("Migrating data from ChromaDB to SQLite...")
            examples = self.export_all_training_examples()
            
            with Session(engine) as session:
                for ex in examples:
                    # Parse timestamp format if needed, simplistic approach:
                    ts = datetime.now()
                    try:
                        if ex.get('timestamp'):
                            ts = datetime.fromisoformat(ex['timestamp'])
                    except:
                        pass
                        
                    db_ex = TrainingExample(
                        context=ex.get('context', ''),
                        response=ex.get('response', ''),
                        source=ex.get('source', 'unknown'),
                        chroma_id=ex.get('id'),
                        timestamp=ts
                    )
                    session.add(db_ex)
                session.commit()
            logger.info(f"Migration complete: {len(examples)} records migrated.")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")

    def clear_training_data(self) -> None:
        """Clear all training data (use with caution!)."""
        # Clear SQLite
        try:
            with Session(engine) as session:
                session.query(TrainingExample).delete()
                session.commit()
        except Exception as e:
            logger.error(f"Failed to clear SQLite: {e}")

        if CHROMA_AVAILABLE:
            self.client.delete_collection("training_conversations")
            self.training_collection = self.client.get_or_create_collection(
                name="training_conversations",
                metadata={"description": "Conversation examples for few-shot learning"}
            )
        else:
            self.training_collection = MockCollection("training_conversations")


# Singleton instance
_memory_service = None

def get_memory_service() -> MemoryService:
    """Get the singleton memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service

# Singleton instance
_memory_service = None

def get_memory_service() -> MemoryService:
    """Get the singleton memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
