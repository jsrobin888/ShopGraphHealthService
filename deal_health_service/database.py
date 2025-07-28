"""
Database layer for the DealHealthService.

This module provides a mocked database interface for storing and retrieving
promotion states and verification events.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from .models import (
    EventProcessingResult,
    EventType,
    PromotionState,
    VerificationEvent,
)


class MockDatabase:
    """
    Mock database implementation for demonstration purposes.
    
    In production, this would be replaced with actual PostgreSQL operations
    using asyncpg or SQLAlchemy.
    """
    
    def __init__(self):
        # In-memory storage for demo
        self.promotions: Dict[str, PromotionState] = {}
        self.events: List[EventProcessingResult] = []
        self._lock = asyncio.Lock()
    
    async def get_promotion(self, promotion_id: str) -> Optional[PromotionState]:
        """Get a promotion by ID."""
        async with self._lock:
            return self.promotions.get(promotion_id)
    
    async def create_promotion(self, promotion: PromotionState) -> PromotionState:
        """Create a new promotion."""
        async with self._lock:
            if promotion.id in self.promotions:
                raise ValueError(f"Promotion {promotion.id} already exists")
            
            self.promotions[promotion.id] = promotion
            return promotion
    
    async def update_promotion(self, promotion: PromotionState) -> PromotionState:
        """Update an existing promotion."""
        async with self._lock:
            if promotion.id not in self.promotions:
                raise ValueError(f"Promotion {promotion.id} not found")
            
            promotion.updated_at = datetime.utcnow()
            self.promotions[promotion.id] = promotion
            return promotion
    
    async def store_event_result(self, result: EventProcessingResult) -> EventProcessingResult:
        """Store an event processing result."""
        async with self._lock:
            result.event_id = str(uuid4())
            self.events.append(result)
            return result
    
    async def get_recent_events(
        self, 
        promotion_id: str, 
        limit: int = 100
    ) -> List[EventProcessingResult]:
        """Get recent events for a promotion."""
        async with self._lock:
            events = [
                e for e in self.events 
                if e.promotion_id == promotion_id
            ]
            # Sort by processed_at descending and limit
            events.sort(key=lambda e: e.processed_at, reverse=True)
            return events[:limit]
    
    async def get_promotions_by_merchant(
        self, 
        merchant_id: int
    ) -> List[PromotionState]:
        """Get all promotions for a merchant."""
        async with self._lock:
            return [
                p for p in self.promotions.values()
                if p.merchant_id == merchant_id
            ]
    
    async def get_promotions_by_health_range(
        self, 
        min_health: int, 
        max_health: int
    ) -> List[PromotionState]:
        """Get promotions within a health score range."""
        async with self._lock:
            return [
                p for p in self.promotions.values()
                if min_health <= p.health_score <= max_health
            ]


class DatabaseService:
    """
    High-level database service that provides business logic operations
    on top of the database layer.
    """
    
    def __init__(self, db: MockDatabase):
        self.db = db
    
    async def get_or_create_promotion(
        self, 
        promotion_id: str, 
        merchant_id: int, 
        title: str, 
        code: Optional[str] = None
    ) -> PromotionState:
        """
        Get an existing promotion or create a new one.
        
        Args:
            promotion_id: Unique promotion identifier
            merchant_id: ID of the merchant
            title: Promotion title
            code: Optional promotion code
            
        Returns:
            Promotion state
        """
        promotion = await self.db.get_promotion(promotion_id)
        
        if promotion is None:
            promotion = PromotionState(
                id=promotion_id,
                merchant_id=merchant_id,
                title=title,
                code=code,
                health_score=50,  # Neutral starting score
                confidence_score=0.0
            )
            await self.db.create_promotion(promotion)
        
        return promotion
    
    async def get_promotion_state(self, promotion_id: str) -> Optional[PromotionState]:
        """
        Get promotion state by ID.
        
        Args:
            promotion_id: Promotion identifier
            
        Returns:
            Promotion state or None if not found
        """
        return await self.db.get_promotion(promotion_id)
    
    async def create_promotion(self, promotion: PromotionState) -> PromotionState:
        """
        Create a new promotion.
        
        Args:
            promotion: Promotion state to create
            
        Returns:
            Created promotion state
        """
        return await self.db.create_promotion(promotion)
    
    async def update_promotion_health_score(self, promotion_id: str, new_score: int) -> PromotionState:
        """
        Update promotion health score.
        
        Args:
            promotion_id: Promotion identifier
            new_score: New health score
            
        Returns:
            Updated promotion state
        """
        promotion = await self.db.get_promotion(promotion_id)
        if not promotion:
            raise ValueError(f"Promotion {promotion_id} not found")
        
        promotion.health_score = new_score
        promotion.updated_at = datetime.utcnow()
        
        return await self.db.update_promotion(promotion)
    
    async def update_promotion_health(
        self, 
        promotion_id: str, 
        new_health_score: int, 
        new_confidence_score: float,
        new_events: List[VerificationEvent]
    ) -> PromotionState:
        """
        Update promotion health information.
        
        Args:
            promotion_id: Promotion identifier
            new_health_score: New health score
            new_confidence_score: New confidence score
            new_events: List of new verification events
            
        Returns:
            Updated promotion state
        """
        promotion = await self.db.get_promotion(promotion_id)
        if not promotion:
            raise ValueError(f"Promotion {promotion_id} not found")
        
        # Update health score and confidence
        promotion.health_score = new_health_score
        promotion.confidence_score = new_confidence_score
        promotion.updated_at = datetime.utcnow()
        
        # Add new events to raw verification signals
        for event in new_events:
            signal_data = {
                "type": type(event).__name__,
                "timestamp": event.timestamp.isoformat(),
                "data": event.dict()
            }
            promotion.raw_verification_signals.append(signal_data)
        
        # Update last verification information
        if new_events:
            latest_event = max(new_events, key=lambda e: e.timestamp)
            promotion.last_verified_at = latest_event.timestamp
            promotion.last_verification_source = type(latest_event).__name__
        
        return await self.db.update_promotion(promotion)
    
    async def store_event_processing_result(
        self, 
        promotion_id: str, 
        event_type: str,
        event_data: dict,
        health_score_after: int,
        health_score_before: Optional[int] = None
    ) -> EventProcessingResult:
        """
        Store event processing result.
        
        Args:
            promotion_id: Promotion identifier
            event_type: Type of event processed
            event_data: Event data
            health_score_after: Health score after processing
            health_score_before: Health score before processing (optional)
            
        Returns:
            Event processing result
        """
        result = EventProcessingResult(
            promotion_id=promotion_id,
            event_type=event_type,
            event_data=event_data,
            processed_at=datetime.utcnow(),
            health_score_before=health_score_before,
            health_score_after=health_score_after,
            success=True
        )
        
        return await self.db.store_event_result(result)
    
    async def get_promotion_history(
        self, 
        promotion_id: str, 
        limit: int = 50
    ) -> List[EventProcessingResult]:
        """
        Get promotion processing history.
        
        Args:
            promotion_id: Promotion identifier
            limit: Maximum number of history entries
            
        Returns:
            List of event processing results
        """
        return await self.db.get_recent_events(promotion_id, limit)
    
    async def get_merchant_promotions(self, merchant_id: int) -> List[PromotionState]:
        """
        Get all promotions for a merchant.
        
        Args:
            merchant_id: Merchant identifier
            
        Returns:
            List of promotion states
        """
        return await self.db.get_promotions_by_merchant(merchant_id)
    
    async def get_promotions_by_health_range(
        self, 
        min_health: int, 
        max_health: int
    ) -> List[PromotionState]:
        """
        Get promotions within a health score range.
        
        Args:
            min_health: Minimum health score (inclusive)
            max_health: Maximum health score (inclusive)
            
        Returns:
            List of promotion states
        """
        return await self.db.get_promotions_by_health_range(min_health, max_health) 