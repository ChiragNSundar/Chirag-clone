"""
Memory Search Service - Full-text search across all memories and knowledge.
"""
from typing import List, Dict, Optional
from datetime import datetime
import re

from .memory_service import get_memory_service
from .logger import get_logger

logger = get_logger(__name__)


class MemorySearchService:
    """Service for searching across all stored memories."""
    
    def __init__(self):
        self.memory = get_memory_service()
    
    def search(
        self,
        query: str,
        limit: int = 20,
        collection: Optional[str] = None,
        include_metadata: bool = True
    ) -> Dict:
        """
        Search across all memory collections.
        
        Args:
            query: Search query
            limit: Maximum results
            collection: Optional collection filter ('training', 'conversations', 'documents')
            include_metadata: Whether to include metadata
            
        Returns:
            Dict with results grouped by collection
        """
        if not query or len(query.strip()) < 2:
            return {'error': 'Query too short', 'results': []}
        
        results = {
            'query': query,
            'total': 0,
            'results': [],
            'collections': {}
        }
        
        try:
            # Search training examples
            if not collection or collection == 'training':
                training_results = self._search_collection(
                    'training_examples',
                    query,
                    limit
                )
                results['collections']['training'] = training_results
                results['total'] += len(training_results)
                results['results'].extend(training_results)
            
            # Search conversation history
            if not collection or collection == 'conversations':
                conv_results = self._search_collection(
                    'conversations',
                    query,
                    limit
                )
                results['collections']['conversations'] = conv_results
                results['total'] += len(conv_results)
                results['results'].extend(conv_results)
            
            # Search documents/knowledge
            if not collection or collection == 'documents':
                doc_results = self._search_collection(
                    'documents',
                    query,
                    limit
                )
                results['collections']['documents'] = doc_results
                results['total'] += len(doc_results)
                results['results'].extend(doc_results)
            
            # Sort by relevance score
            results['results'].sort(key=lambda x: x.get('score', 0), reverse=True)
            results['results'] = results['results'][:limit]
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            results['error'] = str(e)
        
        return results
    
    def _search_collection(
        self,
        collection_name: str,
        query: str,
        limit: int
    ) -> List[Dict]:
        """Search a specific collection."""
        try:
            # Use ChromaDB's query functionality
            collection = self.memory.client.get_or_create_collection(
                name=collection_name
            )
            
            results = collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            items = []
            if results and results.get('documents'):
                docs = results['documents'][0] if results['documents'] else []
                ids = results['ids'][0] if results.get('ids') else []
                distances = results['distances'][0] if results.get('distances') else []
                metadatas = results['metadatas'][0] if results.get('metadatas') else []
                
                for i, doc in enumerate(docs):
                    # Convert distance to score (lower distance = higher score)
                    score = 1 / (1 + distances[i]) if i < len(distances) else 0.5
                    
                    items.append({
                        'id': ids[i] if i < len(ids) else f"{collection_name}_{i}",
                        'content': doc,
                        'collection': collection_name,
                        'score': round(score, 3),
                        'metadata': metadatas[i] if i < len(metadatas) else {},
                        'preview': doc[:200] + '...' if len(doc) > 200 else doc
                    })
            
            return items
            
        except Exception as e:
            logger.error(f"Collection search error ({collection_name}): {e}")
            return []
    
    def search_by_date(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Search memories by date range."""
        # This would require date metadata in collections
        # Placeholder for now
        return []
    
    def search_by_topic(self, topic: str, limit: int = 20) -> List[Dict]:
        """Search for memories related to a specific topic."""
        return self.search(topic, limit)
    
    def get_recent_memories(self, limit: int = 20) -> List[Dict]:
        """Get most recent memories across all collections."""
        # Get recent from each collection
        results = []
        
        for collection_name in ['training_examples', 'conversations', 'documents']:
            try:
                collection = self.memory.client.get_or_create_collection(
                    name=collection_name
                )
                
                # Get all and sort by time (if available)
                all_items = collection.get(
                    limit=limit,
                    include=['documents', 'metadatas']
                )
                
                if all_items and all_items.get('documents'):
                    for i, doc in enumerate(all_items['documents']):
                        metadata = all_items['metadatas'][i] if all_items.get('metadatas') else {}
                        results.append({
                            'content': doc,
                            'collection': collection_name,
                            'metadata': metadata,
                            'preview': doc[:200] + '...' if len(doc) > 200 else doc
                        })
            except:
                pass
        
        return results[:limit]
    
    def get_memory_stats(self) -> Dict:
        """Get statistics about stored memories."""
        stats = {
            'collections': {},
            'total_memories': 0
        }
        
        for collection_name in ['training_examples', 'conversations', 'documents']:
            try:
                collection = self.memory.client.get_or_create_collection(
                    name=collection_name
                )
                count = collection.count()
                stats['collections'][collection_name] = count
                stats['total_memories'] += count
            except:
                stats['collections'][collection_name] = 0
        
        return stats


# Singleton instance
_memory_search_service: Optional[MemorySearchService] = None


def get_memory_search_service() -> MemorySearchService:
    """Get the singleton memory search service instance."""
    global _memory_search_service
    if _memory_search_service is None:
        _memory_search_service = MemorySearchService()
    return _memory_search_service
