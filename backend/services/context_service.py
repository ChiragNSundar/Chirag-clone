"""
Context Service - Offline RAG using local context files.
Auto-loads .txt/.md/.json files from the context directory,
chunks them, indexes with BM25, and provides relevant context
for chat responses — even when LM Studio is not running.
"""
import os
import re
import json
import hashlib
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field

from config import Config
from services.logger import get_logger
from services.hybrid_rag import BM25, SearchResult

logger = get_logger(__name__)


@dataclass
class ContextChunk:
    """A single chunk of context from a file."""
    id: str
    content: str
    source_file: str
    section: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextService:
    """
    Service for loading and querying local context files.
    
    Auto-loads files from CONTEXT_FILES_DIR on startup:
    - .txt files: split by sections (=== headers or blank-line separated)
    - .md files: split by ## headers
    - .json files: each top-level key/item becomes a chunk
    
    Provides BM25 keyword search + optional semantic search for retrieval.
    """
    
    CHUNK_MAX_WORDS = 500  # Max words per chunk
    CHUNK_OVERLAP_WORDS = 50  # Word overlap between chunks
    
    def __init__(self):
        self._chunks: List[ContextChunk] = []
        self._bm25 = BM25()
        self._indexed = False
        self._file_hashes: Dict[str, str] = {}
        self._embedding_model = None
        self._chunk_embeddings: List[List[float]] = []
        
        # Auto-load on init
        self.reload()
    
    def reload(self):
        """Reload all context files from the configured directory."""
        context_dir = Config.CONTEXT_FILES_DIR
        
        if not os.path.exists(context_dir):
            logger.info(f"Context directory not found: {context_dir}. Creating it.")
            os.makedirs(context_dir, exist_ok=True)
            return
        
        new_chunks = []
        new_hashes = {}
        
        for filename in sorted(os.listdir(context_dir)):
            filepath = os.path.join(context_dir, filename)
            if not os.path.isfile(filepath):
                continue
            
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ('.txt', '.md', '.json'):
                continue
            
            try:
                # Check if file changed
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                file_hash = hashlib.md5(content.encode()).hexdigest()
                new_hashes[filename] = file_hash
                
                # Parse file into chunks
                if ext == '.txt':
                    chunks = self._parse_txt(content, filename)
                elif ext == '.md':
                    chunks = self._parse_md(content, filename)
                elif ext == '.json':
                    chunks = self._parse_json(content, filename)
                else:
                    continue
                
                new_chunks.extend(chunks)
                logger.info(f"📄 Loaded context: {filename} ({len(chunks)} chunks)")
                
            except Exception as e:
                logger.error(f"Error loading context file {filename}: {e}")
        
        self._chunks = new_chunks
        self._file_hashes = new_hashes
        
        # Build BM25 index
        if self._chunks:
            documents = [
                {"id": c.id, "content": c.content, "metadata": c.metadata}
                for c in self._chunks
            ]
            self._bm25.index(documents, content_field="content")
            self._indexed = True
            logger.info(f"✅ Context indexed: {len(self._chunks)} chunks from {len(new_hashes)} files")
        else:
            self._indexed = False
            logger.info("No context files loaded")
    
    def _parse_txt(self, content: str, filename: str) -> List[ContextChunk]:
        """Parse a .txt file into chunks. Splits by section headers or paragraph groups."""
        chunks = []
        
        # Try splitting by ===== section headers (like chiragcontext.txt)
        sections = re.split(r'\n={3,}\n', content)
        
        if len(sections) > 1:
            # Has section headers
            current_section = ""
            for i, section in enumerate(sections):
                section = section.strip()
                if not section:
                    continue
                
                # First line of section might be the title
                lines = section.split('\n')
                section_title = ""
                section_body = section
                
                if lines and len(lines[0]) < 100 and not lines[0].startswith('-'):
                    section_title = lines[0].strip().rstrip('.')
                    section_body = '\n'.join(lines[1:]).strip()
                
                # Split long sections into smaller chunks
                sub_chunks = self._split_into_chunks(section_body, self.CHUNK_MAX_WORDS)
                
                for j, sub in enumerate(sub_chunks):
                    chunk_id = f"{filename}:s{i}:c{j}"
                    chunks.append(ContextChunk(
                        id=chunk_id,
                        content=sub,
                        source_file=filename,
                        section=section_title,
                        metadata={"file": filename, "section": section_title, "chunk": j}
                    ))
        else:
            # No section headers — split by paragraphs
            paragraphs = re.split(r'\n\s*\n', content)
            text_buffer = ""
            chunk_idx = 0
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                text_buffer += para + "\n\n"
                
                if len(text_buffer.split()) >= self.CHUNK_MAX_WORDS:
                    chunks.append(ContextChunk(
                        id=f"{filename}:c{chunk_idx}",
                        content=text_buffer.strip(),
                        source_file=filename,
                        metadata={"file": filename, "chunk": chunk_idx}
                    ))
                    chunk_idx += 1
                    text_buffer = ""
            
            # Remaining
            if text_buffer.strip():
                chunks.append(ContextChunk(
                    id=f"{filename}:c{chunk_idx}",
                    content=text_buffer.strip(),
                    source_file=filename,
                    metadata={"file": filename, "chunk": chunk_idx}
                ))
        
        return chunks
    
    def _parse_md(self, content: str, filename: str) -> List[ContextChunk]:
        """Parse a .md file into chunks. Splits by ## headers."""
        chunks = []
        
        # Split by ## headers (h2 and below)
        sections = re.split(r'\n(?=#{1,3}\s)', content)
        
        for i, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue
            
            # Extract header
            header_match = re.match(r'^#{1,3}\s+(.+)', section)
            section_title = header_match.group(1).strip() if header_match else ""
            
            # Split long sections
            sub_chunks = self._split_into_chunks(section, self.CHUNK_MAX_WORDS)
            
            for j, sub in enumerate(sub_chunks):
                chunks.append(ContextChunk(
                    id=f"{filename}:s{i}:c{j}",
                    content=sub,
                    source_file=filename,
                    section=section_title,
                    metadata={"file": filename, "section": section_title, "chunk": j}
                ))
        
        return chunks
    
    def _parse_json(self, content: str, filename: str) -> List[ContextChunk]:
        """Parse a .json file into chunks. Each top-level key becomes a chunk."""
        chunks = []
        
        try:
            data = json.loads(content)
            
            if isinstance(data, dict):
                for i, (key, value) in enumerate(data.items()):
                    text = f"{key}: {json.dumps(value, indent=2)}" if not isinstance(value, str) else f"{key}: {value}"
                    chunks.append(ContextChunk(
                        id=f"{filename}:k{i}",
                        content=text,
                        source_file=filename,
                        section=key,
                        metadata={"file": filename, "key": key}
                    ))
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    text = json.dumps(item, indent=2) if not isinstance(item, str) else item
                    chunks.append(ContextChunk(
                        id=f"{filename}:i{i}",
                        content=text,
                        source_file=filename,
                        metadata={"file": filename, "index": i}
                    ))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filename}: {e}")
        
        return chunks
    
    def _split_into_chunks(self, text: str, max_words: int) -> List[str]:
        """Split text into chunks of max_words with overlap."""
        words = text.split()
        if len(words) <= max_words:
            return [text]
        
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + max_words, len(words))
            chunk = ' '.join(words[start:end])
            chunks.append(chunk)
            start = end - self.CHUNK_OVERLAP_WORDS  # Overlap
            if start >= len(words) - self.CHUNK_OVERLAP_WORDS:
                break
        
        return chunks
    
    def get_relevant_context(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0
    ) -> List[str]:
        """
        Get relevant context chunks for a query.
        
        Uses BM25 keyword search. Returns the text content
        of the most relevant chunks.
        
        Args:
            query: The search query
            top_k: Number of results to return
            min_score: Minimum relevance score
            
        Returns:
            List of context strings, most relevant first
        """
        if not self._indexed or not self._chunks:
            return []
        
        results = self._bm25.search(query, top_k=top_k)
        
        # Filter by score
        if min_score > 0:
            results = [r for r in results if r.score >= min_score]
        
        return [r.content for r in results]
    
    def get_all_context_summary(self) -> str:
        """Get a summary of all loaded context files."""
        if not self._chunks:
            return "No context files loaded."
        
        file_chunks = {}
        for chunk in self._chunks:
            fname = chunk.source_file
            if fname not in file_chunks:
                file_chunks[fname] = 0
            file_chunks[fname] += 1
        
        summary_lines = ["Loaded context files:"]
        for fname, count in file_chunks.items():
            summary_lines.append(f"  - {fname}: {count} chunks")
        summary_lines.append(f"Total: {len(self._chunks)} chunks from {len(file_chunks)} files")
        
        return "\n".join(summary_lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded context."""
        file_stats = {}
        total_words = 0
        
        for chunk in self._chunks:
            fname = chunk.source_file
            words = len(chunk.content.split())
            total_words += words
            
            if fname not in file_stats:
                file_stats[fname] = {"chunks": 0, "words": 0, "sections": set()}
            file_stats[fname]["chunks"] += 1
            file_stats[fname]["words"] += words
            if chunk.section:
                file_stats[fname]["sections"].add(chunk.section)
        
        # Convert sets to lists for JSON serialization
        for fname in file_stats:
            file_stats[fname]["sections"] = list(file_stats[fname]["sections"])
        
        return {
            "total_files": len(file_stats),
            "total_chunks": len(self._chunks),
            "total_words": total_words,
            "files": file_stats,
            "indexed": self._indexed
        }


# Singleton
_context_service = None


def get_context_service() -> ContextService:
    """Get the singleton context service instance."""
    global _context_service
    if _context_service is None:
        _context_service = ContextService()
    return _context_service
