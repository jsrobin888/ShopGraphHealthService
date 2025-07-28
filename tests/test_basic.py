"""
Basic tests to verify the project setup and imports work correctly.
"""

import pytest

from deal_health_service.models import (
    AutomatedTestResult,
    CommunityTip,
    CommunityVerification,
    EventType,
    HealthCalculationConfig,
    PromotionState,
)
from deal_health_service.service import DealHealthService


def test_imports_work():
    """Test that all imports work correctly."""
    assert AutomatedTestResult is not None
    assert CommunityTip is not None
    assert CommunityVerification is not None
    assert EventType is not None
    assert HealthCalculationConfig is not None
    assert PromotionState is not None
    assert DealHealthService is not None


def test_event_types():
    """Test that event types are correctly defined."""
    assert EventType.AUTOMATED_TEST_RESULT == "AutomatedTestResult"
    assert EventType.COMMUNITY_VERIFICATION == "CommunityVerification"
    assert EventType.COMMUNITY_TIP == "CommunityTip"


def test_health_calculation_config_defaults():
    """Test that HealthCalculationConfig has correct defaults."""
    config = HealthCalculationConfig()
    
    assert config.automated_test_weight == 0.6
    assert config.community_verification_weight == 0.3
    assert config.community_tip_weight == 0.1
    assert config.decay_rate_per_day == 0.1
    assert config.max_event_age_days == 30


def test_promotion_state_defaults():
    """Test that PromotionState has correct defaults."""
    promotion = PromotionState(
        id="TEST_001",
        merchant_id=12345,
        title="Test Promotion"
    )
    
    assert promotion.health_score == 50
    assert promotion.confidence_score == 0.0
    assert promotion.total_verifications == 0
    assert promotion.successful_verifications == 0


def test_service_initialization():
    """Test that DealHealthService can be initialized."""
    service = DealHealthService()
    assert service is not None
    assert service.config is not None
    assert service.db is not None
    assert service.db_service is not None
    assert service.health_engine is not None
    assert service.ai_processor is not None


@pytest.mark.asyncio
async def test_service_basic_functionality():
    """Test basic service functionality."""
    service = DealHealthService()
    
    # Test that we can get a promotion (should return None for non-existent)
    promotion = await service.get_promotion_health("NON_EXISTENT")
    assert promotion is None
    
    # Test that we can get merchant promotions (should return empty list)
    promotions = await service.get_merchant_promotions(99999)
    assert isinstance(promotions, list)
    assert len(promotions) == 0 