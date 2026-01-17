"""
Security Headers Middleware - Add security headers to all responses.
Implements Content Security Policy, CORS, and other security measures.
"""
from typing import Optional, Set
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Implements:
    - Content Security Policy (CSP)
    - X-Content-Type-Options
    - X-Frame-Options
    - Referrer-Policy
    - Permissions-Policy
    """
    
    def __init__(
        self,
        app,
        csp_policy: Optional[str] = None,
        allowed_origins: Optional[Set[str]] = None
    ):
        super().__init__(app)
        self.csp_policy = csp_policy or self._default_csp()
        self.allowed_origins = allowed_origins or {"http://localhost:3000", "http://localhost:5173"}
    
    def _default_csp(self) -> str:
        """Build default Content Security Policy."""
        return "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Needed for React dev
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: blob: https:",
            "connect-src 'self' ws: wss: https://api.openai.com https://generativelanguage.googleapis.com",
            "media-src 'self' blob:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ])
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Skip for certain paths
        if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
            return response
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(self), payment=(), usb=()"
        )
        
        # Content Security Policy (only for HTML responses)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Content-Security-Policy"] = self.csp_policy
        
        # CORS headers for allowed origins
        origin = request.headers.get("origin")
        if origin in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        
        return response


class RequestSanitizer:
    """
    Sanitize incoming request data.
    
    - Removes null bytes
    - Limits request body size
    - Validates content types
    """
    
    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain"
    }
    
    MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB
    
    @classmethod
    def sanitize_string(cls, value: str) -> str:
        """Remove potentially dangerous characters from string."""
        # Remove null bytes
        value = value.replace("\x00", "")
        
        # Remove other control characters except newlines and tabs
        import unicodedata
        value = "".join(
            char for char in value
            if not unicodedata.category(char).startswith("C")
            or char in "\n\r\t"
        )
        
        return value
    
    @classmethod
    def validate_content_type(cls, content_type: str) -> bool:
        """Check if content type is allowed."""
        # Extract base content type (without charset etc.)
        base_type = content_type.split(";")[0].strip().lower()
        return base_type in cls.ALLOWED_CONTENT_TYPES


class SQLInjectionGuard:
    """
    Detect potential SQL injection attempts.
    
    Note: This is a defense-in-depth measure.
    Always use parameterized queries as the primary defense.
    """
    
    SUSPICIOUS_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b.*\b(FROM|INTO|TABLE|DATABASE)\b)",
        r"(--|#|/\*|\*/)",  # SQL comments
        r"(\bOR\b\s+\d+\s*=\s*\d+)",  # OR 1=1
        r"(;\s*(SELECT|INSERT|DROP|DELETE))",  # Stacked queries
        r"(\bEXEC\b|\bEXECUTE\b)",
        r"(\bxp_\w+\b)",  # SQL Server extended procedures
    ]
    
    def __init__(self):
        import re
        self._patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.SUSPICIOUS_PATTERNS
        ]
    
    def is_suspicious(self, value: str) -> bool:
        """Check if string contains suspicious SQL patterns."""
        for pattern in self._patterns:
            if pattern.search(value):
                return True
        return False


# ============= IP Allowlist/Blocklist =============

class IPFilter:
    """Filter requests by IP address."""
    
    def __init__(
        self,
        allowlist: Optional[Set[str]] = None,
        blocklist: Optional[Set[str]] = None
    ):
        self.allowlist = allowlist or set()
        self.blocklist = blocklist or set()
    
    def is_allowed(self, ip: str) -> bool:
        """Check if IP is allowed."""
        # Block always takes precedence
        if ip in self.blocklist:
            return False
        
        # If allowlist is empty, allow all (except blocklist)
        if not self.allowlist:
            return True
        
        # If allowlist exists, only allow those IPs
        return ip in self.allowlist
    
    def add_to_blocklist(self, ip: str):
        """Add IP to blocklist."""
        self.blocklist.add(ip)
    
    def remove_from_blocklist(self, ip: str):
        """Remove IP from blocklist."""
        self.blocklist.discard(ip)
