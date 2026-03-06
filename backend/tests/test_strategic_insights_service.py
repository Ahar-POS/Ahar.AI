"""
Tests for Strategic Insights Service

Tests orchestration, caching, error recovery, and cost tracking.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.strategic_insights_service import (
    StrategicInsightsService,
    CircuitBreaker
)
from app.models.strategic_insights import (
    StrategicInsightsRequest,
    StrategicInsights,
    AnalysisPeriod,
    TokenUsage
)


@pytest.fixture
def service():
    """Create service instance with temp cache directory"""
    service = StrategicInsightsService()
    # Use temp directory for testing
    service.cache_dir = Path(tempfile.mkdtemp())
    return service


@pytest.fixture
def mock_request():
    """Create mock insights request"""
    return StrategicInsightsRequest(
        start_date="2024-01-01",
        end_date="2024-01-31",
        compare_to_previous=False
    )


class TestCacheKeyGeneration:
    """Test cache key generation"""

    def test_cache_key_generation(self, service, mock_request):
        """Test cache key is generated from request parameters"""
        key = service._generate_cache_key(mock_request)

        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hash length

    def test_same_request_same_key(self, service):
        """Test same request generates same cache key"""
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

        assert key1 == key2

    def test_different_request_different_key(self, service):
        """Test different requests generate different cache keys"""
        req1 = StrategicInsightsRequest(
            start_date="2024-01-01",
            end_date="2024-01-31",
            compare_to_previous=False
        )

        req2 = StrategicInsightsRequest(
            start_date="2024-02-01",
            end_date="2024-02-29",
            compare_to_previous=False
        )

        key1 = service._generate_cache_key(req1)
        key2 = service._generate_cache_key(req2)

        assert key1 != key2


class TestCaching:
    """Test caching functionality"""

    def test_cache_miss_returns_none(self, service):
        """Test cache miss returns None"""
        result = service._get_cached_insights("nonexistent_key")
        assert result is None

    def test_save_and_retrieve_cache(self, service, mock_request):
        """Test saving and retrieving cached insights"""
        from app.models.strategic_insights import StrategicInsightsResponse

        # Create mock response
        response = StrategicInsightsResponse(
            insights=StrategicInsights(
                opportunities=[],
                risks=[],
                executive_summary="Test summary",
                analysis_period=AnalysisPeriod(
                    start="2024-01-01",
                    end="2024-01-31",
                    duration_days=31
                ),
                iterations_used=10
            ),
            usage=TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                cached_tokens=200,
                total_tokens=1500,
                model="claude-opus-4-6",
                cost_usd=0.21
            ),
            cache_hit=False,
            cache_key="test_key"
        )

        # Save to cache
        service._save_to_cache("test_key", response)

        # Retrieve from cache
        cached = service._get_cached_insights("test_key")

        assert cached is not None
        assert cached.insights.executive_summary == "Test summary"
        assert cached.usage.total_tokens == 1500

    def test_expired_cache_is_deleted(self, service):
        """Test expired cache files are deleted"""
        from app.models.strategic_insights import StrategicInsightsResponse

        response = StrategicInsightsResponse(
            insights=StrategicInsights(
                opportunities=[],
                risks=[],
                executive_summary="Test",
                analysis_period=AnalysisPeriod(
                    start="2024-01-01",
                    end="2024-01-31",
                    duration_days=31
                ),
                iterations_used=5
            ),
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cached_tokens=20,
                total_tokens=150,
                model="claude-opus-4-6",
                cost_usd=0.02
            ),
            cache_hit=False,
            cache_key="expired_key"
        )

        # Save to cache
        service._save_to_cache("expired_key", response)

        # Set TTL to 0 to force expiration
        service.cache_ttl_seconds = 0

        # Try to retrieve - should be None and file deleted
        cached = service._get_cached_insights("expired_key")
        assert cached is None

    @pytest.mark.asyncio
    async def test_clear_cache_specific_key(self, service):
        """Test clearing specific cache key"""
        from app.models.strategic_insights import StrategicInsightsResponse

        response = StrategicInsightsResponse(
            insights=StrategicInsights(
                opportunities=[],
                risks=[],
                executive_summary="Test",
                analysis_period=AnalysisPeriod(start="2024-01-01", end="2024-01-31", duration_days=31),
                iterations_used=5
            ),
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cached_tokens=0,
                total_tokens=150,
                model="test",
                cost_usd=0.01
            ),
            cache_hit=False,
            cache_key="key1"
        )

        service._save_to_cache("key1", response)

        # Clear specific key
        await service.clear_cache("key1")

        # Should not be retrievable
        cached = service._get_cached_insights("key1")
        assert cached is None

    @pytest.mark.asyncio
    async def test_clear_all_cache(self, service):
        """Test clearing all cache"""
        from app.models.strategic_insights import StrategicInsightsResponse

        # Create multiple cache entries
        for i in range(3):
            response = StrategicInsightsResponse(
                insights=StrategicInsights(
                    opportunities=[],
                    risks=[],
                    executive_summary=f"Test {i}",
                    analysis_period=AnalysisPeriod(start="2024-01-01", end="2024-01-31", duration_days=31),
                    iterations_used=5
                ),
                usage=TokenUsage(
                    input_tokens=100,
                    output_tokens=50,
                    cached_tokens=0,
                    total_tokens=150,
                    model="test",
                    cost_usd=0.01
                ),
                cache_hit=False,
                cache_key=f"key{i}"
            )
            service._save_to_cache(f"key{i}", response)

        # Clear all
        await service.clear_cache(cache_key=None)

        # None should be retrievable
        for i in range(3):
            cached = service._get_cached_insights(f"key{i}")
            assert cached is None


class TestTokenCostCalculation:
    """Test token cost calculation"""

    def test_cost_calculation_basic(self, service):
        """Test basic cost calculation"""
        usage = {
            "input_tokens": 20000,
            "output_tokens": 5000,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0
        }

        cost = service._calculate_token_cost(usage)

        # 20k input * $5/1M + 5k output * $25/1M
        expected = (20000 * 5.00 / 1_000_000) + (5000 * 25.00 / 1_000_000)
        assert abs(cost - expected) < 0.001

    def test_cost_calculation_with_cache_write(self, service):
        """Test cost calculation with cache writes"""
        usage = {
            "input_tokens": 20000,
            "output_tokens": 5000,
            "cache_creation_input_tokens": 4000,
            "cache_read_input_tokens": 0
        }

        cost = service._calculate_token_cost(usage)

        # (20k - 4k) input * $5/1M + 5k output * $25/1M + 4k cache write * $6.25/1M
        input_cost = (20000 - 4000) * 5.00 / 1_000_000
        output_cost = 5000 * 25.00 / 1_000_000
        cache_write_cost = 4000 * 6.25 / 1_000_000
        expected = input_cost + output_cost + cache_write_cost

        assert abs(cost - expected) < 0.001

    def test_cost_calculation_with_cache_hit(self, service):
        """Test cost calculation with cache hits"""
        usage = {
            "input_tokens": 20000,
            "output_tokens": 5000,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 4000
        }

        cost = service._calculate_token_cost(usage)

        # (20k - 4k) input * $5/1M + 5k output * $25/1M + 4k cache read * $0.50/1M
        input_cost = (20000 - 4000) * 5.00 / 1_000_000
        output_cost = 5000 * 25.00 / 1_000_000
        cache_read_cost = 4000 * 0.50 / 1_000_000
        expected = input_cost + output_cost + cache_read_cost

        assert abs(cost - expected) < 0.001


class TestCircuitBreaker:
    """Test circuit breaker for failure protection"""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes correctly"""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=300)

        assert cb.failure_threshold == 3
        assert cb.timeout_seconds == 300
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_circuit_breaker_allows_when_closed(self):
        """Test circuit breaker allows attempts when closed"""
        cb = CircuitBreaker()
        assert cb.can_attempt() is True

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold"""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_attempt() is False

    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker resets on success"""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"


class TestOpportunityParsing:
    """Test opportunity parsing from agent output"""

    def test_parse_valid_opportunity(self, service):
        """Test parsing valid opportunity data"""
        data = [{
            "id": "OPP-001",
            "category": "revenue_growth",
            "title": "Test Opportunity",
            "description": "Description",
            "evidence": [
                {
                    "metric": "Revenue",
                    "value": "10%",
                    "source_tool": "get_sales_trends",
                    "sample_size": 100,
                    "statistically_significant": True
                },
                {
                    "metric": "Orders",
                    "value": "50",
                    "source_tool": "get_sales_trends",
                    "sample_size": 50,
                    "statistically_significant": True
                }
            ],
            "impact_min": 10000,
            "impact_max": 30000,
            "impact_expected": 20000,
            "assumptions": ["Assumption 1"],
            "confidence": 0.85,
            "actionable_steps": ["Step 1"],
            "timeline": "1 week",
            "effort": "low"
        }]

        opportunities = service._parse_opportunities(data)

        assert len(opportunities) == 1
        assert opportunities[0].id == "OPP-001"
        assert opportunities[0].confidence == 0.85

    def test_parse_opportunity_requires_min_evidence(self, service):
        """Test opportunities with insufficient evidence are skipped"""
        data = [{
            "id": "OPP-001",
            "category": "revenue_growth",
            "title": "Test",
            "description": "Description",
            "evidence": [
                {
                    "metric": "Revenue",
                    "value": "10%",
                    "source_tool": "test",
                    "sample_size": 100,
                    "statistically_significant": True
                }
            ],  # Only 1 evidence point (need 2)
            "impact_min": 10000,
            "impact_max": 30000,
            "impact_expected": 20000,
            "assumptions": ["Assumption 1"],
            "confidence": 0.85,
            "actionable_steps": ["Step 1"],
            "timeline": "1 week",
            "effort": "low"
        }]

        opportunities = service._parse_opportunities(data)

        assert len(opportunities) == 0  # Should be skipped


class TestRiskParsing:
    """Test risk parsing from agent output"""

    def test_parse_valid_risk(self, service):
        """Test parsing valid risk data"""
        data = [{
            "id": "RISK-001",
            "category": "supply_chain",
            "title": "Test Risk",
            "description": "Description",
            "evidence": [
                {
                    "metric": "Supplier concentration",
                    "value": "80%",
                    "source_tool": "get_supplier_patterns",
                    "sample_size": 50,
                    "statistically_significant": True
                },
                {
                    "metric": "Lead time",
                    "value": "5 days",
                    "source_tool": "get_supplier_patterns",
                    "sample_size": 30,
                    "statistically_significant": True
                }
            ],
            "impact_min": 100000,
            "impact_max": 500000,
            "impact_expected": 300000,
            "probability": 0.4,
            "severity": "high",
            "mitigation_steps": ["Step 1", "Step 2"],
            "timeline": "2 weeks"
        }]

        risks = service._parse_risks(data)

        assert len(risks) == 1
        assert risks[0].id == "RISK-001"
        assert risks[0].probability == 0.4
        assert risks[0].severity == "high"
