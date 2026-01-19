"""
Knowledge Routes - Knowledge base management, document indexing, and querying.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ============= Request Models =============

class KnowledgeTextRequest(BaseModel):
    content: str
    title: str = "Quick Note"
    category: str = "general"

class KnowledgeUrlRequest(BaseModel):
    url: str
    category: str = "general"

class KnowledgeQueryRequest(BaseModel):
    query: str
    n_results: int = 5
    category: Optional[str] = None


# ============= Helper Functions =============

def _get_knowledge_service():
    from services.knowledge_service import get_knowledge_service
    return get_knowledge_service()


# ============= Document Management =============

@router.get("/documents")
async def list_knowledge_documents():
    """List all indexed knowledge documents."""
    try:
        service = _get_knowledge_service()
        documents = service.list_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error(f"List documents error: {e}")
        return {"documents": []}


@router.get("/stats")
async def get_knowledge_stats():
    """Get knowledge base statistics."""
    try:
        service = _get_knowledge_service()
        stats = service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Knowledge stats error: {e}")
        return {"total_documents": 0, "total_chunks": 0}


@router.post("/upload")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    category: str = Form("general"),
    title: Optional[str] = Form(None)
):
    """Upload a document to the knowledge base."""
    try:
        content = await file.read()
        filename = file.filename or "document"
        doc_title = title or filename
        
        text_content = ""
        
        if filename.lower().endswith('.pdf'):
            try:
                import fitz  # PyMuPDF
                pdf_doc = fitz.open(stream=content, filetype="pdf")
                for page in pdf_doc:
                    text_content += page.get_text()
                pdf_doc.close()
            except Exception as e:
                logger.error(f"PDF parsing error: {e}")
                raise HTTPException(status_code=400, detail="Failed to parse PDF")
        elif filename.lower().endswith(('.txt', '.md', '.json', '.csv')):
            text_content = content.decode('utf-8', errors='replace')
        else:
            # Try to decode as text
            try:
                text_content = content.decode('utf-8', errors='replace')
            except:
                raise HTTPException(status_code=400, detail="Unsupported file format")
        
        if not text_content.strip():
            raise HTTPException(status_code=400, detail="Document is empty")
        
        service = _get_knowledge_service()
        doc_id = await asyncio.to_thread(
            service.add_document,
            text_content,
            title=doc_title,
            category=category
        )
        
        return {
            "success": True,
            "doc_id": doc_id,
            "title": doc_title,
            "category": category,
            "characters": len(text_content)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Knowledge upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-text")
async def add_knowledge_text(request: KnowledgeTextRequest):
    """Add text content directly to knowledge base."""
    try:
        service = _get_knowledge_service()
        doc_id = await asyncio.to_thread(
            service.add_document,
            request.content,
            title=request.title,
            category=request.category
        )
        
        return {
            "success": True,
            "doc_id": doc_id,
            "title": request.title,
            "category": request.category
        }
    except Exception as e:
        logger.error(f"Add knowledge text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-url")
async def add_knowledge_from_url(request: KnowledgeUrlRequest):
    """Fetch and add content from a URL to knowledge base."""
    try:
        import aiohttp
        
        # Fetch URL content
        async with aiohttp.ClientSession() as session:
            async with session.get(request.url, timeout=30) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {response.status}")
                html_content = await response.text()
        
        # Extract text from HTML
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            text_content = soup.get_text(separator='\n', strip=True)
        except ImportError:
            # Fallback: basic HTML stripping
            import re
            text_content = re.sub(r'<[^>]+>', '', html_content)
        
        if not text_content.strip():
            raise HTTPException(status_code=400, detail="No content extracted from URL")
        
        # Get title from URL or page
        title = request.url.split('/')[-1] or "Web Page"
        
        service = _get_knowledge_service()
        doc_id = await asyncio.to_thread(
            service.add_document,
            text_content[:50000],  # Limit content size
            title=title,
            category=request.category,
            source_url=request.url
        )
        
        return {
            "success": True,
            "doc_id": doc_id,
            "title": title,
            "category": request.category,
            "characters": len(text_content[:50000])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add URL knowledge error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Querying =============

@router.post("/query")
async def query_knowledge_base(request: KnowledgeQueryRequest):
    """Query the knowledge base for relevant content."""
    try:
        service = _get_knowledge_service()
        results = await asyncio.to_thread(
            service.query,
            request.query,
            n_results=request.n_results,
            category=request.category
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"Knowledge query error: {e}")
        return {"results": []}


@router.get("/search")
async def search_memories(query: str, limit: int = 20, collection: Optional[str] = None):
    """Search across all memories."""
    try:
        from services.memory_service import get_memory_service
        memory = get_memory_service()
        results = memory.search(query, limit=limit, collection=collection)
        return {"results": results}
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        return {"results": []}


@router.get("/memory-stats")
async def get_memory_stats():
    """Get memory statistics."""
    try:
        from services.memory_service import get_memory_service
        memory = get_memory_service()
        return memory.get_stats()
    except Exception as e:
        logger.error(f"Memory stats error: {e}")
        return {}


# ============= Document Management =============

@router.delete("/documents/{doc_id}")
async def delete_knowledge_document(doc_id: str):
    """Delete a document from the knowledge base."""
    try:
        service = _get_knowledge_service()
        success = await asyncio.to_thread(service.delete_document, doc_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        return {"success": False, "error": str(e)}
