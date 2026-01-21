"""
Notion Sync Service - Syncs Notion pages to knowledge base for RAG.
"""
import os
from datetime import datetime
from typing import List, Dict, Optional

from .logger import get_logger

logger = get_logger(__name__)

# Try to import Notion client
try:
    from notion_client import Client as NotionClient
    HAS_NOTION = True
except ImportError:
    HAS_NOTION = False
    logger.warning("notion-client not installed. Install with: pip install notion-client")


class NotionSyncService:
    """Service for syncing Notion pages to the knowledge base."""
    
    def __init__(self):
        self.api_key = os.getenv('NOTION_API_KEY', '')
        self.database_id = os.getenv('NOTION_DATABASE_ID', '')
        self.is_configured = bool(self.api_key and self.database_id)
        self.client = None
        self._last_sync = None
        
        if HAS_NOTION and self.is_configured:
            try:
                self.client = NotionClient(auth=self.api_key)
                logger.info("✅ Notion client initialized")
            except Exception as e:
                logger.error(f"Notion client init failed: {e}")
    
    def get_status(self) -> Dict:
        """Get service status."""
        return {
            'platform': 'notion',
            'has_library': HAS_NOTION,
            'configured': self.is_configured,
            'connected': self.client is not None,
            'last_sync': self._last_sync.isoformat() if self._last_sync else None
        }
    
    def _extract_text_from_block(self, block: Dict) -> str:
        """Extract plain text from a Notion block."""
        block_type = block.get('type', '')
        
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item', 'numbered_list_item', 'quote', 'callout']:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            return ''.join([t.get('plain_text', '') for t in rich_text])
        elif block_type == 'code':
            code_block = block.get('code', {})
            code_text = ''.join([t.get('plain_text', '') for t in code_block.get('rich_text', [])])
            language = code_block.get('language', 'text')
            return f"```{language}\n{code_text}\n```"
        elif block_type == 'divider':
            return '\n---\n'
        elif block_type == 'to_do':
            to_do = block.get('to_do', {})
            checked = '✓' if to_do.get('checked') else '○'
            text = ''.join([t.get('plain_text', '') for t in to_do.get('rich_text', [])])
            return f"{checked} {text}"
        
        return ''
    
    def _get_page_content(self, page_id: str) -> str:
        """Fetch all blocks from a Notion page and extract text."""
        if not self.client:
            return ''
        
        try:
            blocks = self.client.blocks.children.list(block_id=page_id)
            content_parts = []
            
            for block in blocks.get('results', []):
                text = self._extract_text_from_block(block)
                if text:
                    content_parts.append(text)
                
                # Handle nested blocks (children)
                if block.get('has_children'):
                    child_blocks = self.client.blocks.children.list(block_id=block['id'])
                    for child in child_blocks.get('results', []):
                        child_text = self._extract_text_from_block(child)
                        if child_text:
                            content_parts.append(f"  {child_text}")
            
            return '\n'.join(content_parts)
            
        except Exception as e:
            logger.error(f"Error fetching page {page_id}: {e}")
            return ''
    
    def _get_page_title(self, page: Dict) -> str:
        """Extract title from a Notion page."""
        properties = page.get('properties', {})
        
        # Try common title property names
        for prop_name in ['Name', 'Title', 'name', 'title']:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get('type') == 'title':
                    title_parts = prop.get('title', [])
                    return ''.join([t.get('plain_text', '') for t in title_parts])
        
        return 'Untitled'
    
    def fetch_pages(self, limit: int = 100) -> List[Dict]:
        """Fetch pages from the configured Notion database."""
        if not self.client or not self.database_id:
            return []
        
        try:
            results = self.client.databases.query(
                database_id=self.database_id,
                page_size=min(limit, 100)
            )
            
            pages = []
            for page in results.get('results', []):
                page_id = page['id']
                title = self._get_page_title(page)
                content = self._get_page_content(page_id)
                
                if content.strip():
                    pages.append({
                        'id': page_id,
                        'title': title,
                        'content': content,
                        'url': page.get('url', ''),
                        'last_edited': page.get('last_edited_time', '')
                    })
            
            return pages
            
        except Exception as e:
            logger.error(f"Error fetching Notion pages: {e}")
            return []
    
    def sync_to_knowledge_base(self) -> Dict:
        """Sync Notion pages to the knowledge service."""
        if not self.client:
            return {'success': False, 'error': 'Notion not configured'}
        
        try:
            from .knowledge_service import get_knowledge_service
            knowledge = get_knowledge_service()
            
            pages = self.fetch_pages()
            synced = 0
            errors = 0
            
            for page in pages:
                try:
                    knowledge.add_document(
                        content=page['content'],
                        filename=f"notion_{page['id'][:8]}.md",
                        doc_type='md',
                        title=page['title'],
                        category='notion'
                    )
                    synced += 1
                except Exception as e:
                    logger.error(f"Error syncing page {page['title']}: {e}")
                    errors += 1
            
            self._last_sync = datetime.now()
            
            return {
                'success': True,
                'pages_synced': synced,
                'errors': errors,
                'timestamp': self._last_sync.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Notion sync failed: {e}")
            return {'success': False, 'error': str(e)}


# Singleton instance
_notion_service: Optional[NotionSyncService] = None


def get_notion_service() -> NotionSyncService:
    """Get the singleton Notion service instance."""
    global _notion_service
    if _notion_service is None:
        _notion_service = NotionSyncService()
    return _notion_service
