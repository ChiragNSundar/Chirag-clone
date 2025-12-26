"""
Knowledge Service - Document chunking and retrieval for RAG.
Stores documents in ChromaDB for semantic search.
"""
import os
import hashlib
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from config import Config

# PDF support - optional
try:
    import fitz  # PyMuPDF
    HAS_PDF_SUPPORT = True
except ImportError:
    HAS_PDF_SUPPORT = False
    print("PyMuPDF not installed. PDF support disabled. Install with: pip install PyMuPDF")


class KnowledgeService:
    """Service for managing document-based knowledge using ChromaDB."""
    
    # Chunking settings
    CHUNK_SIZE = 500  # Characters per chunk
    CHUNK_OVERLAP = 50  # Overlap between chunks
    
    def __init__(self):
        import chromadb
        from chromadb.config import Settings
        
        self.client = chromadb.PersistentClient(
            path=Config.CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Collection for knowledge documents
        self.collection = self.client.get_or_create_collection(
            name="knowledge_base",
            metadata={"description": "Personal knowledge documents for RAG"}
        )
        
        # Document metadata storage (JSON file)
        self.metadata_path = os.path.join(Config.DATA_DIR, "knowledge_metadata.json")
        self.documents = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load document metadata from JSON file."""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_metadata(self):
        """Save document metadata to JSON file."""
        os.makedirs(os.path.dirname(self.metadata_path), exist_ok=True)
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, indent=2, ensure_ascii=False)
    
    def _generate_doc_id(self, content: str, filename: str) -> str:
        """Generate a unique document ID."""
        return hashlib.md5(f"{filename}:{content[:100]}".encode()).hexdigest()[:12]
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        text = text.strip()
        
        while start < len(text):
            end = start + self.CHUNK_SIZE
            
            # Try to break at sentence or paragraph
            if end < len(text):
                # Look for paragraph break first
                para_break = text.rfind('\n\n', start, end)
                if para_break > start:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    for sep in ['. ', '! ', '? ', '\n']:
                        sep_pos = text.rfind(sep, start, end)
                        if sep_pos > start:
                            end = sep_pos + len(sep)
                            break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.CHUNK_OVERLAP
            if start < 0:
                start = end
        
        return chunks
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file."""
        if not HAS_PDF_SUPPORT:
            raise ValueError("PDF support not available. Install PyMuPDF.")
        
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n\n"
        doc.close()
        return text
    
    def _extract_text_from_file(self, file_path: str, doc_type: str) -> str:
        """Extract text from various file types."""
        if doc_type == 'pdf':
            return self._extract_text_from_pdf(file_path)
        else:  # txt, md, or other text files
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    
    def add_document(
        self,
        content: str,
        filename: str,
        doc_type: str = "txt",
        title: Optional[str] = None,
        category: str = "general"
    ) -> Dict:
        """
        Add a document to the knowledge base.
        
        Args:
            content: The text content of the document
            filename: Original filename
            doc_type: File type (txt, md, pdf)
            title: Optional title (defaults to filename)
            category: Category for organization (personal, work, etc.)
            
        Returns:
            Document metadata including ID and chunk count
        """
        doc_id = self._generate_doc_id(content, filename)
        chunks = self._chunk_text(content)
        
        if not chunks:
            raise ValueError("Document is empty or could not be chunked")
        
        # Add chunks to ChromaDB
        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{
            "doc_id": doc_id,
            "chunk_index": i,
            "filename": filename,
            "category": category,
            "timestamp": datetime.now().isoformat()
        } for i in range(len(chunks))]
        
        # Delete existing chunks if document is being updated
        self._delete_chunks(doc_id)
        
        self.collection.add(
            documents=chunks,
            ids=chunk_ids,
            metadatas=metadatas
        )
        
        # Store metadata
        doc_meta = {
            "id": doc_id,
            "filename": filename,
            "title": title or filename,
            "doc_type": doc_type,
            "category": category,
            "chunk_count": len(chunks),
            "char_count": len(content),
            "added_at": datetime.now().isoformat()
        }
        self.documents[doc_id] = doc_meta
        self._save_metadata()
        
        return doc_meta
    
    def add_document_from_file(
        self,
        file_path: str,
        title: Optional[str] = None,
        category: str = "general"
    ) -> Dict:
        """
        Add a document from a file path.
        
        Args:
            file_path: Path to the file
            title: Optional title
            category: Category for organization
            
        Returns:
            Document metadata
        """
        filename = os.path.basename(file_path)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'txt'
        
        content = self._extract_text_from_file(file_path, ext)
        return self.add_document(content, filename, ext, title, category)
    
    def _delete_chunks(self, doc_id: str):
        """Delete all chunks for a document."""
        try:
            # Get all chunk IDs for this document
            results = self.collection.get(
                where={"doc_id": doc_id}
            )
            if results and results['ids']:
                self.collection.delete(ids=results['ids'])
        except Exception as e:
            print(f"Error deleting chunks: {e}")
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the knowledge base.
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        if doc_id not in self.documents:
            return False
        
        self._delete_chunks(doc_id)
        del self.documents[doc_id]
        self._save_metadata()
        return True
    
    def list_documents(self) -> List[Dict]:
        """Get list of all indexed documents."""
        return list(self.documents.values())
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get metadata for a specific document."""
        return self.documents.get(doc_id)
    
    def query_knowledge(
        self,
        query: str,
        n_results: int = 3,
        category: Optional[str] = None
    ) -> List[Dict]:
        """
        Query the knowledge base for relevant chunks.
        
        Args:
            query: The search query
            n_results: Maximum number of chunks to return
            category: Optional category filter
            
        Returns:
            List of relevant chunks with metadata
        """
        try:
            where_filter = {"category": category} if category else None
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            
            chunks = []
            if results and results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if results.get('distances') else 0
                    
                    chunks.append({
                        'content': doc,
                        'filename': meta.get('filename', 'Unknown'),
                        'category': meta.get('category', 'general'),
                        'doc_id': meta.get('doc_id', ''),
                        'relevance': max(0, 1 - distance)  # Convert distance to relevance
                    })
            
            return chunks
            
        except Exception as e:
            print(f"Knowledge query error: {e}")
            return []
    
    def format_for_llm(self, chunks: List[Dict]) -> str:
        """
        Format retrieved chunks for injection into LLM prompt.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            Formatted string for system prompt
        """
        if not chunks:
            return ""
        
        formatted = "RELEVANT KNOWLEDGE FROM YOUR DOCUMENTS:\n"
        formatted += "-" * 40 + "\n"
        
        for i, chunk in enumerate(chunks, 1):
            formatted += f"[Source: {chunk['filename']}]\n"
            formatted += f"{chunk['content']}\n\n"
        
        formatted += "-" * 40 + "\n"
        formatted += "Use this knowledge naturally in your response if relevant.\n"
        
        return formatted
    
    def get_stats(self) -> Dict:
        """Get statistics about the knowledge base."""
        total_chunks = self.collection.count()
        total_docs = len(self.documents)
        total_chars = sum(doc.get('char_count', 0) for doc in self.documents.values())
        
        categories = {}
        for doc in self.documents.values():
            cat = doc.get('category', 'general')
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            'total_documents': total_docs,
            'total_chunks': total_chunks,
            'total_characters': total_chars,
            'categories': categories
        }


# Singleton instance
_knowledge_service = None

def get_knowledge_service() -> KnowledgeService:
    """Get the singleton knowledge service instance."""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
