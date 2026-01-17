"""
OAuth2 Authentication Routes
Endpoints for Google OAuth2 login flow.
"""
from fastapi import APIRouter, Query, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from typing import Optional

from services.auth_service import (
    get_auth_service, 
    get_current_user, 
    require_auth,
    require_admin,
    is_admin
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/status")
async def get_auth_status():
    """Get OAuth provider availability status."""
    auth_service = get_auth_service()
    return auth_service.get_oauth_status()


@router.get("/google/url")
async def get_google_auth_url(redirect_uri: str = Query(...)):
    """Get Google OAuth authorization URL."""
    auth_service = get_auth_service()
    url, state = auth_service.get_google_auth_url(redirect_uri)
    return {"url": url, "state": state}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    redirect_uri: str = Query(...)
):
    """
    Handle Google OAuth callback.
    
    Returns JWT token for authenticated user.
    """
    auth_service = get_auth_service()
    
    try:
        user = await auth_service.exchange_google_code(code, redirect_uri)
        token = auth_service.generate_jwt(user)
        
        return {
            "success": True,
            "token": token,
            "user": user.to_dict(),
            "is_admin": is_admin(user.email)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_current_user_info(user = Depends(require_auth)):
    """Get current authenticated user info with admin status."""
    user["is_admin"] = is_admin(user.get("email", ""))
    return user


@router.get("/check-admin")
async def check_admin_access(user = Depends(require_admin)):
    """Check if current user is an admin (for training access)."""
    return {"is_admin": True, "email": user.get("email")}


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    
    Note: JWT tokens are stateless, so logout is handled client-side
    by removing the token. This endpoint is for API completeness.
    """
    return {"success": True, "message": "Logged out"}
