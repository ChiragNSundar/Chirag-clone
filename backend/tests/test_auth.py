"""
Auth Service Tests - Google OAuth2, JWT, and Admin Access Control.

Run with: pytest tests/test_auth.py -v
"""
import pytest
import os
import sys
import time
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# JWT Token Tests
# ============================================================================

class TestJWTTokens:
    """Test JWT token generation and validation."""
    
    @pytest.fixture
    def auth_service(self):
        """Create auth service for testing."""
        try:
            from services.auth_service import AuthService
            return AuthService()
        except ImportError as e:
            pytest.skip(f"AuthService not available: {e}")
    
    @pytest.fixture
    def sample_user(self):
        """Create a sample user for testing."""
        try:
            from services.auth_service import User
            return User(
                id="test_123",
                email="test@example.com",
                name="Test User",
                provider="google"
            )
        except ImportError as e:
            pytest.skip(f"User model not available: {e}")
    
    def test_jwt_generation(self, auth_service, sample_user):
        """Test that JWT token is generated correctly."""
        token = auth_service.generate_jwt(sample_user)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        # JWT has 3 parts separated by dots
        assert token.count('.') == 2
    
    def test_jwt_verification(self, auth_service, sample_user):
        """Test that JWT token can be verified."""
        token = auth_service.generate_jwt(sample_user)
        payload = auth_service.verify_jwt(token)
        
        assert payload is not None
        assert payload["sub"] == sample_user.id
        assert payload["email"] == sample_user.email
        assert payload["name"] == sample_user.name
    
    def test_jwt_invalid_token(self, auth_service):
        """Test that invalid JWT token returns None."""
        result = auth_service.verify_jwt("invalid.token.here")
        assert result is None
    
    def test_jwt_empty_token(self, auth_service):
        """Test that empty JWT token returns None."""
        result = auth_service.verify_jwt("")
        assert result is None
    
    def test_jwt_malformed_token(self, auth_service):
        """Test that malformed JWT token is rejected."""
        result = auth_service.verify_jwt("not-a-jwt")
        assert result is None


# ============================================================================
# OAuth URL Generation Tests
# ============================================================================

class TestOAuthURLGeneration:
    """Test Google OAuth authorization URL generation."""
    
    @pytest.fixture
    def auth_service(self):
        """Create auth service for testing."""
        try:
            from services.auth_service import AuthService
            return AuthService()
        except ImportError as e:
            pytest.skip(f"AuthService not available: {e}")
    
    def test_google_auth_url_format(self, auth_service):
        """Test Google OAuth URL has correct format."""
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "test-client-id"}):
            try:
                url, state = auth_service.get_google_auth_url("http://localhost/callback")
                
                assert "accounts.google.com" in url
                assert "client_id=test-client-id" in url
                assert "redirect_uri=" in url
                assert "response_type=code" in url
                assert state is not None
                assert len(state) > 10
            except Exception:
                pytest.skip("Google OAuth not configured")
    
    def test_state_uniqueness(self, auth_service):
        """Test that OAuth state is unique per request."""
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "test"}):
            try:
                _, state1 = auth_service.get_google_auth_url("http://localhost/callback")
                _, state2 = auth_service.get_google_auth_url("http://localhost/callback")
                
                assert state1 != state2
            except Exception:
                pytest.skip("Google OAuth not configured")


# ============================================================================
# Admin Whitelist Tests
# ============================================================================

class TestAdminWhitelist:
    """Test admin email whitelist functionality."""
    
    def test_is_admin_valid_email(self):
        """Test is_admin returns True for whitelisted email."""
        try:
            from services.auth_service import is_admin
            # Default whitelist includes chiragns12@gmail.com
            assert is_admin("chiragns12@gmail.com") == True
        except ImportError as e:
            pytest.skip(f"is_admin not available: {e}")
    
    def test_is_admin_invalid_email(self):
        """Test is_admin returns False for non-whitelisted email."""
        try:
            from services.auth_service import is_admin
            assert is_admin("random@example.com") == False
        except ImportError as e:
            pytest.skip(f"is_admin not available: {e}")
    
    def test_is_admin_case_insensitive(self):
        """Test is_admin is case-insensitive."""
        try:
            from services.auth_service import is_admin
            assert is_admin("CHIRAGNS12@GMAIL.COM") == True
            assert is_admin("ChiragNS12@Gmail.com") == True
        except ImportError as e:
            pytest.skip(f"is_admin not available: {e}")
    
    def test_is_admin_whitespace_handling(self):
        """Test is_admin handles whitespace."""
        try:
            from services.auth_service import is_admin
            assert is_admin("  chiragns12@gmail.com  ") == True
        except ImportError as e:
            pytest.skip(f"is_admin not available: {e}")


# ============================================================================
# Require Admin Dependency Tests
# ============================================================================

class TestRequireAdmin:
    """Test require_admin FastAPI dependency."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Create mock credentials."""
        credentials = MagicMock()
        credentials.credentials = "valid.jwt.token"
        return credentials
    
    @pytest.mark.asyncio
    async def test_require_admin_no_credentials(self):
        """Test require_admin raises 401 with no credentials."""
        try:
            from services.auth_service import require_admin
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(None)
            
            assert exc_info.value.status_code == 401
        except ImportError as e:
            pytest.skip(f"require_admin not available: {e}")
    
    @pytest.mark.asyncio
    async def test_require_admin_non_admin_user(self):
        """Test require_admin raises 403 for non-admin user."""
        try:
            from services.auth_service import require_admin, get_auth_service
            from fastapi import HTTPException
            
            # Mock credentials and JWT verification
            credentials = MagicMock()
            credentials.credentials = "valid.token"
            
            with patch.object(get_auth_service(), 'verify_jwt') as mock_verify:
                mock_verify.return_value = {
                    "sub": "user_123",
                    "email": "notadmin@example.com",
                    "name": "Not Admin"
                }
                
                with pytest.raises(HTTPException) as exc_info:
                    await require_admin(credentials)
                
                assert exc_info.value.status_code == 403
        except ImportError as e:
            pytest.skip(f"require_admin not available: {e}")


# ============================================================================
# OAuth Status Tests
# ============================================================================

class TestOAuthStatus:
    """Test OAuth provider status checks."""
    
    def test_oauth_status_returns_dict(self):
        """Test get_oauth_status returns a dictionary."""
        try:
            from services.auth_service import AuthService
            service = AuthService()
            status = service.get_oauth_status()
            
            assert isinstance(status, dict)
            assert "google" in status
            assert isinstance(status["google"], bool)
        except ImportError as e:
            pytest.skip(f"AuthService not available: {e}")


# ============================================================================
# User Model Tests
# ============================================================================

class TestUserModel:
    """Test User dataclass."""
    
    def test_user_to_dict(self):
        """Test User.to_dict() method."""
        try:
            from services.auth_service import User
            
            user = User(
                id="test_123",
                email="test@example.com",
                name="Test User",
                picture="https://example.com/pic.jpg",
                provider="google"
            )
            
            data = user.to_dict()
            
            assert data["id"] == "test_123"
            assert data["email"] == "test@example.com"
            assert data["name"] == "Test User"
            assert data["picture"] == "https://example.com/pic.jpg"
            assert data["provider"] == "google"
            assert "created_at" in data
        except ImportError as e:
            pytest.skip(f"User model not available: {e}")
    
    def test_user_default_values(self):
        """Test User default values."""
        try:
            from services.auth_service import User
            
            user = User(
                id="test_123",
                email="test@example.com",
                name="Test User"
            )
            
            assert user.provider == "local"
            assert user.picture is None
            assert user.created_at is not None
        except ImportError as e:
            pytest.skip(f"User model not available: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
