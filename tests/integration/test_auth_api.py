"""
Integration tests for authentication API endpoints.

Tests the full auth flow: register, login, refresh, me.
"""
import pytest
from fastapi.testclient import TestClient


class TestAuthRegistration:
    """Tests for /auth/register endpoint."""
    
    def test_register_success(self, client: TestClient):
        """Test successful user registration."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "full_name": "New User",
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_register_weak_password(self, client: TestClient):
        """Test registration with weak password fails."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@example.com",
                "password": "weak",
                "full_name": "Weak User",
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
    
    def test_register_duplicate_email(self, client: TestClient):
        """Test registration with existing email fails."""
        # First registration
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "SecurePass123",
            }
        )
        
        # Second registration with same email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "AnotherPass123",
            }
        )
        
        assert response.status_code == 400
        assert "already" in response.json()["message"].lower()
    
    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email fails."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123",
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestAuthLogin:
    """Tests for /auth/login endpoint."""
    
    def test_login_success(self, client: TestClient):
        """Test successful login."""
        # Register first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "SecurePass123",
            }
        )
        
        # Login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@example.com",
                "password": "SecurePass123",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_login_wrong_password(self, client: TestClient):
        """Test login with wrong password fails."""
        # Register first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpass@example.com",
                "password": "SecurePass123",
            }
        )
        
        # Login with wrong password
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpass@example.com",
                "password": "WrongPassword123",
            }
        )
        
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with nonexistent user fails."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePass123",
            }
        )
        
        assert response.status_code == 401


class TestAuthMe:
    """Tests for /auth/me endpoint."""
    
    def test_get_me_authenticated(self, client: TestClient):
        """Test getting current user when authenticated."""
        # Register and get token
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "me@example.com",
                "password": "SecurePass123",
                "full_name": "Test User",
            }
        )
        token = register_response.json()["access_token"]
        
        # Get current user
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"
        assert data["full_name"] == "Test User"
    
    def test_get_me_unauthenticated(self, client: TestClient):
        """Test getting current user without token fails."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401


class TestAuthRefresh:
    """Tests for /auth/refresh endpoint."""
    
    def test_refresh_token_success(self, client: TestClient):
        """Test refreshing access token."""
        # Register and get tokens
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "password": "SecurePass123",
            }
        )
        refresh_token = register_response.json()["refresh_token"]
        
        # Refresh tokens
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_refresh_invalid_token(self, client: TestClient):
        """Test refresh with invalid token fails."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"}
        )
        
        assert response.status_code == 401
