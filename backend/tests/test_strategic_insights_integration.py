"""
Integration Tests for Strategic Insights System

Simple smoke tests to ensure the system is functional.
"""

import pytest
from app.models.strategic_insights import StrategicInsightsRequest


class TestStrategicInsightsIntegration:
    """Integration tests for full strategic insights flow"""

    def test_models_import(self):
        """Test that all models can be imported"""
        from app.models.strategic_insights import (
            Opportunity,
            Risk,
            Evidence,
            StrategicInsights,
            AnalysisPeriod,
            TokenUsage,
            StrategicInsightsResponse,
            StrategicInsightsRequest
        )
        
        assert Opportunity is not None
        assert Risk is not None
        assert Evidence is not None

    def test_repository_import(self):
        """Test that repository can be imported"""
        from app.repositories.strategic_analytics_repository import StrategicAnalyticsRepository
        
        assert StrategicAnalyticsRepository is not None

    def test_agent_import(self):
        """Test that agent can be imported"""
        from app.services.agents.strategic_analysis_agent import StrategicAnalysisAgent
        
        assert StrategicAnalysisAgent is not None

    def test_service_import(self):
        """Test that service can be imported"""
        from app.services.strategic_insights_service import StrategicInsightsService
        
        assert StrategicInsightsService is not None

    def test_request_model_validation(self):
        """Test request model validation works"""
        request = StrategicInsightsRequest(
            start_date="2024-01-01",
            end_date="2024-01-31",
            compare_to_previous=True
        )
        
        assert request.start_date == "2024-01-01"
        assert request.end_date == "2024-01-31"
        assert request.compare_to_previous is True

    def test_opportunity_model_creation(self):
        """Test creating opportunity model"""
        from app.models.strategic_insights import Opportunity, Evidence
        
        evidence = Evidence(
            metric="Test metric",
            value="100",
            source_tool="test_tool",
            sample_size=50,
            statistically_significant=True
        )
        
        opportunity = Opportunity(
            id="OPP-001",
            category="revenue_growth",
            title="Test Opportunity",
            description="Test description",
            evidence=[evidence, evidence],  # Need min 2 evidence
            impact_min=10000,
            impact_max=30000,
            impact_expected=20000,
            assumptions=["Assumption 1"],
            confidence=0.85,
            actionable_steps=["Step 1"],
            timeline="1 week",
            effort="low"
        )
        
        assert opportunity.id == "OPP-001"
        assert len(opportunity.evidence) == 2
        assert opportunity.confidence == 0.85

    def test_risk_model_creation(self):
        """Test creating risk model"""
        from app.models.strategic_insights import Risk, Evidence
        
        evidence = Evidence(
            metric="Test metric",
            value="80%",
            source_tool="test_tool",
            sample_size=30,
            statistically_significant=True
        )
        
        risk = Risk(
            id="RISK-001",
            category="supply_chain",
            title="Test Risk",
            description="Test description",
            evidence=[evidence, evidence],
            impact_min=100000,
            impact_max=500000,
            impact_expected=300000,
            probability=0.4,
            severity="high",
            mitigation_steps=["Step 1", "Step 2"],
            timeline="2 weeks"
        )
        
        assert risk.id == "RISK-001"
        assert risk.probability == 0.4
        assert risk.severity == "high"

    def test_service_cache_key_generation(self):
        """Test cache key generation"""
        from app.services.strategic_insights_service import StrategicInsightsService
        
        service = StrategicInsightsService()
        
        req1 = StrategicInsightsRequest(
            start_date="2024-01-01",
            end_date="2024-01-31",
            compare_to_previous=False
        )
        
        req2 = StrategicInsightsRequest(
            start_date="2024-01-01",
            end_date="2024-01-31",
            compare_to_previous=False
        )
        
        key1 = service._generate_cache_key(req1)
        key2 = service._generate_cache_key(req2)
        
        # Same request should generate same key
        assert key1 == key2
        assert len(key1) == 32  # MD5 hash

    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        from app.services.strategic_insights_service import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=300)
        
        assert cb.state == "closed"
        assert cb.can_attempt() is True
        
        # Record failures
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_attempt() is False
        
        # Success resets
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_tool_call_tracker(self):
        """Test tool call tracking"""
        from app.services.agents.strategic_analysis_agent import ToolCallTracker
        
        tracker = ToolCallTracker(max_calls=3)
        
        # First call allowed
        assert tracker.validate_call("tool1", {"param": "value1"}) is True
        assert tracker.call_count == 1
        
        # Duplicate blocked
        assert tracker.validate_call("tool1", {"param": "value1"}) is False
        assert tracker.call_count == 1
        
        # Different params allowed
        assert tracker.validate_call("tool1", {"param": "value2"}) is True
        assert tracker.call_count == 2
        
        # Budget enforced
        assert tracker.validate_call("tool2", {"param": "value3"}) is True
        assert tracker.validate_call("tool3", {"param": "value4"}) is False  # Exceeds budget
        
        assert tracker.get_remaining_calls() == 0
