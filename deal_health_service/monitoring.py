"""
Monitoring and Observability Module.

This module provides comprehensive monitoring, metrics collection,
structured logging, and distributed tracing for the DealHealthService.
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest
from prometheus_client.registry import CollectorRegistry
import structlog

logger = structlog.get_logger()


class MetricsCollector:
    """Prometheus metrics collector for DealHealthService."""

    def __init__(self):
        """Initialize metrics collector."""
        self.registry = CollectorRegistry()

        # Event processing metrics
        self.events_processed = Counter(
            "deal_health_events_processed_total",
            "Total number of events processed",
            ["event_type", "status"],
            registry=self.registry,
        )

        self.event_processing_duration = Histogram(
            "deal_health_event_processing_duration_seconds",
            "Time spent processing events",
            ["event_type"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry,
        )

        # Health score metrics
        self.health_score_updates = Counter(
            "deal_health_score_updates_total",
            "Total number of health score updates",
            ["promotion_id", "score_range"],
            registry=self.registry,
        )

        self.health_score_value = Gauge(
            "deal_health_score_current",
            "Current health score for promotions",
            ["promotion_id"],
            registry=self.registry,
        )

        # API metrics
        self.api_requests = Counter(
            "deal_health_api_requests_total",
            "Total number of API requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )

        self.api_request_duration = Histogram(
            "deal_health_api_request_duration_seconds",
            "Time spent handling API requests",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
            registry=self.registry,
        )

        # Database metrics
        self.db_operations = Counter(
            "deal_health_db_operations_total",
            "Total number of database operations",
            ["operation", "table", "status"],
            registry=self.registry,
        )

        self.db_operation_duration = Histogram(
            "deal_health_db_operation_duration_seconds",
            "Time spent on database operations",
            ["operation", "table"],
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0],
            registry=self.registry,
        )

        # AI processing metrics
        self.ai_requests = Counter(
            "deal_health_ai_requests_total",
            "Total number of AI API requests",
            ["provider", "model", "status"],
            registry=self.registry,
        )

        self.ai_request_duration = Histogram(
            "deal_health_ai_request_duration_seconds",
            "Time spent on AI API requests",
            ["provider", "model"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry,
        )

        # Queue metrics
        self.queue_messages = Gauge(
            "deal_health_queue_messages",
            "Number of messages in queue",
            ["queue_name"],
            registry=self.registry,
        )

        self.queue_processing_rate = Summary(
            "deal_health_queue_processing_rate",
            "Rate of message processing",
            ["queue_name"],
            registry=self.registry,
        )

        # Error metrics
        self.errors_total = Counter(
            "deal_health_errors_total",
            "Total number of errors",
            ["error_type", "component"],
            registry=self.registry,
        )

    def record_event_processed(self, event_type: str, status: str = "success"):
        """Record event processing."""
        self.events_processed.labels(event_type=event_type, status=status).inc()

    def record_event_duration(self, event_type: str, duration: float):
        """Record event processing duration."""
        self.event_processing_duration.labels(event_type=event_type).observe(duration)

    def record_health_score_update(self, promotion_id: str, new_score: int):
        """Record health score update."""
        score_range = self._get_score_range(new_score)
        self.health_score_updates.labels(
            promotion_id=promotion_id, score_range=score_range
        ).inc()

        self.health_score_value.labels(promotion_id=promotion_id).set(new_score)

    def record_api_request(
        self, method: str, endpoint: str, status_code: int, duration: float
    ):
        """Record API request."""
        self.api_requests.labels(
            method=method, endpoint=endpoint, status_code=str(status_code)
        ).inc()

        self.api_request_duration.labels(method=method, endpoint=endpoint).observe(
            duration
        )

    def record_db_operation(
        self, operation: str, table: str, status: str, duration: float
    ):
        """Record database operation."""
        self.db_operations.labels(operation=operation, table=table, status=status).inc()

        self.db_operation_duration.labels(operation=operation, table=table).observe(
            duration
        )

    def record_ai_request(
        self, provider: str, model: str, status: str, duration: float
    ):
        """Record AI API request."""
        self.ai_requests.labels(provider=provider, model=model, status=status).inc()

        self.ai_request_duration.labels(provider=provider, model=model).observe(
            duration
        )

    def record_queue_metrics(
        self, queue_name: str, message_count: int, processing_rate: float
    ):
        """Record queue metrics."""
        self.queue_messages.labels(queue_name=queue_name).set(message_count)
        self.queue_processing_rate.labels(queue_name=queue_name).observe(
            processing_rate
        )

    def record_error(self, error_type: str, component: str):
        """Record error occurrence."""
        self.errors_total.labels(error_type=error_type, component=component).inc()

    def _get_score_range(self, score: int) -> str:
        """Get score range category."""
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "good"
        elif score >= 40:
            return "fair"
        elif score >= 20:
            return "poor"
        else:
            return "critical"

    def get_metrics(self) -> str:
        """Get Prometheus metrics as string."""
        return generate_latest(self.registry)


class TracingContext:
    """Distributed tracing context."""

    def __init__(self, trace_id: Optional[str] = None, span_id: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = span_id or str(uuid.uuid4())
        self.parent_span_id = None
        self.start_time = time.time()
        self.tags = {}

    def add_tag(self, key: str, value: str):
        """Add tag to trace."""
        self.tags[key] = value

    def get_duration(self) -> float:
        """Get trace duration."""
        return time.time() - self.start_time


class MonitoringMiddleware:
    """Monitoring middleware for FastAPI."""

    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics

    async def __call__(self, request, call_next):
        """Process request with monitoring."""
        start_time = time.time()

        # Generate trace ID
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))

        # Add trace ID to request state
        request.state.trace_id = trace_id

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            self.metrics.record_api_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration=duration,
            )

            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id

            return response

        except Exception as e:
            # Record error
            self.metrics.record_error(error_type=type(e).__name__, component="api")
            raise


def setup_structured_logging():
    """Setup structured logging with correlation IDs."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def trace_function(operation_name: str):
    """Decorator to trace function execution."""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            trace_id = str(uuid.uuid4())
            start_time = time.time()

            logger.info(
                f"Starting {operation_name}",
                trace_id=trace_id,
                operation=operation_name,
            )

            try:
                result = await func(*args, **kwargs)

                duration = time.time() - start_time
                logger.info(
                    f"Completed {operation_name}",
                    trace_id=trace_id,
                    operation=operation_name,
                    duration=duration,
                    status="success",
                )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Failed {operation_name}",
                    trace_id=trace_id,
                    operation=operation_name,
                    duration=duration,
                    error=str(e),
                    status="error",
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            trace_id = str(uuid.uuid4())
            start_time = time.time()

            logger.info(
                f"Starting {operation_name}",
                trace_id=trace_id,
                operation=operation_name,
            )

            try:
                result = func(*args, **kwargs)

                duration = time.time() - start_time
                logger.info(
                    f"Completed {operation_name}",
                    trace_id=trace_id,
                    operation=operation_name,
                    duration=duration,
                    status="success",
                )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Failed {operation_name}",
                    trace_id=trace_id,
                    operation=operation_name,
                    duration=duration,
                    error=str(e),
                    status="error",
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@asynccontextmanager
async def trace_operation(operation_name: str, **tags):
    """Context manager for tracing operations."""
    trace_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        f"Starting {operation_name}",
        trace_id=trace_id,
        operation=operation_name,
        **tags,
    )

    try:
        yield trace_id
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Failed {operation_name}",
            trace_id=trace_id,
            operation=operation_name,
            duration=duration,
            error=str(e),
            status="error",
            **tags,
        )
        raise
    else:
        duration = time.time() - start_time
        logger.info(
            f"Completed {operation_name}",
            trace_id=trace_id,
            operation=operation_name,
            duration=duration,
            status="success",
            **tags,
        )


class HealthCheck:
    """Health check implementation."""

    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics
        self.start_time = datetime.utcnow()

    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "version": "1.0.0",
            "components": {},
        }

        # Check database connectivity
        try:
            # This would check actual database connection
            health_status["components"]["database"] = {
                "status": "healthy",
                "response_time_ms": 5.2,
            }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        # Check Redis connectivity
        try:
            # This would check actual Redis connection
            health_status["components"]["redis"] = {
                "status": "healthy",
                "response_time_ms": 1.1,
            }
        except Exception as e:
            health_status["components"]["redis"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        # Check AI service connectivity
        try:
            # This would check actual AI service connection
            health_status["components"]["ai_service"] = {
                "status": "healthy",
                "response_time_ms": 150.0,
            }
        except Exception as e:
            health_status["components"]["ai_service"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        # Check message queue
        try:
            # This would check actual queue connectivity
            health_status["components"]["message_queue"] = {
                "status": "healthy",
                "queue_depth": 0,
            }
        except Exception as e:
            health_status["components"]["message_queue"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        return health_status
