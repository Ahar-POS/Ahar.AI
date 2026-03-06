"""
Tests for Strategic Analysis Agent

Tests tool-calling, response parsing, and insight generation.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from anthropic.types import Message, ContentBlock, TextBlock, Usage

from app.services.agents.strategic_analysis_agent import (
    StrategicAnalysisAgent,
    ToolCallTracker
)
from app.repositories.strategic_analytics_repository import StrategicAnalyticsRepository


@pytest.fixture
def mock_repository():
    """Create mock repository"""
    repo = AsyncMock(spec=StrategicAnalyticsRepository)

    # Mock all 8 tools
    repo.get_sales_trends = AsyncMock(return_value={
        "summary": {"total_revenue": 1000000, "total_orders": 500},
        "daily_trends": [],
        "by_order_type": [],
        "peak_hours": []
    })

    repo.get_item_performance = AsyncMock(return_value={
        "top_performers": [],
        "bottom_performers": [],
        "summary": {}
    })

    repo.get_inventory_risks = AsyncMock(return_value={
        "low_stock_items": [],
        "waste_analysis": {},
        "summary": {}
    })

    repo.get_supplier_patterns = AsyncMock(return_value={
        "supplier_spend": [],
        "supplier_concentration": {},
        "summary": {}
    })

    repo.get_customer_behavior = AsyncMock(return_value={
        "time_patterns": [],
        "weekday_vs_weekend": {},
        "order_composition": {}
    })

    repo.get_operational_metrics = AsyncMock(return_value={
        "kitchen_performance": {},
        "order_completion": {},
        "industry_comparison": {}
    })

    repo.get_financial_health = AsyncMock(return_value={
        "revenue": {},
        "costs": {},
        "margins": {},
        "industry_comparison": {}
    })

    repo.get_comparative_analysis = AsyncMock(return_value={
        "current_period": {},
        "comparison_period": {},
        "growth_rates": {}
    })

    return repo


@pytest.fixture
def agent(mock_repository):
    """Create agent instance with mock repository"""
    return StrategicAnalysisAgent(
        repository=mock_repository,
        model="claude-sonnet-4-5"
    )


class TestToolCallTracker:
    """Test tool call tracking and deduplication"""

    def test_tracker_initialization(self):
        """Test tracker initializes correctly"""
        tracker = ToolCallTracker(max_calls=15)
        assert tracker.max_calls == 15
        assert tracker.call_count == 0
        assert len(tracker.call_history) == 0

    def test_tracker_allows_unique_calls(self):
        """Test tracker allows unique tool calls"""
        tracker = ToolCallTracker(max_calls=3)

        assert tracker.validate_call("tool1", {"param": "value1"}) is True
        assert tracker.call_count == 1

        assert tracker.validate_call("tool1", {"param": "value2"}) is True
        assert tracker.call_count == 2

    def test_tracker_blocks_duplicate_calls(self):
        """Test tracker blocks duplicate tool calls"""
        tracker = ToolCallTracker(max_calls=5)

        params = {"param": "value"}
        assert tracker.validate_call("tool1", params) is True
        assert tracker.validate_call("tool1", params) is False  # Duplicate

        assert tracker.call_count == 1  # Only counted once

    def test_tracker_enforces_budget(self):
        """Test tracker enforces call budget"""
        tracker = ToolCallTracker(max_calls=2)

        assert tracker.validate_call("tool1", {"p": "1"}) is True
        assert tracker.validate_call("tool2", {"p": "2"}) is True
        assert tracker.validate_call("tool3", {"p": "3"}) is False  # Budget exceeded

        assert tracker.call_count == 2

    def test_remaining_calls(self):
        """Test remaining calls calculation"""
        tracker = ToolCallTracker(max_calls=5)

        assert tracker.get_remaining_calls() == 5

        tracker.validate_call("tool1", {"p": "1"})
        assert tracker.get_remaining_calls() == 4

        tracker.validate_call("tool2", {"p": "2"})
        tracker.validate_call("tool3", {"p": "3"})
        assert tracker.get_remaining_calls() == 2


class TestAgentInitialization:
    """Test agent initialization"""

    def test_agent_has_8_tools(self, agent):
        """Test agent defines 8 analytical tools"""
        assert len(agent.tools) == 8

        tool_names = [tool["name"] for tool in agent.tools]
        expected_tools = [
            "get_sales_trends",
            "get_item_performance",
            "get_inventory_risks",
            "get_supplier_patterns",
            "get_customer_behavior",
            "get_operational_metrics",
            "get_financial_health",
            "get_comparative_analysis"
        ]

        for expected in expected_tools:
            assert expected in tool_names

    def test_agent_has_system_prompt(self, agent):
        """Test agent has strategic analysis system prompt"""
        assert len(agent.system_prompt) > 0
        assert "strategic" in agent.system_prompt.lower()
        assert "opportunities" in agent.system_prompt.lower()
        assert "risks" in agent.system_prompt.lower()


class TestToolExecution:
    """Test tool execution methods"""

    @pytest.mark.asyncio
    async def test_execute_sales_trends_tool(self, agent, mock_repository):
        """Test executing get_sales_trends tool"""
        result = await agent._execute_tool(
            "get_sales_trends",
            {"start_date": "2024-01-01", "end_date": "2024-01-31", "granularity": "daily"}
        )

        assert "summary" in result
        mock_repository.get_sales_trends.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_item_performance_tool(self, agent, mock_repository):
        """Test executing get_item_performance tool"""
        result = await agent._execute_tool(
            "get_item_performance",
            {"start_date": "2024-01-01", "end_date": "2024-01-31", "top_n": 20}
        )

        assert "top_performers" in result or result == {}
        mock_repository.get_item_performance.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_returns_error(self, agent):
        """Test executing unknown tool returns error"""
        result = await agent._execute_tool(
            "unknown_tool",
            {"param": "value"}
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_tool_call_deduplication(self, agent):
        """Test tool calls are deduplicated"""
        params = {"start_date": "2024-01-01", "end_date": "2024-01-31"}

        # First call should succeed
        result1 = await agent._execute_tool("get_sales_trends", params)
        assert "error" not in result1

        # Second call with same params should be blocked
        result2 = await agent._execute_tool("get_sales_trends", params)
        assert "error" in result2
        assert "duplicate" in result2["error"].lower() or "budget" in result2["error"].lower()


class TestResponseParsing:
    """Test parsing Claude responses into structured insights"""

    @pytest.mark.asyncio
    async def test_parse_valid_json_response(self, agent):
        """Test parsing valid JSON response"""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text=json.dumps({
                    "opportunities": [
                        {
                            "id": "OPP-001",
                            "category": "revenue_growth",
                            "title": "Test Opportunity",
                            "description": "Test description",
                            "evidence": [
                                {
                                    "metric": "Revenue growth",
                                    "value": "10%",
                                    "source_tool": "get_sales_trends",
                                    "sample_size": 100,
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
                        }
                    ],
                    "risks": [],
                    "executive_summary": "Test summary",
                    "phase_completed": "synthesis"
                })
            )
        ]

        decision = await agent._parse_response(mock_response)

        assert decision.metadata["opportunities"][0]["id"] == "OPP-001"
        assert len(decision.metadata["opportunities"]) == 1

    @pytest.mark.asyncio
    async def test_parse_json_in_code_block(self, agent):
        """Test parsing JSON wrapped in markdown code block"""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text=f"""```json
{json.dumps({
    "opportunities": [],
    "risks": [],
    "executive_summary": "Summary",
    "phase_completed": "discovery"
})}
```"""
            )
        ]

        decision = await agent._parse_response(mock_response)

        assert decision.metadata["executive_summary"] == "Summary"

    @pytest.mark.asyncio
    async def test_parse_invalid_json_returns_error(self, agent):
        """Test parsing invalid JSON returns error decision"""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text="This is not valid JSON { broken"
            )
        ]

        decision = await agent._parse_response(mock_response)

        assert decision.confidence == 0.0
        assert decision.metadata["error"] == "JSON parse error"


class TestDataGathering:
    """Test data gathering methods"""

    @pytest.mark.asyncio
    async def test_gather_data(self, agent):
        """Test gathering analysis context"""
        context = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "compare_to_previous": True,
            "trigger": "manual"
        }

        data = await agent._gather_data(context)

        assert data["start_date"] == "2024-01-01"
        assert data["end_date"] == "2024-01-31"
        assert data["compare_to_previous"] is True

    @pytest.mark.asyncio
    async def test_build_prompt(self, agent):
        """Test building analysis prompt"""
        data = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "compare_to_previous": False
        }

        context = {"trigger": "manual"}

        prompt = await agent._build_prompt(data, context)

        assert "2024-01-01" in prompt
        assert "2024-01-31" in prompt
        assert "opportunities" in prompt.lower()
        assert "risks" in prompt.lower()


class TestCheckpoints:
    """Test checkpoint system for graceful degradation"""

    def test_save_checkpoint(self, agent):
        """Test saving analysis checkpoint"""
        from app.models.strategic_insights import Opportunity, Risk, Evidence

        opportunities = [
            Opportunity(
                id="OPP-001",
                category="revenue_growth",
                title="Test",
                description="Test description",
                evidence=[
                    Evidence(
                        metric="Test",
                        value="10%",
                        source_tool="test",
                        sample_size=100,
                        statistically_significant=True
                    )
                ],
                impact_min=10000,
                impact_max=30000,
                impact_expected=20000,
                assumptions=["Test"],
                confidence=0.8,
                actionable_steps=["Step 1"],
                timeline="1 week",
                effort="low"
            )
        ]

        agent.save_checkpoint(opportunities, [], "discovery")

        assert len(agent.checkpoints) == 1
        assert agent.checkpoints[0].phase == "discovery"
        assert len(agent.checkpoints[0].opportunities) == 1
