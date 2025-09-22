"""
Unit tests for AuthService
"""
import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from app.services.auth_service import AuthService


class TestAuthService:
    """Test cases for AuthService"""
    
    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mocked database"""
        with patch('app.services.auth_service.mongo') as mock_mongo:
            mock_mongo.db = {
                "admin_users": Mock(),
                "users": Mock()
            }
            return AuthService()
    
    @pytest.fixture
    def sample_admin_user(self):
        """Sample admin user data"""
        return {
            "_id": "admin_123",
            "email": "admin@test.com",
            "hashed_password": "$2b$12$hashedpassword",
            "role": "admin"
        }
    
    @pytest.fixture
    def sample_user(self):
        """Sample regular user data"""
        return {
            "_id": "user_123",
            "email": "user@test.com",
            "password_hash": "$2b$12$hashedpassword",
            "role": "wedding_planner",
            "is_active": True,
            "email_verified": True,
            "registration_source": "public_signup"
        }
    
    @patch('app.services.auth_service.verify_password')
    def test_authenticate_admin_user_success(self, mock_verify, auth_service, sample_admin_user):
        """Test successful admin user authentication"""
        # Arrange
        auth_service.admin_collection.find_one.return_value = sample_admin_user
        mock_verify.return_value = True
        
        # Act
        result = auth_service.authenticate_user("admin@test.com", "password")
        
        # Assert
        assert result == sample_admin_user
        auth_service.admin_collection.find_one.assert_called_once_with({"email": "admin@test.com"})
        mock_verify.assert_called_once_with("password", "$2b$12$hashedpassword")
    
    @patch('app.services.auth_service.verify_password')
    def test_authenticate_admin_user_wrong_password(self, mock_verify, auth_service, sample_admin_user):
        """Test admin user authentication with wrong password"""
        # Arrange
        auth_service.admin_collection.find_one.return_value = sample_admin_user
        mock_verify.return_value = False
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            auth_service.authenticate_user("admin@test.com", "wrongpassword")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid credentials"
    
    @patch('app.services.auth_service.verify_password')
    def test_authenticate_regular_user_success(self, mock_verify, auth_service, sample_user):
        """Test successful regular user authentication"""
        # Arrange
        auth_service.admin_collection.find_one.return_value = None
        auth_service.users_collection.find_one.return_value = sample_user
        mock_verify.return_value = True
        
        # Act
        result = auth_service.authenticate_user("user@test.com", "password")
        
        # Assert
        assert result == sample_user
        auth_service.users_collection.find_one.assert_called_once_with({"email": "user@test.com"})
        mock_verify.assert_called_once_with("password", "$2b$12$hashedpassword")
    
    def test_authenticate_user_not_found(self, auth_service):
        """Test authentication when user doesn't exist"""
        # Arrange
        auth_service.admin_collection.find_one.return_value = None
        auth_service.users_collection.find_one.return_value = None
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            auth_service.authenticate_user("nonexistent@test.com", "password")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid credentials"
    
    @patch('app.services.auth_service.verify_password')
    def test_authenticate_inactive_user(self, mock_verify, auth_service, sample_user):
        """Test authentication of inactive user"""
        # Arrange
        sample_user["is_active"] = False
        auth_service.admin_collection.find_one.return_value = None
        auth_service.users_collection.find_one.return_value = sample_user
        mock_verify.return_value = True
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            auth_service.authenticate_user("user@test.com", "password")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Account is not active. Please contact support."
    
    @patch('app.services.auth_service.verify_password')
    def test_authenticate_unverified_email(self, mock_verify, auth_service, sample_user):
        """Test authentication of user with unverified email"""
        # Arrange
        sample_user["email_verified"] = False
        auth_service.admin_collection.find_one.return_value = None
        auth_service.users_collection.find_one.return_value = sample_user
        mock_verify.return_value = True
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            auth_service.authenticate_user("user@test.com", "password")
        
        assert exc_info.value.status_code == 401
        assert "verify your email address" in exc_info.value.detail
    
    @patch('app.services.auth_service.create_access_token')
    def test_login_and_get_token_success(self, mock_create_token, auth_service, sample_admin_user):
        """Test successful login and token generation"""
        # Arrange
        mock_create_token.return_value = "test_token_123"
        
        with patch.object(auth_service, 'authenticate_user') as mock_auth:
            mock_auth.return_value = sample_admin_user
            
            # Act
            result = auth_service.login_and_get_token("admin@test.com", "password")
            
            # Assert
            assert result == {"access_token": "test_token_123", "token_type": "bearer"}
            mock_auth.assert_called_once_with("admin@test.com", "password")
            mock_create_token.assert_called_once()