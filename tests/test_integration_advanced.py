"""
Advanced Integration Tests for DealHealthService API endpoints.

This test suite covers advanced scenarios, edge cases, and performance testing
for the DealHealthService - Health Graph System.

Requires Docker Compose services to be running:
    docker-compose up -d
"""

import asyncio
import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import pytest
from fastapi.testclient import TestClient

from deal_health_service.api import app
from deal_health_service.models import (
    AutomatedTestResult,
    CommunityTip,
    CommunityVerification,
    EventType,
    HealthCalculationConfig,
)


class TestAdvancedIntegration:
    """Advanced integration tests for complex scenarios."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test client and wait for services to be ready."""
        self.client = TestClient(app)
        self.base_url = "http://localhost:8000"
        
        # Wait for services to be ready
        self._wait_for_services()
    
    def _wait_for_services(self, timeout: int = 30):
        """Wait for all services to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = httpx.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    health_data = response.json()
                    if health_data["status"] == "healthy":
                        print("✅ Services are ready for advanced testing!")
                        return
            except Exception:
                pass
            time.sleep(1)
        raise TimeoutError("Services did not become ready within timeout")

    def test_health_score_evolution_over_time(self):
        """Test how health scores evolve with multiple events over time."""
        promotion_id = "TEST_EVOLUTION_001"
        
        # Initial state - should be neutral (50)
        response = self.client.get(f"/promotions/{promotion_id}/health")
        if response.status_code == 200:
            initial_score = response.json()["data"]["health_score"]
        else:
            initial_score = 50
        
        # Add a negative automated test
        negative_event = {
            "type": "AutomatedTestResult",
            "promotionId": promotion_id,
            "merchantId": 1001,
            "success": False,
            "discountValue": 0.0,
            "errorMessage": "Coupon expired",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = self.client.post(
            f"/events/process-single?promotion_id={promotion_id}",
            json=negative_event
        )
        assert response.status_code == 200
        
        # Check score decreased
        response = self.client.get(f"/promotions/{promotion_id}/health")
        assert response.status_code == 200
        score_after_negative = response.json()["data"]["health_score"]
        assert score_after_negative < initial_score
        
        # Add a positive community verification
        positive_event = {
            "type": "CommunityVerification",
            "promotionId": promotion_id,
            "verifierId": "user_high_rep",
            "verifierReputationScore": 95,
            "is_valid": True,
            "verificationMethod": "manual_test",
            "timestamp": datetime.utcnow().isoformat(),
            "notes": "Actually works fine!"
        }
        
        response = self.client.post(
            f"/events/process-single?promotion_id={promotion_id}",
            json=positive_event
        )
        assert response.status_code == 200
        
        # Check score improved
        response = self.client.get(f"/promotions/{promotion_id}/health")
        assert response.status_code == 200
        final_score = response.json()["data"]["health_score"]
        assert final_score > score_after_negative

    def test_ai_processing_with_complex_tips(self):
        """Test AI processing with complex community tips."""
        promotion_id = "TEST_AI_COMPLEX_001"
        
        complex_tips = [
            {
                "tipText": "This coupon works but only on orders over $50 and excludes electronics. Got 15% off my clothing purchase!",
                "expected_conditions": ["minimum spend", "electronics excluded"],
                "expected_effectiveness": "medium"
            },
            {
                "tipText": "AMAZING DEAL! Works perfectly for everything. No restrictions at all. 25% off!",
                "expected_conditions": [],
                "expected_effectiveness": "high"
            },
            {
                "tipText": "Doesn't work anymore. Tried yesterday and got error message about expired coupon.",
                "expected_conditions": [],
                "expected_effectiveness": "low"
            }
        ]
        
        for i, tip_data in enumerate(complex_tips):
            event_data = {
                "type": "CommunityTip",
                "promotionId": promotion_id,
                "tipText": tip_data["tipText"],
                "userId": f"user_complex_{i}",
                "userReputation": 80,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = self.client.post(
                f"/events/process-single?promotion_id={promotion_id}",
                json=event_data
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is True
        
        # Check final health score
        response = self.client.get(f"/promotions/{promotion_id}/health")
        assert response.status_code == 200
        final_score = response.json()["data"]["health_score"]
        # Should be around neutral due to mixed signals
        assert 30 <= final_score <= 70

    def test_high_volume_event_processing(self):
        """Test processing a high volume of events for multiple promotions."""
        num_promotions = 10
        events_per_promotion = 5
        
        all_events = []
        
        # Generate events for multiple promotions
        for promo_idx in range(num_promotions):
            promotion_id = f"TEST_HIGH_VOLUME_{promo_idx:03d}"
            
            for event_idx in range(events_per_promotion):
                event_type = random.choice(["AutomatedTestResult", "CommunityVerification", "CommunityTip"])
                
                if event_type == "AutomatedTestResult":
                    event_data = {
                        "type": event_type,
                        "promotionId": promotion_id,
                        "merchantId": 2000 + promo_idx,
                        "success": random.choice([True, False]),
                        "discountValue": random.uniform(5.0, 50.0),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                elif event_type == "CommunityVerification":
                    event_data = {
                        "type": event_type,
                        "promotionId": promotion_id,
                        "verifierId": f"user_vol_{promo_idx}_{event_idx}",
                        "verifierReputationScore": random.randint(50, 100),
                        "is_valid": random.choice([True, False]),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:  # CommunityTip
                    event_data = {
                        "type": event_type,
                        "promotionId": promotion_id,
                        "tipText": f"Tip {event_idx} for promotion {promo_idx}",
                        "userId": f"user_tip_{promo_idx}_{event_idx}",
                        "userReputation": random.randint(50, 100),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                
                all_events.append((promotion_id, event_data))
        
        # Process all events
        start_time = time.time()
        
        for promotion_id, event_data in all_events:
            response = self.client.post(
                f"/events/process-single?promotion_id={promotion_id}",
                json=event_data
            )
            assert response.status_code == 200
        
        processing_time = time.time() - start_time
        
        print(f"Processed {len(all_events)} events in {processing_time:.2f} seconds")
        print(f"Average processing time: {processing_time/len(all_events)*1000:.2f} ms per event")
        
        # Verify all promotions have health scores
        for promo_idx in range(num_promotions):
            promotion_id = f"TEST_HIGH_VOLUME_{promo_idx:03d}"
            response = self.client.get(f"/promotions/{promotion_id}/health")
            assert response.status_code == 200
            assert response.json()["data"]["health_score"] >= 0
            assert response.json()["data"]["health_score"] <= 100

    def test_concurrent_health_score_queries(self):
        """Test concurrent health score queries for the same promotion."""
        promotion_id = "TEST_CONCURRENT_001"
        
        # First create a promotion with some events
        event_data = {
            "type": "AutomatedTestResult",
            "promotionId": promotion_id,
            "merchantId": 3001,
            "success": True,
            "discountValue": 20.0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.client.post(
            f"/events/process-single?promotion_id={promotion_id}",
            json=event_data
        )
        
        # Now test concurrent queries
        def query_health_score():
            try:
                response = self.client.get(f"/promotions/{promotion_id}/health")
                return response.status_code, response.json()["data"]["health_score"]
            except Exception as e:
                return 500, str(e)
        
        # Run 20 concurrent queries
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(query_health_score) for _ in range(20)]
            results = [future.result() for future in as_completed(futures)]
        
        # All queries should succeed and return the same score
        status_codes = [result[0] for result in results]
        health_scores = [result[1] for result in results if isinstance(result[1], int)]
        
        assert all(status == 200 for status in status_codes)
        assert len(set(health_scores)) == 1  # All scores should be identical
        assert health_scores[0] > 50  # Should be positive

    def test_merchant_analytics_workflow(self):
        """Test a complete merchant analytics workflow."""
        merchant_id = 4001
        
        # Create multiple promotions for the merchant
        promotions = []
        for i in range(5):
            promotion_id = f"TEST_MERCHANT_ANALYTICS_{i:03d}"
            promotions.append(promotion_id)
            
            # Add mixed events for each promotion
            events = [
                {
                    "type": "AutomatedTestResult",
                    "promotionId": promotion_id,
                    "merchantId": merchant_id,
                    "success": i % 2 == 0,  # Alternate success/failure
                    "discountValue": 10.0 + i * 5,
                    "timestamp": datetime.utcnow().isoformat()
                },
                {
                    "type": "CommunityVerification",
                    "promotionId": promotion_id,
                    "verifierId": f"user_analytics_{i}",
                    "verifierReputationScore": 70 + i * 5,
                    "is_valid": i % 3 != 0,  # Some failures
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
            
            for event_data in events:
                self.client.post(
                    f"/events/process-single?promotion_id={promotion_id}",
                    json=event_data
                )
        
        # Get merchant analytics
        response = self.client.get(f"/merchants/{merchant_id}/promotions")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["promotions"]) >= 5
        
        # Analyze health score distribution
        health_scores = [promo["health_score"] for promo in data["promotions"]]
        avg_health = sum(health_scores) / len(health_scores)
        
        print(f"Merchant {merchant_id} analytics:")
        print(f"  Total promotions: {len(data['promotions'])}")
        print(f"  Average health score: {avg_health:.2f}")
        print(f"  Health score range: {min(health_scores)} - {max(health_scores)}")
        
        # Test health range filtering
        response = self.client.get(f"/promotions/by-health?min_health=50&max_health=100")
        assert response.status_code == 200
        
        good_promotions = response.json()["promotions"]
        good_count = len([p for p in data["promotions"] if p["health_score"] >= 50])
        assert len(good_promotions) >= good_count

    def test_configuration_impact_on_health_scores(self):
        """Test how configuration changes impact health score calculations."""
        promotion_id = "TEST_CONFIG_IMPACT_001"
        
        # Create baseline events
        baseline_events = [
            {
                "type": "AutomatedTestResult",
                "promotionId": promotion_id,
                "merchantId": 5001,
                "success": True,
                "discountValue": 25.0,
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "type": "CommunityVerification",
                "promotionId": promotion_id,
                "verifierId": "user_config",
                "verifierReputationScore": 85,
                "is_valid": True,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        
        for event_data in baseline_events:
            self.client.post(
                f"/events/process-single?promotion_id={promotion_id}",
                json=event_data
            )
        
        # Get baseline score
        response = self.client.get(f"/promotions/{promotion_id}/health")
        baseline_score = response.json()["data"]["health_score"]
        
        # Change configuration to favor automated tests
        config_data = {
            "automated_test_weight": 0.8,
            "community_verification_weight": 0.1,
            "community_tip_weight": 0.1,
            "decay_rate_per_day": 0.1,
            "min_confidence_for_positive": 0.3,
            "min_confidence_for_negative": 0.3,
            "max_event_age_days": 30
        }
        
        response = self.client.post("/config/update", json=config_data)
        assert response.status_code == 200
        
        # Process the same events again
        for event_data in baseline_events:
            self.client.post(
                f"/events/process-single?promotion_id={promotion_id}",
                json=event_data
            )
        
        # Get new score
        response = self.client.get(f"/promotions/{promotion_id}/health")
        new_score = response.json()["data"]["health_score"]
        
        # Scores should be different due to configuration change
        assert new_score != baseline_score

    def test_error_recovery_and_resilience(self):
        """Test system resilience and error recovery."""
        # Test with malformed events
        malformed_events = [
            {},  # Empty event
            {"type": "AutomatedTestResult"},  # Missing required fields
            {"type": "InvalidType", "promotionId": "TEST_ERROR_001"},  # Invalid type
            {"type": "AutomatedTestResult", "promotionId": "TEST_ERROR_002", "success": "not_boolean"},  # Wrong type
        ]
        
        for i, event_data in enumerate(malformed_events):
            promotion_id = f"TEST_ERROR_RECOVERY_{i:03d}"
            
            response = self.client.post(
                f"/events/process-single?promotion_id={promotion_id}",
                json=event_data
            )
            
            # System should handle errors gracefully
            assert response.status_code == 200
            data = response.json()
            assert not data["success"]  # Should indicate error
        
        # Test with very large event data
        large_event = {
            "type": "CommunityTip",
            "promotionId": "TEST_LARGE_EVENT_001",
            "tipText": "A" * 10000,  # Very large tip text
            "userId": "user_large",
            "userReputation": 75,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = self.client.post(
            f"/events/process-single?promotion_id=TEST_LARGE_EVENT_001",
            json=large_event
        )
        
        # Should handle large data gracefully
        assert response.status_code in [200, 413]  # 413 if size limit exceeded
        
        # Verify system is still healthy after errors
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_performance_under_load(self):
        """Test system performance under simulated load."""
        # Simulate flash sale scenario with rapid event processing
        promotion_id = "TEST_PERFORMANCE_001"
        
        # Create rapid-fire events
        start_time = time.time()
        
        for i in range(50):  # 50 rapid events
            event_data = {
                "type": "AutomatedTestResult",
                "promotionId": promotion_id,
                "merchantId": 6001,
                "success": i % 3 != 0,  # Some failures
                "discountValue": 10.0 + i,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = self.client.post(
                f"/events/process-single?promotion_id={promotion_id}",
                json=event_data
            )
            assert response.status_code == 200
        
        processing_time = time.time() - start_time
        events_per_second = 50 / processing_time
        
        print(f"Performance test results:")
        print(f"  Processed 50 events in {processing_time:.2f} seconds")
        print(f"  Events per second: {events_per_second:.2f}")
        
        # Should handle at least 10 events per second
        assert events_per_second >= 10
        
        # Verify final health score is reasonable
        response = self.client.get(f"/promotions/{promotion_id}/health")
        assert response.status_code == 200
        final_score = response.json()["data"]["health_score"]
        assert 0 <= final_score <= 100

    def test_data_consistency_and_integrity(self):
        """Test data consistency and integrity across operations."""
        promotion_id = "TEST_CONSISTENCY_001"
        
        # Create initial state
        initial_event = {
            "type": "AutomatedTestResult",
            "promotionId": promotion_id,
            "merchantId": 7001,
            "success": True,
            "discountValue": 30.0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.client.post(
            f"/events/process-single?promotion_id={promotion_id}",
            json=initial_event
        )
        
        # Get initial health score
        response = self.client.get(f"/promotions/{promotion_id}/health")
        initial_score = response.json()["data"]["health_score"]
        
        # Get initial history
        response = self.client.get(f"/promotions/{promotion_id}/history")
        initial_history_count = len(response.json()["data"])
        
        # Process same event again (should be idempotent)
        self.client.post(
            f"/events/process-single?promotion_id={promotion_id}",
            json=initial_event
        )
        
        # Health score should remain the same (idempotency)
        response = self.client.get(f"/promotions/{promotion_id}/health")
        current_score = response.json()["data"]["health_score"]
        assert current_score == initial_score
        
        # History should be consistent
        response = self.client.get(f"/promotions/{promotion_id}/history")
        current_history_count = len(response.json()["data"])
        assert current_history_count >= initial_history_count
        
        # Add new event
        new_event = {
            "type": "CommunityVerification",
            "promotionId": promotion_id,
            "verifierId": "user_consistency",
            "verifierReputationScore": 90,
            "is_valid": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.client.post(
            f"/events/process-single?promotion_id={promotion_id}",
            json=new_event
        )
        
        # Health score should change
        response = self.client.get(f"/promotions/{promotion_id}/health")
        new_score = response.json()["data"]["health_score"]
        assert new_score != initial_score
        
        # History should include new event
        response = self.client.get(f"/promotions/{promotion_id}/history")
        final_history_count = len(response.json()["data"])
        assert final_history_count > initial_history_count


if __name__ == "__main__":
    # Run advanced integration tests
    pytest.main([__file__, "-v"]) 