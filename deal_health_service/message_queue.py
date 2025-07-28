"""
Message Queue Integration Module.

This module handles event ingestion from Google Cloud Pub/Sub with proper
error handling, retry logic, and dead letter queue management.
"""

import asyncio
import logging
from typing import Callable, Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Supported event types."""

    AUTOMATED_TEST_RESULT = "AutomatedTestResult"
    COMMUNITY_VERIFICATION = "CommunityVerification"
    COMMUNITY_TIP = "CommunityTip"


class MessageQueueConfig(BaseModel):
    """Configuration for message queue integration."""

    provider: str = "pubsub"  # pubsub, mock
    project_id: Optional[str] = None
    subscription_name: str = "deal-health-events"
    topic_name: str = "deal-health-events"
    credentials_path: Optional[str] = None

    # Retry configuration
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    max_retry_delay_seconds: float = 60.0

    # Processing configuration
    batch_size: int = 10
    max_concurrent_messages: int = 5
    ack_deadline_seconds: int = 60

    # Dead letter queue
    enable_dlq: bool = True
    dlq_topic_name: str = "deal-health-events-dlq"
    max_delivery_attempts: int = 3


class EventMessage(BaseModel):
    """Event message structure."""

    id: str
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime
    source: str
    correlation_id: Optional[str] = None
    delivery_attempts: int = 0


class MessageQueueProcessor:
    """
    Message queue processor for event ingestion.

    Handles Google Cloud Pub/Sub integration with proper error handling,
    retry logic, and dead letter queue management.
    """

    def __init__(self, config: MessageQueueConfig, event_handler: Callable):
        """
        Initialize message queue processor.

        Args:
            config: Message queue configuration
            event_handler: Function to handle processed events
        """
        self.config = config
        self.event_handler = event_handler
        self.client = None
        self.is_running = False
        self.processing_tasks: List[asyncio.Task] = []

        # Statistics
        self.stats = {
            "messages_processed": 0,
            "messages_failed": 0,
            "messages_retried": 0,
            "dlq_messages": 0,
        }

    async def start(self):
        """Start the message queue processor."""
        logger.info("Starting message queue processor...")
        self.is_running = True

        if self.config.provider == "pubsub":
            await self._setup_pubsub_client()
        else:
            await self._setup_mock_client()

        # Start processing loop
        asyncio.create_task(self._processing_loop())
        logger.info("Message queue processor started")

    async def stop(self):
        """Stop the message queue processor."""
        logger.info("Stopping message queue processor...")
        self.is_running = False

        # Cancel all processing tasks
        for task in self.processing_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.processing_tasks:
            await asyncio.gather(*self.processing_tasks, return_exceptions=True)

        # Close client
        if self.client:
            await self.client.aclose()

        logger.info("Message queue processor stopped")

    async def _setup_pubsub_client(self):
        """Setup Google Cloud Pub/Sub client."""
        try:
            # In production, use google-cloud-pubsub library
            # For now, we'll use a mock implementation
            self.client = MockPubSubClient(self.config)
            logger.info("Pub/Sub client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Pub/Sub client: {str(e)}")
            raise

    async def _setup_mock_client(self):
        """Setup mock client for development/testing."""
        self.client = MockPubSubClient(self.config)
        logger.info("Mock Pub/Sub client initialized")

    async def _processing_loop(self):
        """Main processing loop."""
        while self.is_running:
            try:
                # Pull messages from queue
                messages = await self.client.pull_messages(
                    max_messages=self.config.batch_size
                )

                if messages:
                    # Process messages concurrently
                    tasks = []
                    for message in messages:
                        task = asyncio.create_task(self._process_message(message))
                        tasks.append(task)

                    # Wait for all messages to be processed
                    await asyncio.gather(*tasks, return_exceptions=True)

                    # Update processing tasks list
                    self.processing_tasks = [t for t in tasks if not t.done()]

                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in processing loop: {str(e)}")
                await asyncio.sleep(1)  # Wait before retrying

    async def _process_message(self, message: EventMessage):
        """Process a single message with retry logic."""
        try:
            # Validate message
            if not self._validate_message(message):
                logger.warning(f"Invalid message format: {message.id}")
                await self._acknowledge_message(message.id)
                return

            # Process message
            await self.event_handler(message)

            # Acknowledge successful processing
            await self._acknowledge_message(message.id)

            # Update statistics
            self.stats["messages_processed"] += 1

            logger.debug(f"Successfully processed message: {message.id}")

        except Exception as e:
            logger.error(f"Failed to process message {message.id}: {str(e)}")

            # Handle retry logic
            if message.delivery_attempts < self.config.max_delivery_attempts:
                await self._retry_message(message, e)
            else:
                await self._send_to_dlq(message, e)

    def _validate_message(self, message: EventMessage) -> bool:
        """Validate message format and content."""
        try:
            # Check required fields
            if not message.id or not message.type or not message.data:
                return False

            # Validate event type
            if message.type not in EventType:
                return False

            # Validate timestamp
            if not isinstance(message.timestamp, datetime):
                return False

            return True

        except Exception:
            return False

    async def _retry_message(self, message: EventMessage, error: Exception):
        """Retry message processing with exponential backoff."""
        message.delivery_attempts += 1

        # Calculate delay with exponential backoff
        delay = min(
            self.config.retry_delay_seconds * (2 ** (message.delivery_attempts - 1)),
            self.config.max_retry_delay_seconds,
        )

        logger.info(
            f"Retrying message {message.id} in {delay}s "
            f"(attempt {message.delivery_attempts})"
        )

        # Schedule retry
        asyncio.create_task(self._delayed_retry(message, delay))

        # Update statistics
        self.stats["messages_retried"] += 1

    async def _delayed_retry(self, message: EventMessage, delay: float):
        """Retry message after delay."""
        await asyncio.sleep(delay)

        # Re-queue message for processing
        await self.client.publish_message(message)

    async def _send_to_dlq(self, message: EventMessage, error: Exception):
        """Send message to dead letter queue."""
        if not self.config.enable_dlq:
            logger.error(f"Message {message.id} failed permanently, DLQ disabled")
            await self._acknowledge_message(message.id)
            return

        try:
            # Add error information to message
            dlq_message = EventMessage(
                id=f"dlq_{message.id}",
                type=message.type,
                data={
                    **message.data,
                    "original_message_id": message.id,
                    "error": str(error),
                    "failed_at": datetime.utcnow().isoformat(),
                    "delivery_attempts": message.delivery_attempts,
                },
                timestamp=datetime.utcnow(),
                source="dlq",
                correlation_id=message.correlation_id,
            )

            # Publish to DLQ
            await self.client.publish_to_dlq(dlq_message)

            # Acknowledge original message
            await self._acknowledge_message(message.id)

            # Update statistics
            self.stats["dlq_messages"] += 1
            self.stats["messages_failed"] += 1

            logger.warning(
                f"Message {message.id} sent to DLQ after "
                f"{message.delivery_attempts} attempts"
            )

        except Exception as dlq_error:
            logger.error(
                f"Failed to send message {message.id} to DLQ: {str(dlq_error)}"
            )
            # Still acknowledge to prevent infinite retries
            await self._acknowledge_message(message.id)

    async def _acknowledge_message(self, message_id: str):
        """Acknowledge message processing."""
        try:
            await self.client.acknowledge_message(message_id)
        except Exception as e:
            logger.error(f"Failed to acknowledge message {message_id}: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            **self.stats,
            "is_running": self.is_running,
            "active_tasks": len(self.processing_tasks),
        }


class MockPubSubClient:
    """Mock Pub/Sub client for development/testing."""

    def __init__(self, config: MessageQueueConfig):
        self.config = config
        self.messages = []
        self.dlq_messages = []

    async def pull_messages(self, max_messages: int) -> List[EventMessage]:
        """Pull messages from queue (mock implementation)."""
        # Simulate message arrival
        if not self.messages:
            # Generate mock messages for testing
            await self._generate_mock_messages()

        # Return up to max_messages
        pulled_messages = self.messages[:max_messages]
        self.messages = self.messages[max_messages:]

        return pulled_messages

    async def publish_message(self, message: EventMessage):
        """Publish message to queue."""
        self.messages.append(message)

    async def publish_to_dlq(self, message: EventMessage):
        """Publish message to dead letter queue."""
        self.dlq_messages.append(message)

    async def acknowledge_message(self, message_id: str):
        """Acknowledge message processing."""
        # In mock implementation, just log
        logger.debug(f"Acknowledged message: {message_id}")

    async def _generate_mock_messages(self):
        """Generate mock messages for testing."""
        mock_events = [
            {
                "type": EventType.AUTOMATED_TEST_RESULT,
                "data": {
                    "promotionId": "TEST_PROMO_001",
                    "merchantId": 12345,
                    "success": True,
                    "discountValue": 20.0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "testDuration": 3000,
                    "testEnvironment": "production",
                },
            },
            {
                "type": EventType.COMMUNITY_VERIFICATION,
                "data": {
                    "promotionId": "TEST_PROMO_002",
                    "verifierId": "user_123",
                    "verifierReputationScore": 85,
                    "is_valid": True,
                    "timestamp": datetime.utcnow().isoformat(),
                    "verificationMethod": "manual_checkout",
                    "notes": "Successfully applied discount",
                },
            },
            {
                "type": EventType.COMMUNITY_TIP,
                "data": {
                    "promotionId": "TEST_PROMO_003",
                    "tipText": (
                        "This code works great! Just make sure to spend at least $25."
                    ),
                    "timestamp": datetime.utcnow().isoformat(),
                    "userId": "user_456",
                    "userReputation": 75,
                },
            },
        ]

        for i, event in enumerate(mock_events):
            message = EventMessage(
                id=f"msg_{i}_{datetime.utcnow().timestamp()}",
                type=event["type"],
                data=event["data"],
                timestamp=datetime.utcnow(),
                source="mock",
                correlation_id=f"corr_{i}",
            )
            self.messages.append(message)
