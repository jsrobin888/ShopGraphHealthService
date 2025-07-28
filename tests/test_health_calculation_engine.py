"""
Unit tests for the Health Calculation Engine.

This module tests the core business logic for calculating promotion health scores
based on verification events from multiple sources.
"""

import pytest
from datetime import datetime, timedelta

from deal_health_service.health_calculation_engine import AIProcessor, HealthCalculationEngine
from deal_health_service.models import (
    AutomatedTestResult,
    CommunityTip,
    CommunityVerification,
    HealthCalculationConfig,
    PromotionState,
    StructuredTipData,
)


class TestHealthCalculationEngine:
    """Test cases for the HealthCalculationEngine."""
    
    @pytest.fixture
    def config(self):
        """Default configuration for testing."""
        return HealthCalculationConfig(
            automated_test_weight=0.6,
            community_verification_weight=0.3,
            community_tip_weight=0.1,
            decay_rate_per_day=0.1,
            max_event_age_days=30
        )
    
    @pytest.fixture
    def engine(self, config):
        """Health calculation engine instance."""
        return HealthCalculationEngine(config)
    
    @pytest.fixture
    def base_promotion(self):
        """Base promotion state for testing."""
        return PromotionState(
            id="TEST_PROMO_001",
            merchant_id=12345,
            title="Test Promotion",
            health_score=50,
            confidence_score=0.0
        )
    
    @pytest.fixture
    def recent_timestamp(self):
        """Recent timestamp for events."""
        return datetime.utcnow()
    
    def test_calculate_health_score_no_events(self, engine, base_promotion):
        """Test health score calculation with no events."""
        new_score, confidence, reason = engine.calculate_health_score(
            base_promotion, []
        )
        
        assert new_score == 50  # Should remain at neutral score
        assert confidence == 0.0  # No confidence without events
        assert "No events to process" in reason
    
    def test_calculate_health_score_single_automated_test_success(self, engine, base_promotion, recent_timestamp):
        """Test health score calculation with successful automated test."""
        event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=True,
            discountValue=20.0,
            timestamp=recent_timestamp
        )
        
        new_score, confidence, reason = engine.calculate_health_score(
            base_promotion, [event]
        )
        
        # Should increase health score due to successful test
        assert new_score > 50
        assert confidence > 0.0
        assert "AutomatedTestResult" in reason
    
    def test_calculate_health_score_single_automated_test_failure(self, engine, base_promotion, recent_timestamp):
        """Test health score calculation with failed automated test."""
        event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=False,
            discountValue=0.0,
            timestamp=recent_timestamp
        )
        
        new_score, confidence, reason = engine.calculate_health_score(
            base_promotion, [event]
        )
        
        # Should decrease health score due to failed test
        assert new_score < 50
        assert confidence > 0.0
        assert "AutomatedTestResult" in reason
    
    def test_calculate_health_score_community_verification_high_reputation(self, engine, base_promotion, recent_timestamp):
        """Test health score calculation with high-reputation community verification."""
        event = CommunityVerification(
            promotionId="TEST_PROMO_001",
            verifierId="user_123",
            verifierReputationScore=95,
            is_valid=True,
            timestamp=recent_timestamp
        )
        
        new_score, confidence, reason = engine.calculate_health_score(
            base_promotion, [event]
        )
        
        # Should increase health score due to high-reputation verification
        assert new_score > 50
        assert confidence > 0.0
        assert "CommunityVerification" in reason
    
    def test_calculate_health_score_community_verification_low_reputation(self, engine, base_promotion, recent_timestamp):
        """Test health score calculation with low-reputation community verification."""
        event = CommunityVerification(
            promotionId="TEST_PROMO_001",
            verifierId="user_456",
            verifierReputationScore=20,
            is_valid=True,
            timestamp=recent_timestamp
        )
        
        new_score, confidence, reason = engine.calculate_health_score(
            base_promotion, [event]
        )
        
        # Should still increase but with lower weight due to low reputation
        assert new_score > 50
        assert confidence > 0.0
        assert "CommunityVerification" in reason
    
    def test_calculate_health_score_conflicting_events(self, engine, base_promotion, recent_timestamp):
        """Test health score calculation with conflicting events."""
        # Successful automated test
        automated_event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=True,
            discountValue=20.0,
            timestamp=recent_timestamp
        )
        
        # Failed community verification
        community_event = CommunityVerification(
            promotionId="TEST_PROMO_001",
            verifierId="user_123",
            verifierReputationScore=80,
            is_valid=False,
            timestamp=recent_timestamp
        )
        
        new_score, confidence, reason = engine.calculate_health_score(
            base_promotion, [automated_event, community_event]
        )
        
        # Should be weighted toward automated test (higher weight)
        assert new_score > 50  # Automated test should dominate
        assert confidence > 0.0
        assert "AutomatedTestResult" in reason
        assert "CommunityVerification" in reason
    
    def test_calculate_health_score_temporal_decay(self, engine, base_promotion):
        """Test that older events have less impact due to temporal decay."""
        # Recent successful test
        recent_event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=True,
            discountValue=20.0,
            timestamp=datetime.utcnow()
        )
        
        # Old successful test (10 days ago)
        old_event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=True,
            discountValue=20.0,
            timestamp=datetime.utcnow() - timedelta(days=10)
        )
        
        # Calculate with recent event only
        recent_score, _, _ = engine.calculate_health_score(
            base_promotion, [recent_event]
        )
        
        # Calculate with old event only
        old_score, _, _ = engine.calculate_health_score(
            base_promotion, [old_event]
        )
        
        # Recent event should have more impact
        assert recent_score > old_score
    
    def test_calculate_health_score_event_diversity_confidence(self, engine, base_promotion, recent_timestamp):
        """Test that confidence increases with event diversity."""
        # Single event type
        single_event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=True,
            discountValue=20.0,
            timestamp=recent_timestamp
        )
        
        # Multiple event types
        automated_event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=True,
            discountValue=20.0,
            timestamp=recent_timestamp
        )
        
        community_event = CommunityVerification(
            promotionId="TEST_PROMO_001",
            verifierId="user_123",
            verifierReputationScore=80,
            is_valid=True,
            timestamp=recent_timestamp
        )
        
        # Calculate confidence with single event type
        _, single_confidence, _ = engine.calculate_health_score(
            base_promotion, [single_event]
        )
        
        # Calculate confidence with multiple event types
        _, diverse_confidence, _ = engine.calculate_health_score(
            base_promotion, [automated_event, community_event]
        )
        
        # Diverse events should have higher confidence
        assert diverse_confidence > single_confidence
    
    def test_calculate_health_score_edge_cases(self, engine, base_promotion, recent_timestamp):
        """Test edge cases in health score calculation."""
        # Test with maximum reputation score
        max_reputation_event = CommunityVerification(
            promotionId="TEST_PROMO_001",
            verifierId="user_max",
            verifierReputationScore=100,
            is_valid=True,
            timestamp=recent_timestamp
        )
        
        new_score, confidence, _ = engine.calculate_health_score(
            base_promotion, [max_reputation_event]
        )
        
        assert new_score > 50
        assert confidence > 0.0
        
        # Test with minimum reputation score
        min_reputation_event = CommunityVerification(
            promotionId="TEST_PROMO_001",
            verifierId="user_min",
            verifierReputationScore=0,
            is_valid=True,
            timestamp=recent_timestamp
        )
        
        new_score, confidence, _ = engine.calculate_health_score(
            base_promotion, [min_reputation_event]
        )
        
        # Should still have some impact but minimal
        assert new_score >= 50
        assert confidence > 0.0
    
    def test_calculate_health_score_with_existing_signals(self, engine, base_promotion, recent_timestamp):
        """Test health score calculation with existing verification signals."""
        # Add existing signals to promotion
        existing_event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=True,
            discountValue=15.0,
            timestamp=recent_timestamp - timedelta(hours=1)
        )
        
        base_promotion.raw_verification_signals = [existing_event.dict()]
        
        # New conflicting event
        new_event = AutomatedTestResult(
            promotionId="TEST_PROMO_001",
            merchantId=12345,
            success=False,
            discountValue=0.0,
            timestamp=recent_timestamp
        )
        
        new_score, confidence, reason = engine.calculate_health_score(
            base_promotion, [new_event]
        )
        
        # Should consider both existing and new events
        assert confidence > 0.0
        assert "AutomatedTestResult" in reason


class TestAIProcessor:
    """Test cases for the AIProcessor."""
    
    @pytest.fixture
    def processor(self):
        """AI processor instance."""
        return AIProcessor()
    
    @pytest.fixture
    def sample_tip(self):
        """Sample community tip for testing."""
        return CommunityTip(
            promotionId="TEST_PROMO_001",
            tipText="This code works great for orders over $50!",
            timestamp=datetime.utcnow(),
            userId="user_123",
            userReputation=85
        )
    
    def test_process_community_tip_positive(self, processor, sample_tip):
        """Test processing a positive community tip."""
        result = processor.process_community_tip(sample_tip)
        
        assert result.structured_data.effectiveness > 5  # Should be positive
        assert result.structured_data.confidence > 0
        assert "Minimum spend required" in result.conditions
        assert result.health_impact > 0  # Should have positive impact
    
    def test_process_community_tip_negative(self, processor):
        """Test processing a negative community tip."""
        negative_tip = CommunityTip(
            promotionId="TEST_PROMO_001",
            tipText="This code is expired and doesn't work anymore",
            timestamp=datetime.utcnow(),
            userId="user_456",
            userReputation=70
        )
        
        result = processor.process_community_tip(negative_tip)
        
        assert result.structured_data.effectiveness < 5  # Should be negative
        assert result.structured_data.confidence > 0
        assert "Code may be expired" in result.exclusions
        assert result.health_impact < 0  # Should have negative impact
    
    def test_process_community_tip_neutral(self, processor):
        """Test processing a neutral community tip."""
        neutral_tip = CommunityTip(
            promotionId="TEST_PROMO_001",
            tipText="This code might work, not sure about the conditions",
            timestamp=datetime.utcnow(),
            userId="user_789",
            userReputation=50
        )
        
        result = processor.process_community_tip(neutral_tip)
        
        assert result.structured_data.effectiveness == 5  # Should be neutral
        assert result.structured_data.confidence == 5  # Medium confidence
        assert result.health_impact == 0  # Should have no impact
    
    def test_process_community_tip_with_conditions(self, processor):
        """Test processing a tip with specific conditions."""
        conditional_tip = CommunityTip(
            promotionId="TEST_PROMO_001",
            tipText="Only works on sale items and excludes electronics",
            timestamp=datetime.utcnow(),
            userId="user_101",
            userReputation=90
        )
        
        result = processor.process_community_tip(conditional_tip)
        
        assert "Only works on sale items" in result.conditions
        assert "Some items excluded" in result.exclusions
        assert result.structured_data.effectiveness < 5  # Should be slightly negative due to exclusions
    
    def test_process_community_tip_user_reputation_impact(self, processor):
        """Test that user reputation affects health impact."""
        # High reputation user
        high_reputation_tip = CommunityTip(
            promotionId="TEST_PROMO_001",
            tipText="Works great!",
            timestamp=datetime.utcnow(),
            userId="user_high",
            userReputation=95
        )
        
        # Low reputation user
        low_reputation_tip = CommunityTip(
            promotionId="TEST_PROMO_001",
            tipText="Works great!",
            timestamp=datetime.utcnow(),
            userId="user_low",
            userReputation=20
        )
        
        high_result = processor.process_community_tip(high_reputation_tip)
        low_result = processor.process_community_tip(low_reputation_tip)
        
        # High reputation should have more impact
        assert abs(high_result.health_impact) > abs(low_result.health_impact)
    
    def test_process_community_tip_no_user_reputation(self, processor):
        """Test processing tip without user reputation."""
        tip_no_reputation = CommunityTip(
            promotionId="TEST_PROMO_001",
            tipText="This code works great!",
            timestamp=datetime.utcnow(),
            userId="user_unknown"
        )
        
        result = processor.process_community_tip(tip_no_reputation)
        
        # Should still process successfully
        assert result.structured_data.effectiveness > 5
        assert result.health_impact > 0
        assert result.conditions == []
        assert result.exclusions == []


class TestHealthCalculationConfig:
    """Test cases for the HealthCalculationConfig."""
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = HealthCalculationConfig(
            automated_test_weight=0.6,
            community_verification_weight=0.3,
            community_tip_weight=0.1
        )
        
        assert config.automated_test_weight == 0.6
        assert config.community_verification_weight == 0.3
        assert config.community_tip_weight == 0.1
        assert config.total_weight == 1.0
    
    def test_config_invalid_weights(self):
        """Test that invalid weights raise validation errors."""
        with pytest.raises(ValueError):
            HealthCalculationConfig(automated_test_weight=1.5)  # > 1.0
        
        with pytest.raises(ValueError):
            HealthCalculationConfig(community_verification_weight=-0.1)  # < 0.0
    
    def test_config_total_weight_property(self):
        """Test the total_weight property calculation."""
        config = HealthCalculationConfig(
            automated_test_weight=0.5,
            community_verification_weight=0.3,
            community_tip_weight=0.1
        )
        
        assert config.total_weight == 0.9  # Should sum to 0.9 