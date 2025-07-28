"""
Data models for the DealHealthService.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, ConfigDict


class EventType(str, Enum):
    """Types of verification events."""

    AUTOMATED_TEST_RESULT = "AutomatedTestResult"
    COMMUNITY_VERIFICATION = "CommunityVerification"
    COMMUNITY_TIP = "CommunityTip"


class BaseEvent(BaseModel):
    """Base class for all verification events."""

    type: EventType
    promotionId: str
    timestamp: datetime

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class AutomatedTestResult(BaseEvent):
    """Event from automated testing system (ACT)."""

    type: EventType = EventType.AUTOMATED_TEST_RESULT
    merchantId: int
    success: bool
    discountValue: float
    testDuration: Optional[int] = None  # milliseconds
    errorMessage: Optional[str] = None
    testEnvironment: Optional[str] = None

    def is_positive(self) -> bool:
        """Return True if this event indicates a healthy promotion."""
        return self.success


class CommunityVerification(BaseEvent):
    """Event from community verification (BFT)."""

    type: EventType = EventType.COMMUNITY_VERIFICATION
    verifierId: str
    verifierReputationScore: int = Field(ge=0, le=100)
    is_valid: bool
    verificationMethod: Optional[str] = None
    notes: Optional[str] = None

    def is_positive(self) -> bool:
        """Return True if this event indicates a healthy promotion."""
        return self.is_valid


class StructuredTipData(BaseModel):
    """Structured data extracted from community tips via AI."""

    conditions: List[str] = []
    exclusions: List[str] = []
    effectiveness: int = Field(
        ge=1, le=10
    )  # How well the tip suggests the promotion works
    confidence: int = Field(ge=1, le=10)  # AI confidence in this analysis


class CommunityTip(BaseEvent):
    """Event from community tips (natural language feedback)."""

    type: EventType = EventType.COMMUNITY_TIP
    tipText: str
    userId: Optional[str] = None
    userReputation: Optional[int] = Field(None, ge=0, le=100)
    structured_data: Optional[StructuredTipData] = None  # <-- Added field
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)  # <-- Added field

    def is_positive(self) -> bool:
        """Community tips are processed through AI, so we don't know initially."""
        return True  # Will be determined by AI processing


# Union type for all events
VerificationEvent = Union[AutomatedTestResult, CommunityVerification, CommunityTip]


class ProcessedTipResult(BaseModel):
    """Result of processing a community tip through AI."""

    structured_data: StructuredTipData
    health_impact: float  # Impact on health score (-1 to 1)
    conditions: List[str]
    exclusions: List[str]


class PromotionState(BaseModel):
    """Current state of a promotion in the database."""

    id: str
    merchant_id: int
    title: str
    code: Optional[str] = None
    health_score: int = Field(default=50, ge=0, le=100)
    raw_verification_signals: List[Dict] = Field(default_factory=list)
    last_verified_at: Optional[datetime] = None
    last_verification_source: Optional[str] = None
    total_verifications: int = 0
    successful_verifications: int = 0
    last_automated_test_at: Optional[datetime] = None
    last_community_verification_at: Optional[datetime] = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class HealthScoreUpdate(BaseModel):
    """Result of health score calculation."""

    promotion_id: str
    old_score: int
    new_score: int
    change_reason: str
    events_processed: int
    confidence_score: float


class EventProcessingResult(BaseModel):
    """Result of processing a verification event."""

    event_id: str
    promotion_id: str
    event_type: EventType
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    health_score_before: int
    health_score_after: int
    success: bool
    error_message: Optional[str] = None

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class HealthCalculationConfig(BaseModel):
    """Configuration for health score calculation."""

    # Event weights
    automated_test_weight: float = 0.6
    community_verification_weight: float = 0.3
    community_tip_weight: float = 0.1

    # Temporal decay
    decay_rate_per_day: float = 0.1  # 10% decay per day

    # Minimum confidence thresholds
    min_confidence_for_positive: float = 0.3
    min_confidence_for_negative: float = 0.3

    # Event age limits
    max_event_age_days: int = 30

    @field_validator(
        "automated_test_weight", "community_verification_weight", "community_tip_weight"
    )
    @classmethod
    def validate_weights(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Weights must be between 0 and 1")
        return v

    @property
    def total_weight(self) -> float:
        """Total of all weights (should be <= 1)."""
        return (
            self.automated_test_weight
            + self.community_verification_weight
            + self.community_tip_weight
        )


class ServiceConfig(BaseModel):
    """Configuration for the DealHealthService."""

    # Database
    database_url: str = "postgresql://user:password@localhost/deal_health"
    redis_url: str = "redis://localhost:6379"

    # Processing
    batch_size: int = 100
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Health calculation
    health_calculation: HealthCalculationConfig = Field(
        default_factory=HealthCalculationConfig
    )

    # Monitoring
    metrics_port: int = 9090
    log_level: str = "INFO"
