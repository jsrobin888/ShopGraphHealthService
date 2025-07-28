"""
Health Calculation Engine for the DealHealthService.

This module contains the core business logic for calculating promotion health scores
based on verification events from multiple sources.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .models import (
    AutomatedTestResult,
    CommunityTip,
    CommunityVerification,
    HealthCalculationConfig,
    ProcessedTipResult,
    PromotionState,
    StructuredTipData,
    VerificationEvent,
    EventType,
)


class HealthCalculationEngine:
    """
    Core engine for calculating promotion health scores.
    
    This engine processes verification events from multiple sources and calculates
    a health score (0-100) that represents the likelihood of a promotion working
    for users.
    """
    
    def __init__(self, config: HealthCalculationConfig):
        self.config = config
    
    def calculate_health_score(self, events: List[VerificationEvent]) -> int:
        """
        Calculate health score from a list of verification events.
        
        Args:
            events: List of verification events to process
            
        Returns:
            Health score (0-100)
        """
        if not events:
            return 50  # Neutral score for no events
        
        # Calculate weighted score
        total_weight = 0.0
        weighted_sum = 0.0
        
        for event in events:
            weight = self._get_event_weight(event)
            decay = self._calculate_temporal_decay(event.timestamp)
            adjusted_weight = weight * decay
            
            if adjusted_weight > 0:
                if self._is_positive_event(event):
                    weighted_sum += adjusted_weight
                else:
                    weighted_sum -= adjusted_weight
                
                total_weight += adjusted_weight
        
        if total_weight == 0:
            return 50  # Neutral score
        
        # Calculate raw score and convert to 0-100 scale
        raw_score = weighted_sum / total_weight
        new_score = int((raw_score + 1) * 50)  # Convert from [-1, 1] to [0, 100]
        return max(0, min(100, new_score))
    
    def get_confidence_score(self, events: List[VerificationEvent]) -> float:
        """
        Calculate confidence score for the health calculation.
        
        Args:
            events: List of verification events
            
        Returns:
            Confidence score (0.0-1.0)
        """
        if not events:
            return 0.0
        
        total_weight = 0.0
        event_types = set()
        
        for event in events:
            weight = self._get_event_weight(event)
            decay = self._calculate_temporal_decay(event.timestamp)
            adjusted_weight = weight * decay
            
            if adjusted_weight > 0:
                total_weight += adjusted_weight
                event_types.add(type(event).__name__)
        
        # Base confidence on total weight and event diversity
        weight_confidence = min(1.0, total_weight / 10.0)  # Normalize to 0-1
        diversity_confidence = min(1.0, len(event_types) / 3.0)  # 3 event types max
        
        return (weight_confidence + diversity_confidence) / 2.0
    
    def _get_event_weight(self, event: VerificationEvent) -> float:
        """
        Get the weight for a verification event based on its type and reliability.
        
        Args:
            event: Verification event
            
        Returns:
            Event weight (0.0-1.0)
        """
        base_weight = 0.0
        
        if isinstance(event, AutomatedTestResult):
            base_weight = self.config.automated_test_weight
            # Additional weight based on test success
            if event.success:
                base_weight *= 1.2
            else:
                base_weight *= 0.8
                
        elif isinstance(event, CommunityVerification):
            base_weight = self.config.community_verification_weight
            # Weight by verifier reputation
            reputation_factor = getattr(event, 'verifierReputationScore', 50) / 100.0
            base_weight *= reputation_factor
            
        elif isinstance(event, CommunityTip):
            base_weight = self.config.community_tip_weight
            # Weight by user reputation if available
            user_reputation = getattr(event, 'userReputation', 50)
            reputation_factor = user_reputation / 100.0
            base_weight *= reputation_factor
            
            # Additional weight based on AI confidence if available
            if hasattr(event, 'confidence_score') and event.confidence_score:
                base_weight *= event.confidence_score
        
        return base_weight
    
    def _calculate_temporal_decay(self, event_timestamp: datetime) -> float:
        """
        Calculate temporal decay factor for an event based on its age.
        
        Args:
            event_timestamp: Timestamp of the event
            
        Returns:
            Decay factor (0.0-1.0)
        """
        now = datetime.utcnow()
        age_hours = (now - event_timestamp).total_seconds() / 3600
        
        # Apply exponential decay
        decay_rate = self.config.decay_rate_per_day
        days_old = age_hours / 24
        decay_factor = math.exp(-decay_rate * days_old)
        
        return max(0.0, min(1.0, decay_factor))
    
    def _is_positive_event(self, event: VerificationEvent) -> bool:
        """
        Determine if an event is positive (increases health score) or negative.
        
        Args:
            event: Verification event
            
        Returns:
            True if positive, False if negative
        """
        if isinstance(event, AutomatedTestResult):
            return event.success
            
        elif isinstance(event, CommunityVerification):
            return getattr(event, 'is_valid', True)
            
        elif isinstance(event, CommunityTip):
            # For community tips, check if AI processing indicates positive sentiment
            if hasattr(event, 'structured_data') and event.structured_data:
                effectiveness = event.structured_data.get('effectiveness', 5)
                return effectiveness > 5  # Above neutral
            return True  # Default to positive if no AI processing
            
        return True  # Default to positive for unknown event types 