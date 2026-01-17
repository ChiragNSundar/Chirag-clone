"""
OAuth2 Authentication Service
Handles Google and GitHub OAuth2 authentication flows.
"""
import os
import secrets
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import jwt
from functools import wraps

from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .logger import get_logger

logger = get_logger(__name__)

# Configuration from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")

# Admin Access Control - Only these emails can access training
ALLOWED_ADMIN_EMAILS = os.getenv(
    "ALLOWED_ADMIN_EMAILS", 
    "chiragns12@gmail.com"
).split(",")

JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # 1 week

# OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@dataclass
class User:
    """Authenticated user."""
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    provider: str = "local"
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "provider": self.provider,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class AuthService:
    """
    OAuth2 Authentication Service.
    
    Supports:
    - Google OAuth2
    - GitHub OAuth2
    - JWT token generation and validation
    """
    
    def __init__(self):
        self.sessions: Dict[str, User] = {}
        self._check_config()
    
    def _check_config(self):
        """Log configuration status."""
        if not GOOGLE_CLIENT_ID:
            logger.warning("GOOGLE_CLIENT_ID not set - Google OAuth disabled")
        if not GITHUB_CLIENT_ID:
            logger.warning("GITHUB_CLIENT_ID not set - GitHub OAuth disabled")
    
    def get_google_auth_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Generate Google OAuth2 authorization URL.
        
        Args:
            redirect_uri: Callback URL after auth
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=503, detail="Google OAuth not configured")
        
        state = state or secrets.token_urlsafe(32)
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "email profile openid",
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GOOGLE_AUTH_URL}?{query}", state
    
    def get_github_auth_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Generate GitHub OAuth2 authorization URL.
        
        Args:
            redirect_uri: Callback URL after auth
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        if not GITHUB_CLIENT_ID:
            raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
        
        state = state or secrets.token_urlsafe(32)
        params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "user:email read:user",
            "state": state
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GITHUB_AUTH_URL}?{query}", state
    
    async def exchange_google_code(self, code: str, redirect_uri: str) -> User:
        """
        Exchange Google authorization code for user info.
        
        Args:
            code: Authorization code from Google
            redirect_uri: Same redirect URI used in auth request
            
        Returns:
            Authenticated User object
        """
        import httpx
        
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri
                }
            )
            
            if token_response.status_code != 200:
                logger.error(f"Google token exchange failed: {token_response.text}")
                raise HTTPException(status_code=401, detail="Failed to authenticate with Google")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            
            # Get user info
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if userinfo_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Failed to get user info from Google")
            
            userinfo = userinfo_response.json()
            
            user = User(
                id=f"google_{userinfo['id']}",
                email=userinfo.get("email", ""),
                name=userinfo.get("name", userinfo.get("email", "")),
                picture=userinfo.get("picture"),
                provider="google"
            )
            
            logger.info(f"User authenticated via Google: {user.email}")
            return user
    
    async def exchange_github_code(self, code: str, redirect_uri: str) -> User:
        """
        Exchange GitHub authorization code for user info.
        
        Args:
            code: Authorization code from GitHub
            redirect_uri: Same redirect URI used in auth request
            
        Returns:
            Authenticated User object
        """
        import httpx
        
        async with httpx.AsyncClient() as client:
            # Exchange code for token
            token_response = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri
                }
            )
            
            if token_response.status_code != 200:
                logger.error(f"GitHub token exchange failed: {token_response.text}")
                raise HTTPException(status_code=401, detail="Failed to authenticate with GitHub")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            
            if not access_token:
                raise HTTPException(status_code=401, detail="No access token from GitHub")
            
            # Get user info
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            
            user_response = await client.get(GITHUB_USER_URL, headers=headers)
            if user_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Failed to get user info from GitHub")
            
            userinfo = user_response.json()
            
            # Get email (may be private)
            email = userinfo.get("email")
            if not email:
                emails_response = await client.get(GITHUB_EMAILS_URL, headers=headers)
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    primary_email = next((e for e in emails if e.get("primary")), None)
                    email = primary_email.get("email") if primary_email else emails[0].get("email") if emails else ""
            
            user = User(
                id=f"github_{userinfo['id']}",
                email=email or f"{userinfo.get('login')}@github.local",
                name=userinfo.get("name") or userinfo.get("login", ""),
                picture=userinfo.get("avatar_url"),
                provider="github"
            )
            
            logger.info(f"User authenticated via GitHub: {user.email}")
            return user
    
    def generate_jwt(self, user: User) -> str:
        """
        Generate JWT token for authenticated user.
        
        Args:
            user: Authenticated user
            
        Returns:
            JWT token string
        """
        payload = {
            "sub": user.id,
            "email": user.email,
            "name": user.name,
            "provider": user.provider,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
    
    def get_oauth_status(self) -> Dict[str, bool]:
        """Get status of OAuth providers."""
        return {
            "google": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
            "github": bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)
        }


# Singleton instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get singleton auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# FastAPI Security Dependency
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency to get current authenticated user.
    
    Returns:
        User payload from JWT or None
    """
    if not credentials:
        return None
    
    auth_service = get_auth_service()
    return auth_service.verify_jwt(credentials.credentials)


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency that requires authentication.
    
    Raises:
        HTTPException: If not authenticated
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    auth_service = get_auth_service()
    user = auth_service.verify_jwt(credentials.credentials)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user


def is_admin(email: str) -> bool:
    """
    Check if email is in the allowed admin list.
    
    Args:
        email: User's email address
        
    Returns:
        True if user is an admin
    """
    return email.lower().strip() in [e.lower().strip() for e in ALLOWED_ADMIN_EMAILS]


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency that requires admin authentication.
    Only allows users with emails in ALLOWED_ADMIN_EMAILS.
    
    Raises:
        HTTPException: If not authenticated or not an admin
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    auth_service = get_auth_service()
    user = auth_service.verify_jwt(credentials.credentials)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    email = user.get("email", "")
    if not is_admin(email):
        logger.warning(f"Unauthorized admin access attempt by: {email}")
        raise HTTPException(
            status_code=403, 
            detail=f"Access denied. Only {ALLOWED_ADMIN_EMAILS[0]} can access training."
        )
    
    return user
