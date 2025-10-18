"""
Comprehensive tests for JWT authentication and authorization.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    require_role,
    verify_password,
    UserRole,
    ALGORITHM,
)
from app.core.config import settings


class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_hash_password_creates_hash(self):
        password = "secure_password123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
    
    def test_verify_password_succeeds_with_correct_password(self):
        password = "secure_password123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed)
    
    def test_verify_password_fails_with_incorrect_password(self):
        password = "secure_password123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        
        assert not verify_password(wrong_password, hashed)


class TestJWTTokens:
    """Test JWT token creation and validation."""
    
    def test_create_access_token_encodes_data(self):
        data = {"sub": "testuser", "role": "analyst"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode without verification to check structure
        decoded = jwt.decode(token, options={"verify_signature": False})
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "analyst"
        assert "exp" in decoded
    
    def test_create_access_token_includes_expiration(self):
        data = {"sub": "testuser", "role": "admin"}
        token = create_access_token(data)
        
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Should expire in roughly 30 minutes (with 1 min tolerance)
        assert timedelta(minutes=29) < (exp - now) < timedelta(minutes=31)
    
    def test_create_access_token_with_custom_expiration(self):
        data = {"sub": "testuser", "role": "admin"}
        custom_delta = timedelta(hours=2)
        token = create_access_token(data, expires_delta=custom_delta)
        
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Should expire in roughly 2 hours
        assert timedelta(hours=1, minutes=59) < (exp - now) < timedelta(hours=2, minutes=1)
    
    def test_create_refresh_token_has_longer_expiration(self):
        data = {"sub": "testuser", "role": "analyst"}
        token = create_refresh_token(data)
        
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Should expire in roughly 7 days
        assert timedelta(days=6, hours=23) < (exp - now) < timedelta(days=7, hours=1)
    
    def test_decode_token_succeeds_with_valid_token(self):
        data = {"sub": "testuser", "role": "admin"}
        token = create_access_token(data)
        
        decoded = decode_token(token)
        
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "admin"
    
    def test_decode_token_fails_with_invalid_token(self):
        invalid_token = "invalid.jwt.token"
        
        with pytest.raises(HTTPException) as exc:
            decode_token(invalid_token)
        
        assert exc.value.status_code == 401
        assert "Invalid authentication credentials" in exc.value.detail
    
    def test_decode_token_fails_with_expired_token(self):
        data = {"sub": "testuser", "role": "admin"}
        # Create token that expired 1 hour ago
        expired_delta = timedelta(hours=-1)
        token = create_access_token(data, expires_delta=expired_delta)
        
        with pytest.raises(HTTPException) as exc:
            decode_token(token)
        
        assert exc.value.status_code == 401
        assert "Token has expired" in exc.value.detail
    
    def test_decode_token_fails_with_wrong_secret(self):
        data = {"sub": "testuser", "role": "admin"}
        # Create token with different secret
        wrong_secret_token = jwt.encode(
            {**data, "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
            "wrong_secret_key",
            algorithm=ALGORITHM
        )
        
        with pytest.raises(HTTPException) as exc:
            decode_token(wrong_secret_token)
        
        assert exc.value.status_code == 401


class TestRoleBasedAccessControl:
    """Test role-based access control."""
    
    @pytest.mark.asyncio
    async def test_require_role_allows_correct_role(self):
        checker = require_role(UserRole.ADMIN)
        user = {"username": "admin_user", "role": UserRole.ADMIN}
        
        # Mock get_current_user
        async def mock_get_current_user():
            return user
        
        result = await checker(user=user)
        
        assert result == user
    
    @pytest.mark.asyncio
    async def test_require_role_denies_incorrect_role(self):
        checker = require_role(UserRole.ADMIN)
        user = {"username": "analyst_user", "role": UserRole.ANALYST}
        
        with pytest.raises(HTTPException) as exc:
            await checker(user=user)
        
        assert exc.value.status_code == 403
        assert "Insufficient permissions" in exc.value.detail
    
    @pytest.mark.asyncio
    async def test_require_role_allows_multiple_roles(self):
        checker = require_role(UserRole.ADMIN, UserRole.ANALYST)
        
        # Test admin
        admin_user = {"username": "admin", "role": UserRole.ADMIN}
        result = await checker(user=admin_user)
        assert result == admin_user
        
        # Test analyst
        analyst_user = {"username": "analyst", "role": UserRole.ANALYST}
        result = await checker(user=analyst_user)
        assert result == analyst_user
    
    @pytest.mark.asyncio
    async def test_require_role_denies_readonly_user_from_admin_only(self):
        checker = require_role(UserRole.ADMIN)
        readonly_user = {"username": "viewer", "role": UserRole.READONLY}
        
        with pytest.raises(HTTPException) as exc:
            await checker(user=readonly_user)
        
        assert exc.value.status_code == 403


class TestUserRoles:
    """Test user role constants."""
    
    def test_all_roles_defined(self):
        assert UserRole.ADMIN in UserRole.ALL_ROLES
        assert UserRole.ANALYST in UserRole.ALL_ROLES
        assert UserRole.READONLY in UserRole.ALL_ROLES
    
    def test_role_values(self):
        assert UserRole.ADMIN == "admin"
        assert UserRole.ANALYST == "analyst"
        assert UserRole.READONLY == "read_only"


@pytest.mark.asyncio
async def test_get_current_user_extracts_from_token(monkeypatch):
    """Integration test for get_current_user dependency."""
    from app.core.security import get_current_user
    
    # Create valid token
    token = create_access_token({"sub": "testuser", "role": "analyst"})
    
    # Mock credentials
    class MockCredentials:
        credentials = token
    
    user = await get_current_user(credentials=MockCredentials())
    
    assert user["username"] == "testuser"
    assert user["role"] == "analyst"


@pytest.mark.asyncio
async def test_get_current_user_fails_without_username():
    """Test get_current_user fails if token missing username."""
    from app.core.security import get_current_user
    
    # Create token without 'sub'
    bad_token = jwt.encode(
        {"role": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        settings.SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    class MockCredentials:
        credentials = bad_token
    
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=MockCredentials())
    
    assert exc.value.status_code == 401
    assert "Invalid token payload" in exc.value.detail

