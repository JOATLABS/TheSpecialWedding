"""
Custom exception classes for the Wedding WebApp
"""

class WeddingAppException(Exception):
    """Base exception class for the Wedding WebApp"""
    
    def __init__(self, message: str, error_code: str = None, status_code: int = 500):
        self.message = message
        self.error_code = error_code or "INTERNAL_ERROR"
        self.status_code = status_code
        super().__init__(self.message)

class AuthenticationError(WeddingAppException):
    """Authentication related errors"""
    
    def __init__(self, message: str = "Authentication failed", error_code: str = "AUTH_ERROR"):
        super().__init__(message, error_code, 401)

class AuthorizationError(WeddingAppException):
    """Authorization related errors"""
    
    def __init__(self, message: str = "Access denied", error_code: str = "ACCESS_DENIED"):
        super().__init__(message, error_code, 403)

class ValidationError(WeddingAppException):
    """Validation related errors"""
    
    def __init__(self, message: str, field: str = None, error_code: str = "VALIDATION_ERROR"):
        self.field = field
        super().__init__(message, error_code, 400)

class NotFoundError(WeddingAppException):
    """Resource not found errors"""
    
    def __init__(self, resource: str = "Resource", error_code: str = "NOT_FOUND"):
        message = f"{resource} not found"
        super().__init__(message, error_code, 404)

class ConflictError(WeddingAppException):
    """Resource conflict errors"""
    
    def __init__(self, message: str = "Resource conflict", error_code: str = "CONFLICT"):
        super().__init__(message, error_code, 409)

class DatabaseError(WeddingAppException):
    """Database operation errors"""
    
    def __init__(self, message: str = "Database operation failed", error_code: str = "DATABASE_ERROR"):
        super().__init__(message, error_code, 500)

class ExternalServiceError(WeddingAppException):
    """External service errors"""
    
    def __init__(self, service: str, message: str = None, error_code: str = "EXTERNAL_SERVICE_ERROR"):
        if not message:
            message = f"{service} service unavailable"
        super().__init__(message, error_code, 503)

class RateLimitError(WeddingAppException):
    """Rate limiting errors"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(message, "RATE_LIMIT_EXCEEDED", 429)

class SubscriptionError(WeddingAppException):
    """Subscription related errors"""
    
    def __init__(self, message: str, error_code: str = "SUBSCRIPTION_ERROR"):
        super().__init__(message, error_code, 402)

class InvitationError(WeddingAppException):
    """Invitation related errors"""
    
    def __init__(self, message: str, error_code: str = "INVITATION_ERROR"):
        super().__init__(message, error_code, 400)

class WeddingAccessError(WeddingAppException):
    """Wedding access related errors"""
    
    def __init__(self, wedding_id: str = None, error_code: str = "WEDDING_ACCESS_DENIED"):
        message = f"Access denied to wedding {wedding_id}" if wedding_id else "Wedding access denied"
        super().__init__(message, error_code, 403)