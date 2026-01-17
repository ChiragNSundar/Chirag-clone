"""
Hybrid RAG Search - Combines semantic (vector) and keyword (BM25) search.
Uses reciprocal rank fusion to merge results for better retrieval.
"""
import math
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from services.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """A single search result."""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # 'semantic', 'keyword', or 'hybrid'


@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search."""
    semantic_weight: float = 0.5  # Weight for semantic search (0-1)
    keyword_weight: float = 0.5   # Weight for keyword search (0-1)
    top_k: int = 10               # Number of results to return
    rrf_k: int = 60               # RRF constant (higher = more emphasis on top ranks)
    min_score: float = 0.0        # Minimum score threshold


class BM25:
    """
    BM25 (Best Match 25) keyword search implementation.
    A ranking function for information retrieval.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Args:
            k1: Term frequency saturation parameter
            b: Document length normalization parameter
        """
        self.k1 = k1
        self.b = b
        self._documents: List[Dict] = []
        self._doc_lengths: List[int] = []
        self._avg_doc_length: float = 0
        self._doc_freqs: Dict[str, int] = defaultdict(int)
        self._idf: Dict[str, float] = {}
        self._doc_term_freqs: List[Dict[str, int]] = []
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization (lowercase, split on non-alphanumeric)."""
        import re
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens
    
    def index(self, documents: List[Dict[str, Any]], content_field: str = "content"):
        """
        Index documents for BM25 search.
        
        Args:
            documents: List of documents with content
            content_field: Field containing the text content
        """
        self._documents = documents
        self._doc_term_freqs = []
        self._doc_lengths = []
        self._doc_freqs = defaultdict(int)
        
        for doc in documents:
            content = doc.get(content_field, "")
            tokens = self._tokenize(content)
            
            # Count term frequencies in this document
            term_freqs = defaultdict(int)
            for token in tokens:
                term_freqs[token] += 1
            
            self._doc_term_freqs.append(dict(term_freqs))
            self._doc_lengths.append(len(tokens))
            
            # Count document frequencies
            for term in set(tokens):
                self._doc_freqs[term] += 1
        
        # Calculate average document length
        if self._doc_lengths:
            self._avg_doc_length = sum(self._doc_lengths) / len(self._doc_lengths)
        
        # Pre-compute IDF for all terms
        n_docs = len(documents)
        for term, df in self._doc_freqs.items():
            self._idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
        
        logger.info(f"BM25 indexed {len(documents)} documents, {len(self._doc_freqs)} unique terms")
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        Search for documents matching the query.
        
        Returns:
            List of SearchResult sorted by score
        """
        if not self._documents:
            return []
        
        query_tokens = self._tokenize(query)
        scores = []
        
        for i, doc in enumerate(self._documents):
            score = 0.0
            doc_length = self._doc_lengths[i]
            term_freqs = self._doc_term_freqs[i]
            
            for term in query_tokens:
                if term not in self._idf:
                    continue
                
                tf = term_freqs.get(term, 0)
                idf = self._idf[term]
                
                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self._avg_doc_length)
                score += idf * numerator / denominator
            
            if score > 0:
                scores.append((i, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for i, score in scores[:top_k]:
            doc = self._documents[i]
            results.append(SearchResult(
                id=doc.get("id", str(i)),
                content=doc.get("content", ""),
                score=score,
                metadata=doc.get("metadata", {}),
                source="keyword"
            ))
        
        return results


class HybridSearch:
    """
    Hybrid search combining semantic and keyword search.
    Uses Reciprocal Rank Fusion (RRF) to merge results.
    """
    
    def __init__(
        self,
        semantic_search_fn: callable,
        config: Optional[HybridSearchConfig] = None
    ):
        """
        Args:
            semantic_search_fn: Function that takes (query, top_k) and returns List[SearchResult]
            config: Search configuration
        """
        self.semantic_search = semantic_search_fn
        self.config = config or HybridSearchConfig()
        self.bm25 = BM25()
        self._indexed = False
    
    def index(self, documents: List[Dict[str, Any]], content_field: str = "content"):
        """Index documents for keyword search."""
        self.bm25.index(documents, content_field)
        self._indexed = True
    
    def _reciprocal_rank_fusion(
        self,
        result_lists: List[List[SearchResult]],
        weights: List[float]
    ) -> List[SearchResult]:
        """
        Merge multiple result lists using Reciprocal Rank Fusion.
        
        RRF score = sum(weight_i / (k + rank_i)) for each result list
        """
        k = self.config.rrf_k
        fused_scores: Dict[str, float] = defaultdict(float)
        result_by_id: Dict[str, SearchResult] = {}
        
        for results, weight in zip(result_lists, weights):
            for rank, result in enumerate(results, start=1):
                fused_scores[result.id] += weight / (k + rank)
                
                # Keep the result with highest individual score
                if result.id not in result_by_id or result.score > result_by_id[result.id].score:
                    result_by_id[result.id] = result
        
        # Sort by fused score
        sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
        
        # Build final results
        results = []
        for id_ in sorted_ids[:self.config.top_k]:
            result = result_by_id[id_]
            results.append(SearchResult(
                id=result.id,
                content=result.content,
                score=fused_scores[id_],
                metadata=result.metadata,
                source="hybrid"
            ))
        
        return results
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        semantic_only: bool = False,
        keyword_only: bool = False
    ) -> List[SearchResult]:
        """
        Perform hybrid search.
        
        Args:
            query: Search query
            top_k: Override default top_k
            semantic_only: Use only semantic search
            keyword_only: Use only keyword search
        
        Returns:
            List of SearchResult sorted by relevance
        """
        k = top_k or self.config.top_k
        
        if keyword_only:
            return self.bm25.search(query, k)
        
        if semantic_only:
            return self.semantic_search(query, k)
        
        # Perform both searches
        # Fetch more results than needed so RRF has enough to work with
        semantic_results = self.semantic_search(query, k * 2)
        keyword_results = self.bm25.search(query, k * 2) if self._indexed else []
        
        # If keyword search has no results, fall back to semantic only
        if not keyword_results:
            return semantic_results[:k]
        
        # Fuse results
        weights = [self.config.semantic_weight, self.config.keyword_weight]
        fused = self._reciprocal_rank_fusion(
            [semantic_results, keyword_results],
            weights
        )
        
        return fused[:k]


# ============= Reranker =============

class SimpleReranker:
    """
    Simple reranker using keyword overlap scoring.
    For production, use a proper reranker model like BGE-Reranker.
    """
    
    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 5
    ) -> List[SearchResult]:
        """
        Rerank results based on query-result similarity.
        
        This is a simple implementation. For better results, use:
        - sentence-transformers cross-encoders
        - Cohere rerank API
        - BGE-Reranker
        """
        if not results:
            return []
        
        query_tokens = set(query.lower().split())
        scored = []
        
        for result in results:
            content_tokens = set(result.content.lower().split()[:200])
            
            # Jaccard similarity
            intersection = len(query_tokens & content_tokens)
            union = len(query_tokens | content_tokens)
            jaccard = intersection / union if union > 0 else 0
            
            # Combine with original score
            combined_score = 0.7 * result.score + 0.3 * jaccard
            
            scored.append((result, combined_score))
        
        # Sort by combined score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        reranked = []
        for result, score in scored[:top_k]:
            reranked.append(SearchResult(
                id=result.id,
                content=result.content,
                score=score,
                metadata=result.metadata,
                source=result.source
            ))
        
        return reranked
