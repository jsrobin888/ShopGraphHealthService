"""
Security module for the DealHealthService.

Implements JWT authentication, rate limiting, input validation, and security headers
as specified in the system design.
"""

import time
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

# Security configuration
SECURITY_CONFIG = {
    "jwt_secret": "your-super-secret-jwt-key-change-in-production",  # Change in production
    "jwt_algorithm": "HS256",
    "jwt_expiration_hours": 24,
    "rate_limit_requests_per_minute": 100,
    "rate_limit_burst_size": 20,
    "rate_limit_window_size_seconds": 60,  # Added missing field
    "max_request_size_mb": 10,
    "allowed_origins": ["*"],  # Configure appropriately for production
    "allowed_methods": ["GET", "POST", "PUT", "DELETE"],
    "allowed_headers": ["*"],
    "expose_headers": ["X-Total-Count", "X-Health-Score"],
    "max_age_seconds": 3600,
}


class JWTPayload(BaseModel):
    """JWT token payload structure."""
    
    user_id: str
    email: str
    role: str
    permissions: List[str]
    exp: datetime
    iat: datetime
    iss: str = "deal-health-service"


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    
    requests_per_minute: int = 100
    burst_size: int = 20
    window_size_seconds: int = 60


class SecurityService:
    """Security service for authentication and authorization."""
    
    def __init__(self, config: Dict = None):
        self.config = config or SECURITY_CONFIG
        self.rate_limit_store: Dict[str, List[float]] = defaultdict(list)
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def create_jwt_token(self, user_id: str, email: str, role: str, permissions: List[str]) -> str:
        """Create a JWT token for authentication."""
        now = datetime.utcnow()
        payload = JWTPayload(
            user_id=user_id,
            email=email,
            role=role,
            permissions=permissions,
            exp=now + timedelta(hours=self.config["jwt_expiration_hours"]),
            iat=now,
        )
        
        token = jwt.encode(
            payload.dict(),
            self.config["jwt_secret"],
            algorithm=self.config["jwt_algorithm"]
        )
        
        logger.info(f"Created JWT token for user {user_id}")
        return token
    
    def verify_jwt_token(self, token: str) -> JWTPayload:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.config["jwt_secret"],
                algorithms=[self.config["jwt_algorithm"]]
            )
            return JWTPayload(**payload)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    def check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit."""
        now = time.time()
        
        # Cleanup old entries periodically
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_rate_limit_store(now)
            self._last_cleanup = now
        
        # Get client's request history
        requests = self.rate_limit_store[client_id]
        
        # Remove requests older than the window
        window_start = now - self.config["rate_limit_window_size_seconds"]
        requests = [req_time for req_time in requests if req_time > window_start]
        self.rate_limit_store[client_id] = requests
        
        # Check if limit exceeded
        if len(requests) >= self.config["rate_limit_requests_per_minute"]:
            logger.warning(f"Rate limit exceeded for client {client_id}")
            return False
        
        # Add current request
        requests.append(now)
        return True
    
    def _cleanup_rate_limit_store(self, now: float):
        """Clean up old rate limit entries."""
        window_start = now - self.config["rate_limit_window_size_seconds"]
        for client_id in list(self.rate_limit_store.keys()):
            self.rate_limit_store[client_id] = [
                req_time for req_time in self.rate_limit_store[client_id]
                if req_time > window_start
            ]
            if not self.rate_limit_store[client_id]:
                del self.rate_limit_store[client_id]
    
    def validate_input(self, data: Dict) -> bool:
        """Validate input data for security."""
        # Check for SQL injection patterns
        sql_patterns = ["'", '"', ';', '--', '/*', '*/', 'DROP', 'DELETE', 'UPDATE', 'INSERT']
        data_str = str(data).upper()
        
        for pattern in sql_patterns:
            if pattern.upper() in data_str:
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return False
        
        # Check for XSS patterns
        xss_patterns = ['<script', 'javascript:', 'onload=', 'onerror=']
        for pattern in xss_patterns:
            if pattern.lower() in str(data).lower():
                logger.warning(f"Potential XSS detected: {pattern}")
                return False
        
        return True
    
    def sanitize_input(self, data: str) -> str:
        """Sanitize input data."""
        # Basic HTML entity encoding
        replacements = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '&': '&amp;'
        }
        
        for char, replacement in replacements.items():
            data = data.replace(char, replacement)
        
        return data


class SecurityMiddleware:
    """Security middleware for FastAPI."""
    
    def __init__(self, security_service: SecurityService):
        self.security_service = security_service
        self.security_scheme = HTTPBearer()
    
    async def authenticate_request(self, request: Request) -> Optional[JWTPayload]:
        """Authenticate incoming request."""
        # Skip authentication for health and metrics endpoints
        if request.url.path in ['/health', '/metrics', '/docs', '/openapi.json']:
            return None
        
        try:
            credentials: HTTPAuthorizationCredentials = await self.security_scheme(request)
            token = credentials.credentials
            return self.security_service.verify_jwt_token(token)
        except Exception as e:
            logger.warning(f"Authentication failed: {str(e)}")
            return None
    
    def check_rate_limit(self, request: Request) -> bool:
        """Check rate limit for request."""
        client_id = self._get_client_id(request)
        return self.security_service.check_rate_limit(client_id)
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use X-Forwarded-For header if available (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Fall back to client host
        return request.client.host if request.client else "unknown"
    
    def add_security_headers(self, response):
        """Add security headers to response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


# Input validation models
class EventValidation(BaseModel):
    """Event validation model."""
    
    @validator('*', pre=True)
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            # Basic sanitization
            return v.strip()[:1000]  # Limit length
        return v


class APIKeyValidation(BaseModel):
    """API key validation model."""
    
    api_key: str
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 32:
            raise ValueError("API key must be at least 32 characters long")
        return v


# Security utilities
def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    """Hash a password securely."""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${hash_obj.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        salt, hash_hex = hashed.split('$')
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hash_obj.hex() == hash_hex
    except Exception:
        return False


# Global security service instance
security_service = SecurityService()
security_middleware = SecurityMiddleware(security_service) 