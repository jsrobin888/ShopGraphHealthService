"""
Main DealHealthService implementation - Health Graph System for ShopGraph.

This module contains the core service that orchestrates the health calculation
process for promotions based on verification events. It serves as the Health Graph
System within the ShopGraph ecosystem, ensuring reliable promotion data.
"""

import logging
from typing import List, Optional

from .database import DatabaseService, MockDatabase
from .health_calculation_engine import HealthCalculationEngine
from .ai_processor import AIProcessor, AIProcessorConfig
from .message_queue import (
    MessageQueueProcessor,
    MessageQueueConfig,
    EventMessage,
    EventType,
)
from .monitoring import MetricsCollector, trace_function
from .models import (
    AutomatedTestResult,
    CommunityTip,
    CommunityVerification,
    EventProcessingResult,
    HealthCalculationConfig,
    HealthScoreUpdate,
    PromotionState,
    VerificationEvent,
)

logger = logging.getLogger(__name__)


class DealHealthService:
    """
    Health Graph System for ShopGraph - Main service for processing verification events
    and calculating promotion health scores.

    This service orchestrates the entire process of:
    1. Receiving verification events from message queue
    2. Processing events through AI (for community tips)
    3. Calculating health scores using the HealthCalculationEngine
    4. Updating promotion states in the database
    5. Storing event processing results for audit
    6. Monitoring and metrics collection

    The service ensures the accuracy and reliability of promotional data,
    directly impacting user trust and the success of products like SimplyCodes.
    """

    def __init__(self, config: Optional[HealthCalculationConfig] = None):
        """
        Initialize the DealHealthService - Health Graph System.

        Args:
            config: Configuration for health calculation (optional)
        """
        self.config = config or HealthCalculationConfig()

        # Initialize core components
        self.db = MockDatabase()
        self.db_service = DatabaseService(self.db)
        self.health_engine = HealthCalculationEngine(self.config)

        # Initialize AI processor for community tip analysis
        ai_config = AIProcessorConfig(
            provider="mock",  # Will be configurable via environment
            model="gpt-4",
            api_key=None,
        )
        self.ai_processor = AIProcessor(ai_config)

        # Initialize message queue processor for event ingestion
        queue_config = MessageQueueConfig(
            provider="mock",  # Will be configurable via environment
            subscription_name="deal-health-events",
            topic_name="deal-health-events",
        )
        self.queue_processor = MessageQueueProcessor(
            queue_config, self._handle_queue_event
        )

        # Initialize monitoring for observability
        self.metrics = MetricsCollector()

        logger.info(
            "DealHealthService - Health Graph System initialized with config: %s",
            self.config.model_dump(),
        )

    async def start(self):
        """Start the Health Graph System and all components."""
        logger.info("Starting DealHealthService - Health Graph System...")

        # Start message queue processor
        await self.queue_processor.start()

        logger.info("DealHealthService - Health Graph System started successfully")

    async def stop(self):
        """Stop the Health Graph System and all components."""
        logger.info("Stopping DealHealthService - Health Graph System...")

        # Stop message queue processor
        await self.queue_processor.stop()

        # Close AI processor
        await self.ai_processor.close()

        logger.info("DealHealthService - Health Graph System stopped")

    async def _handle_queue_event(self, message: EventMessage) -> dict:
        """
        Handle events from the message queue - part of the Health Graph System.

        Args:
            message: Event message from queue

        Returns:
            Processing result
        """
        try:
            # Convert message to verification event
            event = self._convert_message_to_event(message)

            # Process the event through the health calculation engine
            result = await self.process_single_event(
                message.data.get("promotionId"), event
            )

            # Record metrics for monitoring
            self.metrics.record_event_processed(message.type.value, "success")

            return {"success": True, "result": result}

        except Exception as e:
            logger.error(f"Failed to process queue event {message.id}: {str(e)}")
            self.metrics.record_event_processed(message.type.value, "failed")
            self.metrics.record_error(type(e).__name__, "queue_processor")
            raise

    def _convert_message_to_event(self, message: EventMessage) -> VerificationEvent:
        """Convert queue message to verification event for health calculation."""
        data = message.data

        if message.type == EventType.AUTOMATED_TEST_RESULT:
            return AutomatedTestResult(**data)
        elif message.type == EventType.COMMUNITY_VERIFICATION:
            return CommunityVerification(**data)
        elif message.type == EventType.COMMUNITY_TIP:
            return CommunityTip(**data)
        else:
            raise ValueError(f"Unknown event type: {message.type}")

    @trace_function("process_verification_events")
    async def process_verification_events(
        self, promotion_id: str, events: List[VerificationEvent]
    ) -> HealthScoreUpdate:
        """
        Process verification events for health score calculation.

        This is the core method of the Health Graph System that processes
        events from multiple sources (ACT, BFT, user feedback) to calculate
        real-time health scores for promotions.

        Args:
            promotion_id: ID of the promotion to process
            events: List of verification events to process

        Returns:
            Health score update result
        """
        if not events:
            logger.warning("No events provided for promotion %s", promotion_id)
            return HealthScoreUpdate(
                promotion_id=promotion_id,
                old_score=0,
                new_score=0,
                change_reason="No events to process",
                events_processed=0,
                confidence_score=0.0,
            )

        logger.info(
            "Processing %d events for promotion %s in Health Graph System",
            len(events),
            promotion_id,
        )

        try:
            # Get or create promotion in the health graph
            promotion = await self._get_or_create_promotion_from_events(events[0])

            # Process events individually and track results
            processed_events = []
            old_score = promotion.health_score

            for event in events:
                try:
                    # Process community tips through AI for structured data extraction
                    if isinstance(event, CommunityTip):
                        processed_event = await self._process_community_tip(event)
                    else:
                        processed_event = event

                    processed_events.append(processed_event)

                    # Record event processing metrics
                    event_type = type(event).__name__
                    self.metrics.record_event_processed(event_type, "success")

                except Exception as e:
                    logger.error("Failed to process event: %s", str(e))
                    event_type = type(event).__name__
                    self.metrics.record_event_processed(event_type, "failed")
                    self.metrics.record_error(type(e).__name__, "event_processor")
                    raise

            # Calculate new health score using the health calculation engine
            new_score = self.health_engine.calculate_health_score(processed_events)

            # Update promotion state in the health graph
            await self._update_promotion_state(
                promotion_id, new_score, processed_events
            )

            # Record health score update for monitoring
            self.metrics.record_health_score_update(promotion_id, new_score)

            return HealthScoreUpdate(
                promotion_id=promotion_id,
                old_score=old_score,
                new_score=new_score,
                change_reason=(
                    f"Processed {len(processed_events)} events in Health Graph System"
                ),
                events_processed=len(processed_events),
                confidence_score=self.health_engine.get_confidence_score(
                    processed_events
                ),
            )

        except Exception as e:
            logger.error(
                "Failed to process verification events in Health Graph System: %s",
                str(e),
            )
            self.metrics.record_error(type(e).__name__, "verification_processor")
            raise

    @trace_function("process_single_event")
    async def process_single_event(
        self, promotion_id: str, event: VerificationEvent
    ) -> HealthScoreUpdate:
        """
        Process a single verification event for health score calculation.

        Args:
            promotion_id: ID of the promotion to process
            event: Verification event to process

        Returns:
            Health score update result
        """
        return await self.process_verification_events(promotion_id, [event])

    @trace_function("get_promotion_health")
    async def get_promotion_health(self, promotion_id: str) -> Optional[PromotionState]:
        """
        Get current health information for a promotion from the Health Graph System.

        Args:
            promotion_id: ID of the promotion

        Returns:
            Promotion state or None if not found
        """
        return await self.db_service.get_promotion_state(promotion_id)

    @trace_function("get_promotion_history")
    async def get_promotion_history(
        self, promotion_id: str, limit: int = 50
    ) -> List[EventProcessingResult]:
        """
        Get processing history for a promotion from the Health Graph System.

        Args:
            promotion_id: ID of the promotion
            limit: Maximum number of history entries to return

        Returns:
            List of event processing results
        """
        return await self.db_service.get_promotion_history(promotion_id, limit)

    @trace_function("get_merchant_promotions")
    async def get_merchant_promotions(self, merchant_id: int) -> List[PromotionState]:
        """
        Get all promotions for a merchant from the Health Graph System.

        Args:
            merchant_id: ID of the merchant

        Returns:
            List of promotion states
        """
        return await self.db_service.get_merchant_promotions(merchant_id)

    @trace_function("get_promotions_by_health_range")
    async def get_promotions_by_health_range(
        self, min_health: int, max_health: int
    ) -> List[PromotionState]:
        """
        Get promotions within a health score range from the Health Graph System.

        Args:
            min_health: Minimum health score (inclusive)
            max_health: Maximum health score (inclusive)

        Returns:
            List of promotion states
        """
        return await self.db_service.get_promotions_by_health_range(
            min_health, max_health
        )

    @trace_function("_get_or_create_promotion_from_events")
    async def _get_or_create_promotion_from_events(
        self, event: VerificationEvent
    ) -> PromotionState:
        """
        Get or create promotion state from event data in the Health Graph System.

        Args:
            event: Verification event containing promotion data

        Returns:
            Promotion state
        """
        promotion_id = event.promotionId
        merchant_id = getattr(event, "merchantId", 0)

        # Try to get existing promotion from health graph
        promotion = await self.db_service.get_promotion_state(promotion_id)

        if not promotion:
            # Create new promotion in health graph
            promotion = PromotionState(
                id=promotion_id,
                merchant_id=merchant_id,
                title=f"Promotion {promotion_id}",
                health_score=50,  # Neutral starting score
                confidence_score=0.0,
            )
            await self.db_service.create_promotion(promotion)

        return promotion

    @trace_function("_process_community_tip")
    async def _process_community_tip(self, tip: CommunityTip) -> CommunityTip:
        """
        Process community tip through AI to extract structured data.

        Args:
            tip: Community tip to process

        Returns:
            Processed community tip with structured data
        """
        try:
            # Process through AI for structured data extraction
            ai_result = await self.ai_processor.process_community_tip(
                tip.tipText, getattr(tip, "userReputation", 50)
            )

            # Update tip with structured data from AI processing
            tip.structured_data = ai_result["structured_data"]
            tip.confidence_score = ai_result["confidence_score"]

            # Record AI processing metrics
            self.metrics.record_ai_request(
                "mock", "gpt-4", "success", 0.1  # Mock duration
            )

            return tip

        except Exception as e:
            logger.error("Failed to process community tip: %s", str(e))
            self.metrics.record_ai_request("mock", "gpt-4", "failed", 0.0)
            self.metrics.record_error(type(e).__name__, "ai_processor")

            # Return tip without AI processing
            return tip

    @trace_function("_update_promotion_state")
    async def _update_promotion_state(
        self, promotion_id: str, new_score: int, events: List[VerificationEvent]
    ):
        """
        Update promotion state with new health score and events.

        Args:
            promotion_id: ID of the promotion
            new_score: New health score
            events: Events that led to this score
        """
        # Update promotion health score in the health graph
        await self.db_service.update_promotion_health_score(promotion_id, new_score)

        # Store event processing results for audit trail
        for event in events:
            await self.db_service.store_event_processing_result(
                promotion_id=promotion_id,
                event_type=type(event).__name__,
                event_data=event.dict(),
                health_score_after=new_score,
            )

    @trace_function("batch_process_events")
    async def batch_process_events(
        self, events_by_promotion: dict[str, List[VerificationEvent]]
    ) -> List[HealthScoreUpdate]:
        """
        Process events for multiple promotions in batch for the Health Graph System.

        Args:
            events_by_promotion: Dictionary mapping promotion IDs to event lists

        Returns:
            List of health score updates
        """
        results = []

        for promotion_id, events in events_by_promotion.items():
            try:
                result = await self.process_verification_events(promotion_id, events)
                results.append(result)
            except Exception as e:
                logger.error(
                    "Failed to process events for promotion %s: %s",
                    promotion_id,
                    str(e),
                )
                # Continue processing other promotions
                continue

        return results

    def get_metrics(self) -> str:
        """Get Prometheus metrics for the Health Graph System."""
        return self.metrics.get_metrics()

    def get_queue_stats(self) -> dict:
        """Get message queue statistics for the Health Graph System."""
        return self.queue_processor.get_stats()
