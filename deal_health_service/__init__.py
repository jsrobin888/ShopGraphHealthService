"""
DealHealthService - AI-Powered Deal Health Service for ShopGraph

A microservice that processes verification events from multiple sources
to calculate real-time health scores for promotions in ShopGraph.
"""

__version__ = "1.0.0"
__author__ = "Demand.io Team"
__description__ = "AI-Powered Deal Health Service for ShopGraph"

from .models import (
    AutomatedTestResult,
    CommunityTip,
    CommunityVerification,
    EventType,
    HealthCalculationConfig,
    HealthScoreUpdate,
    PromotionState,
    ServiceConfig,
    VerificationEvent,
)
from .service import DealHealthService

__all__ = [
    "DealHealthService",
    "AutomatedTestResult",
    "CommunityTip", 
    "CommunityVerification",
    "EventType",
    "HealthCalculationConfig",
    "HealthScoreUpdate",
    "PromotionState",
    "ServiceConfig",
    "VerificationEvent",
] 