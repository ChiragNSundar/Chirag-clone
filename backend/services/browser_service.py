
"""
Browser Service - Headless web browsing capabilities using Playwright.
Safely manages browser context and provides high-level actions (navigate, read, screenshot).
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
import base64

from .logger import get_logger

logger = get_logger(__name__)

try:
    from playwright.async_api import async_playwright, Page, Browser
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("Playwright not installed. Browsing disabled.")

class BrowserService:
    """Service to control headless browser."""
    
    def __init__(self):
        self.enabled = HAS_PLAYWRIGHT
        self._browser: Optional[Browser] = None
        self._playwright = None
    
    async def _ensure_browser(self):
        """Lazy load browser."""
        if not self.enabled:
            raise Exception("Playwright not enabled")
            
        if not self._playwright:
            self._playwright = await async_playwright().start()
            
        if not self._browser:
            try:
                self._browser = await self._playwright.chromium.launch(headless=True)
            except Exception as e:
                logger.error(f"Failed to launch browser: {e}")
                # Try installing if failed? No, just fail for now.
                raise e

    async def browse(self, url: str) -> Dict[str, Any]:
        """
        Navigate to a URL and return content + screenshot.
        """
        if not self.enabled:
            return {"error": "Browsing features disabled"}
            
        page = None
        try:
            await self._ensure_browser()
            page = await self._browser.new_page()
            
            # Set viewport
            await page.set_viewport_size({"width": 1280, "height": 800})
            
            # Navigate with timeout
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            
            # Get content
            title = await page.title()
            content = await page.inner_text("body")
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(type='jpeg', quality=70)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            return {
                "title": title,
                "url": url,
                "content": content[:10000], # Limit text size
                "screenshot": screenshot_b64,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Browse error: {e}")
            return {"error": str(e), "status": "failed"}
        finally:
            if page:
                await page.close()

    async def shutdown(self):
        """Cleanup resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

# Singleton
_browser_service = None

def get_browser_service() -> BrowserService:
    global _browser_service
    if _browser_service is None:
        _browser_service = BrowserService()
    return _browser_service
