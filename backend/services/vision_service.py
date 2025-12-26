"""
Vision Service - Multimodal image analysis using Gemini.
Enables the bot to see and react to images.
"""
import base64
import hashlib
from typing import Optional, Dict
from config import Config


class VisionService:
    """Service for analyzing images using multimodal LLM."""
    
    # Simple cache for image analyses
    _cache = {}
    _cache_max_size = 50
    
    def __init__(self):
        self.client = None
        self.model = None
        self._init_error = None
        self._lazy_init_done = False
    
    def _lazy_init(self):
        """Lazy initialization of vision client."""
        if self._lazy_init_done:
            return
        self._lazy_init_done = True
        
        try:
            if Config.GEMINI_API_KEY and Config.GEMINI_API_KEY != 'your-gemini-api-key-here':
                import google.generativeai as genai
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self.client = genai
                self.model = "gemini-1.5-flash"  # Multimodal model
            else:
                self._init_error = "Gemini API key not configured"
        except Exception as e:
            self._init_error = str(e)
            print(f"Vision service init error: {e}")
    
    def _get_cache_key(self, image_data: str, prompt: str) -> str:
        """Generate a cache key for an image analysis."""
        return hashlib.md5(f"{image_data[:100]}:{prompt}".encode()).hexdigest()
    
    def _add_to_cache(self, key: str, result: str):
        """Add result to cache."""
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = result
    
    def analyze_image(
        self,
        image_data: str,
        prompt: str = "Describe what you see in this image in detail.",
        mime_type: str = "image/jpeg"
    ) -> Dict:
        """
        Analyze an image using multimodal LLM.
        
        Args:
            image_data: Base64 encoded image data (without data URL prefix)
            prompt: The prompt for the analysis
            mime_type: MIME type of the image (image/jpeg, image/png, etc.)
            
        Returns:
            Dict with 'success', 'description', and optional 'error'
        """
        self._lazy_init()
        
        if self._init_error:
            return {
                'success': False,
                'error': self._init_error
            }
        
        # Check cache
        cache_key = self._get_cache_key(image_data, prompt)
        if cache_key in self._cache:
            return {
                'success': True,
                'description': self._cache[cache_key],
                'from_cache': True
            }
        
        try:
            # Create the model
            model = self.client.GenerativeModel(self.model)
            
            # Prepare image data
            image_part = {
                "mime_type": mime_type,
                "data": base64.b64decode(image_data)
            }
            
            # Generate response
            response = model.generate_content([prompt, image_part])
            description = response.text
            
            # Cache the result
            self._add_to_cache(cache_key, description)
            
            return {
                'success': True,
                'description': description
            }
            
        except Exception as e:
            print(f"Vision analysis error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def extract_context(
        self,
        image_data: str,
        mime_type: str = "image/jpeg"
    ) -> str:
        """
        Extract a brief context description for chat injection.
        
        Args:
            image_data: Base64 encoded image data
            mime_type: MIME type of the image
            
        Returns:
            Brief description for chat context
        """
        result = self.analyze_image(
            image_data,
            prompt="Briefly describe this image in 1-2 sentences for context in a conversation.",
            mime_type=mime_type
        )
        
        if result['success']:
            return result['description']
        else:
            return "[Image could not be analyzed]"
    
    def react_to_image(
        self,
        image_data: str,
        user_message: str,
        personality_context: str = "",
        mime_type: str = "image/jpeg"
    ) -> Dict:
        """
        Generate a personality-appropriate reaction to an image.
        
        Args:
            image_data: Base64 encoded image data
            user_message: What the user said about the image
            personality_context: Personality traits for style matching
            mime_type: MIME type of the image
            
        Returns:
            Dict with 'success' and 'reaction'
        """
        self._lazy_init()
        
        if self._init_error:
            return {
                'success': False,
                'error': self._init_error
            }
        
        try:
            model = self.client.GenerativeModel(self.model)
            
            image_part = {
                "mime_type": mime_type,
                "data": base64.b64decode(image_data)
            }
            
            prompt = f"""You are reacting to this image that someone shared with you.
They said: "{user_message}"

{personality_context}

Give a natural, conversational reaction to the image. Be genuine and match the conversational style described.
Keep your response brief (1-3 sentences) unless they asked a specific question."""

            response = model.generate_content([prompt, image_part])
            
            return {
                'success': True,
                'reaction': response.text
            }
            
        except Exception as e:
            print(f"Vision reaction error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def is_available(self) -> bool:
        """Check if vision service is available."""
        self._lazy_init()
        return self._init_error is None


# Singleton instance
_vision_service = None

def get_vision_service() -> VisionService:
    """Get the singleton vision service instance."""
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service
