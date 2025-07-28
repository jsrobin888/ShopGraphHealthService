"""
FastAPI application for the DealHealthService - Health Graph System.

This module provides REST API endpoints for processing verification events
and retrieving promotion health information within the ShopGraph ecosystem.
"""

import logging
import time
import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .models import (
    AutomatedTestResult,
    CommunityTip,
    CommunityVerification,
    HealthCalculationConfig,
    HealthScoreUpdate,
    PromotionState,
)
from .service import DealHealthService
from .monitoring import setup_structured_logging, HealthCheck

# Setup structured logging
setup_structured_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DealHealthService API - Health Graph System",
    description="AI-Powered Deal Health Service for ShopGraph - Health Graph System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Initialize service
service = DealHealthService()


# Add monitoring middleware - using a function-based approach
@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    """Monitoring middleware for request tracking and metrics."""
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
        service.metrics.record_api_request(
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
        service.metrics.record_error(error_type=type(e).__name__, component="api")
        raise


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize health check
health_check = HealthCheck(service.metrics)


# Request/Response models
class ProcessEventsRequest(BaseModel):
    """Request model for processing verification events in the Health Graph System."""

    promotion_id: str
    events: List[dict]  # Raw event data that will be parsed


class BatchProcessRequest(BaseModel):
    """Request model for batch processing events in the Health Graph System."""

    events_by_promotion: dict[str, List[dict]]


class HealthScoreResponse(BaseModel):
    """Response model for health score updates from the Health Graph System."""

    success: bool
    data: Optional[HealthScoreUpdate] = None
    error: Optional[str] = None


class PromotionHealthResponse(BaseModel):
    """Response model for promotion health information from the Health Graph System."""

    success: bool
    data: Optional[PromotionState] = None
    error: Optional[str] = None


class PromotionHistoryResponse(BaseModel):
    """Response model for promotion history from the Health Graph System."""

    success: bool
    data: Optional[List[dict]] = None
    error: Optional[str] = None


# Health check endpoint
@app.get("/health")
async def health_check_endpoint():
    """Comprehensive health check endpoint for the Health Graph System."""
    return await health_check.check_health()


# Metrics endpoint for Prometheus
@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint():
    """Prometheus metrics endpoint for the Health Graph System."""
    return service.get_metrics()


# Queue statistics endpoint
@app.get("/queue/stats")
async def queue_stats_endpoint():
    """Message queue statistics endpoint for the Health Graph System."""
    return service.get_queue_stats()


# Process verification events
@app.post("/events/process", response_model=HealthScoreResponse)
async def process_verification_events(request: ProcessEventsRequest):
    """
    Process verification events for a promotion in the Health Graph System.

    This endpoint accepts a list of verification events and calculates
    the new health score for the specified promotion using the Health Graph System.
    """
    try:
        # Parse events from raw data
        events = []
        for event_data in request.events:
            event_type = event_data.get("type")

            if event_type == "AutomatedTestResult":
                event = AutomatedTestResult(**event_data)
            elif event_type == "CommunityVerification":
                event = CommunityVerification(**event_data)
            elif event_type == "CommunityTip":
                event = CommunityTip(**event_data)
            else:
                raise HTTPException(
                    status_code=400, detail=f"Unknown event type: {event_type}"
                )

            events.append(event)

        # Process events through the Health Graph System
        result = await service.process_verification_events(request.promotion_id, events)

        return HealthScoreResponse(success=True, data=result)

    except Exception as e:
        logger.error("Failed to process events in Health Graph System: %s", str(e))
        return HealthScoreResponse(success=False, error=str(e))


@app.post("/events/process-single", response_model=HealthScoreResponse)
async def process_single_event(promotion_id: str, event: dict):
    """
    Process a single verification event for a promotion in the Health Graph System.

    This endpoint accepts a single verification event and calculates
    the new health score for the specified promotion using the Health Graph System.
    """
    try:
        # Parse event from raw data
        event_type = event.get("type")

        if event_type == "AutomatedTestResult":
            verification_event = AutomatedTestResult(**event)
        elif event_type == "CommunityVerification":
            verification_event = CommunityVerification(**event)
        elif event_type == "CommunityTip":
            verification_event = CommunityTip(**event)
        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown event type: {event_type}"
            )

        # Process event through the Health Graph System
        result = await service.process_single_event(promotion_id, verification_event)

        return HealthScoreResponse(success=True, data=result)

    except Exception as e:
        logger.error(
            "Failed to process single event in Health Graph System: %s", str(e)
        )
        return HealthScoreResponse(success=False, error=str(e))


@app.post("/events/batch-process", response_model=dict)
async def batch_process_events(request: BatchProcessRequest):
    """
    Process events for multiple promotions in batch using the Health Graph System.

    This endpoint accepts events for multiple promotions and processes
    them concurrently for better performance in the Health Graph System.
    """
    try:
        # Parse events from raw data
        events_by_promotion = {}

        for promotion_id, raw_events in request.events_by_promotion.items():
            events = []
            for event_data in raw_events:
                event_type = event_data.get("type")

                if event_type == "AutomatedTestResult":
                    event = AutomatedTestResult(**event_data)
                elif event_type == "CommunityVerification":
                    event = CommunityVerification(**event_data)
                elif event_type == "CommunityTip":
                    event = CommunityTip(**event_data)
                else:
                    raise HTTPException(
                        status_code=400, detail=f"Unknown event type: {event_type}"
                    )

                events.append(event)

            events_by_promotion[promotion_id] = events

        # Process events in batch through the Health Graph System
        results = await service.batch_process_events(events_by_promotion)

        return {
            "success": True,
            "results": [result.dict() for result in results],
            "processed_promotions": len(results),
        }

    except Exception as e:
        logger.error(
            "Failed to batch process events in Health Graph System: %s", str(e)
        )
        return {"success": False, "error": str(e)}


@app.get("/promotions/{promotion_id}/health", response_model=PromotionHealthResponse)
async def get_promotion_health(promotion_id: str):
    """
    Get current health information for a promotion from the Health Graph System.

    Returns the current health score, confidence, and other
    relevant information for the specified promotion from the Health Graph System.
    """
    try:
        promotion = await service.get_promotion_health(promotion_id)

        if not promotion:
            raise HTTPException(
                status_code=404, detail="Promotion not found in Health Graph System"
            )

        return PromotionHealthResponse(success=True, data=promotion)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get promotion health from Health Graph System: %s", str(e)
        )
        return PromotionHealthResponse(success=False, error=str(e))


@app.get("/promotions/{promotion_id}/history", response_model=PromotionHistoryResponse)
async def get_promotion_history(promotion_id: str, limit: int = 50):
    """
    Get processing history for a promotion from the Health Graph System.

    Returns a list of recent event processing results
    for the specified promotion from the Health Graph System.
    """
    try:
        history = await service.get_promotion_history(promotion_id, limit)

        return PromotionHistoryResponse(
            success=True, data=[result.dict() for result in history]
        )

    except Exception as e:
        logger.error(
            "Failed to get promotion history from Health Graph System: %s", str(e)
        )
        return PromotionHistoryResponse(success=False, error=str(e))


@app.get("/merchants/{merchant_id}/promotions", response_model=dict)
async def get_merchant_promotions(merchant_id: int):
    """
    Get all promotions for a merchant from the Health Graph System.

    Returns a list of all promotions associated with
    the specified merchant from the Health Graph System.
    """
    try:
        promotions = await service.get_merchant_promotions(merchant_id)

        return {
            "success": True,
            "merchant_id": merchant_id,
            "promotions": [promotion.dict() for promotion in promotions],
            "count": len(promotions),
        }

    except Exception as e:
        logger.error(
            "Failed to get merchant promotions from Health Graph System: %s", str(e)
        )
        return {"success": False, "error": str(e)}


@app.get("/promotions/by-health", response_model=dict)
async def get_promotions_by_health_range(min_health: int = 0, max_health: int = 100):
    """
    Get promotions within a health score range from the Health Graph System.

    Returns promotions with health scores between
    min_health and max_health (inclusive) from the Health Graph System.
    """
    try:
        if min_health < 0 or max_health > 100 or min_health > max_health:
            raise HTTPException(
                status_code=400,
                detail="Invalid health range. Must be 0-100 and min <= max",
            )

        promotions = await service.get_promotions_by_health_range(
            min_health, max_health
        )

        return {
            "success": True,
            "min_health": min_health,
            "max_health": max_health,
            "promotions": [promotion.dict() for promotion in promotions],
            "count": len(promotions),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get promotions by health range from Health Graph System: %s",
            str(e),
        )
        return {"success": False, "error": str(e)}


# Update service configuration
@app.post("/config/update")
async def update_config(config: HealthCalculationConfig):
    """
    Update the Health Graph System configuration.

    This endpoint allows updating the health calculation parameters
    such as event weights and decay rates in the Health Graph System.
    """
    try:
        # Create new service instance with updated config
        global service
        service = DealHealthService(config)

        return {
            "success": True,
            "message": "Health Graph System configuration updated successfully",
            "config": config.dict(),
        }

    except Exception as e:
        logger.error("Failed to update Health Graph System config: %s", str(e))
        return {
            "success": False,
            "error": f"Failed to update Health Graph System config: {str(e)}",
        }


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize Health Graph System on startup."""
    logger.info("Starting DealHealthService - Health Graph System...")
    await service.start()
    logger.info("DealHealthService - Health Graph System started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup Health Graph System on shutdown."""
    logger.info("Shutting down DealHealthService - Health Graph System...")
    await service.stop()
    logger.info("DealHealthService - Health Graph System shutdown complete")
