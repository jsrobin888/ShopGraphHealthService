"""
Configuration module for the DealHealthService.

Provides production-ready configuration management that aligns with the system design.
"""

import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    url: str = Field(default="postgresql://user:password@localhost/deal_health")
    pool_size: int = Field(default=20, ge=1, le=100)
    max_overflow: int = Field(default=30, ge=0)
    pool_timeout: int = Field(default=30, ge=1)
    pool_recycle: int = Field(default=3600, ge=300)
    
    @validator('url')
    def validate_database_url(cls, v):
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError('Database URL must be a PostgreSQL connection string')
        return v


class RedisConfig(BaseModel):
    """Redis configuration."""
    
    url: str = Field(default="redis://localhost:6379")
    pool_size: int = Field(default=10, ge=1, le=50)
    max_connections: int = Field(default=20, ge=1)
    socket_timeout: int = Field(default=5, ge=1)
    socket_connect_timeout: int = Field(default=5, ge=1)
    retry_on_timeout: bool = True
    health_check_interval: int = Field(default=30, ge=5)


class MessageQueueConfig(BaseModel):
    """Message queue configuration."""
    
    provider: str = Field(default="pubsub")  # pubsub, mock
    project_id: Optional[str] = None
    subscription_name: str = Field(default="deal-health-events")
    topic_name: str = Field(default="deal-health-events")
    credentials_path: Optional[str] = None
    
    # Retry configuration
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: float = Field(default=1.0, ge=0.1)
    max_retry_delay_seconds: float = Field(default=60.0, ge=1.0)
    
    # Processing configuration
    batch_size: int = Field(default=10, ge=1, le=100)
    max_concurrent_messages: int = Field(default=5, ge=1, le=50)
    ack_deadline_seconds: int = Field(default=60, ge=10)
    
    # Dead letter queue
    enable_dlq: bool = True
    dlq_topic_name: str = Field(default="deal-health-events-dlq")
    max_delivery_attempts: int = Field(default=3, ge=1, le=10)


class AIConfig(BaseModel):
    """AI service configuration."""
    
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_model: str = Field(default="gpt-4")
    anthropic_model: str = Field(default="claude-3-sonnet-20240229")
    max_tokens: int = Field(default=1000, ge=100, le=4000)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    max_retries: int = Field(default=3, ge=1, le=5)
    
    # Fallback configuration
    enable_fallback: bool = True
    fallback_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class SecurityConfig(BaseModel):
    """Security configuration."""
    
    jwt_secret: str = Field(default="your-super-secret-jwt-key-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_hours: int = Field(default=24, ge=1, le=168)
    
    # Rate limiting
    rate_limit_requests_per_minute: int = Field(default=100, ge=10, le=1000)
    rate_limit_burst_size: int = Field(default=20, ge=5, le=100)
    rate_limit_window_size_seconds: int = Field(default=60, ge=30, le=300)
    
    # CORS
    allowed_origins: List[str] = Field(default=["*"])
    allowed_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE"])
    allowed_headers: List[str] = Field(default=["*"])
    expose_headers: List[str] = Field(default=["X-Total-Count", "X-Health-Score"])
    max_age_seconds: int = Field(default=3600, ge=300, le=86400)
    
    # Input validation
    max_request_size_mb: int = Field(default=10, ge=1, le=100)
    
    @validator('jwt_secret')
    def validate_jwt_secret(cls, v):
        if v == "your-super-secret-jwt-key-change-in-production":
            raise ValueError("JWT secret must be changed in production")
        if len(v) < 32:
            raise ValueError("JWT secret must be at least 32 characters long")
        return v


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""
    
    metrics_port: int = Field(default=9090, ge=1024, le=65535)
    log_level: str = Field(default="INFO")
    enable_structured_logging: bool = True
    enable_prometheus_metrics: bool = True
    enable_distributed_tracing: bool = True
    
    # Alerting
    alert_on_error_rate_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    alert_on_latency_threshold_ms: int = Field(default=1000, ge=100, le=10000)
    alert_on_queue_depth_threshold: int = Field(default=1000, ge=100, le=10000)


class HealthCalculationConfig(BaseModel):
    """Health calculation configuration."""
    
    # Event weights
    automated_test_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    community_verification_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    community_tip_weight: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Temporal decay
    decay_rate_per_day: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Minimum confidence thresholds
    min_confidence_for_positive: float = Field(default=0.3, ge=0.0, le=1.0)
    min_confidence_for_negative: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Event age limits
    max_event_age_days: int = Field(default=30, ge=1, le=365)
    
    @validator('automated_test_weight', 'community_verification_weight', 'community_tip_weight')
    @classmethod
    def validate_weights(cls, v):
        if v < 0 or v > 1:
            raise ValueError('Weights must be between 0 and 1')
        return v
    
    @property
    def total_weight(self) -> float:
        """Calculate total weight for validation."""
        return self.automated_test_weight + self.community_verification_weight + self.community_tip_weight


class ServiceConfig(BaseSettings):
    """Main service configuration."""
    
    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    
    # Service
    service_name: str = Field(default="deal-health-service")
    service_version: str = Field(default="1.0.0")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1024, le=65535)
    
    # Database
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    
    # Redis
    redis: RedisConfig = Field(default_factory=RedisConfig)
    
    # Message Queue
    message_queue: MessageQueueConfig = Field(default_factory=MessageQueueConfig)
    
    # AI
    ai: AIConfig = Field(default_factory=AIConfig)
    
    # Security
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    # Monitoring
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Health Calculation
    health_calculation: HealthCalculationConfig = Field(default_factory=HealthCalculationConfig)
    
    # Processing
    batch_size: int = Field(default=100, ge=1, le=1000)
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator('environment')
    def validate_environment(cls, v):
        allowed = ['development', 'staging', 'production']
        if v not in allowed:
            raise ValueError(f'Environment must be one of: {allowed}')
        return v
    
    def get_database_url(self) -> str:
        """Get database URL from environment or config."""
        return os.getenv('DATABASE_URL', self.database.url)
    
    def get_redis_url(self) -> str:
        """Get Redis URL from environment or config."""
        return os.getenv('REDIS_URL', self.redis.url)
    
    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from environment or config."""
        return os.getenv('OPENAI_API_KEY', self.ai.openai_api_key)
    
    def get_anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key from environment or config."""
        return os.getenv('ANTHROPIC_API_KEY', self.ai.anthropic_api_key)
    
    def get_jwt_secret(self) -> str:
        """Get JWT secret from environment or config."""
        return os.getenv('JWT_SECRET', self.security.jwt_secret)
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == 'production'
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins based on environment."""
        if self.is_production():
            return self.security.allowed_origins
        return ["*"]  # Allow all in development


# Global configuration instance
config = ServiceConfig()


def get_config() -> ServiceConfig:
    """Get the global configuration instance."""
    return config


def validate_config() -> None:
    """Validate the configuration."""
    # Validate health calculation weights
    total_weight = config.health_calculation.total_weight
    if abs(total_weight - 1.0) > 0.01:
        raise ValueError(f"Health calculation weights must sum to 1.0, got {total_weight}")
    
    # Validate production settings
    if config.is_production():
        if config.debug:
            raise ValueError("Debug mode cannot be enabled in production")
        
        if config.security.jwt_secret == "your-super-secret-jwt-key-change-in-production":
            raise ValueError("JWT secret must be changed in production")
        
        if "*" in config.security.allowed_origins:
            raise ValueError("CORS origins cannot be '*' in production")
    
    # Validate AI configuration
    if not config.ai.openai_api_key and not config.ai.anthropic_api_key:
        raise ValueError("At least one AI API key must be configured")
    
    print("✅ Configuration validation passed")


if __name__ == "__main__":
    # Validate configuration when run directly
    validate_config()
    print("Configuration loaded successfully:")
    print(f"Environment: {config.environment}")
    print(f"Service: {config.service_name} v{config.service_version}")
    print(f"Host: {config.host}:{config.port}")
    print(f"Database: {config.database.url}")
    print(f"Redis: {config.redis.url}")
    print(f"Message Queue: {config.message_queue.provider}")
    print(f"AI Services: OpenAI={bool(config.ai.openai_api_key)}, Anthropic={bool(config.ai.anthropic_api_key)}") 