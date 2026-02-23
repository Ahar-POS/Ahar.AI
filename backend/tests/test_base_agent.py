"""
Tests for BaseAgent class

Creates a mock agent to test:
- Agent execution flow
- Tool-calling loop
- Decision structure
- Approval logic
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any
from anthropic.types import Message, ContentBlock, TextBlock, ToolUseBlock, Usage

from app.services.agents.base_agent import BaseAgent, AgentDecision, Action


class MockAgent(BaseAgent):
    """Simple mock agent for testing BaseAgent pattern"""

    def __init__(self):
        super().__init__(agent_name="test_agent")
        self.tools = [
            {
                "name": "get_test_data",
                "description": "Get test data",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    }
                }
            }
        ]
        self.system_prompt = "You are a test agent for unit testing."

    async def _gather_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Gather test data"""
        return {
            'test_value': 42,
            'context_trigger': context.get('trigger', 'manual')
        }

    async def _build_prompt(self, data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Build test prompt"""
        return f"Analyze this data: {data['test_value']}"

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute mock tool"""
        if tool_name == "get_test_data":
            return {"result": f"Data for query: {tool_input.get('query', 'none')}"}
        raise ValueError(f"Unknown tool: {tool_name}")

    async def _parse_response(self, response: Any) -> AgentDecision:
        """Parse mock response"""
        # Extract text from response
        text_content = ""
        for block in response.content:
            if isinstance(block, TextBlock):
                text_content += block.text

        # Create mock decision
        return AgentDecision(
            actions=[
                Action(
                    action_type="test_action",
                    data={"message": "Test action from mock agent"},
                    estimated_cost=10000,  # ₹100
                    reasoning="This is a test action",
                    confidence=0.95
                )
            ],
            reasoning="Mock agent decision",
            confidence=0.95
        )


@pytest.mark.asyncio
async def test_action_approval_logic():
    """Test Action approval logic based on cost and confidence"""

    # Low cost, high confidence - should auto-execute
    action1 = Action(
        action_type="test",
        data={},
        estimated_cost=10000,  # ₹100
        reasoning="Test",
        confidence=0.9
    )
    assert action1.requires_approval() is False

    # High cost - should require approval
    action2 = Action(
        action_type="test",
        data={},
        estimated_cost=60000,  # ₹600
        reasoning="Test",
        confidence=0.95
    )
    assert action2.requires_approval() is True

    # Medium cost, low confidence - should require approval
    action3 = Action(
        action_type="test",
        data={},
        estimated_cost=30000,  # ₹300
        reasoning="Test",
        confidence=0.75
    )
    assert action3.requires_approval() is True

    # Informational (cost=0) - should auto-execute
    action4 = Action(
        action_type="alert",
        data={},
        estimated_cost=0,
        reasoning="Alert",
        confidence=0.5
    )
    assert action4.requires_approval() is False


@pytest.mark.asyncio
async def test_agent_decision_structure():
    """Test AgentDecision data structure"""

    decision = AgentDecision(
        actions=[
            Action(
                action_type="purchase_order",
                data={"material_id": "RM001", "quantity": 50},
                estimated_cost=55000,  # ₹550 (> ₹500 threshold)
                reasoning="Low stock",
                confidence=0.9
            ),
            Action(
                action_type="waste_alert",
                data={"material_id": "RM002"},
                estimated_cost=0,
                reasoning="Expiring soon",
                confidence=1.0
            )
        ],
        reasoning="Daily inventory check",
        confidence=0.9
    )

    assert len(decision.actions) == 2
    assert decision.get_approval_required_count() == 1  # Only purchase order
    assert decision.has_high_priority_actions() is True  # Purchase order is ₹550 > ₹500


@pytest.mark.asyncio
async def test_mock_agent_gather_data():
    """Test MockAgent data gathering"""
    agent = MockAgent()

    context = {'trigger': 'scheduled'}
    data = await agent._gather_data(context)

    assert data['test_value'] == 42
    assert data['context_trigger'] == 'scheduled'


@pytest.mark.asyncio
async def test_mock_agent_build_prompt():
    """Test MockAgent prompt building"""
    agent = MockAgent()

    data = {'test_value': 42}
    context = {}
    prompt = await agent._build_prompt(data, context)

    assert "42" in prompt
    assert "Analyze" in prompt


@pytest.mark.asyncio
async def test_mock_agent_execute_tool():
    """Test MockAgent tool execution"""
    agent = MockAgent()

    result = await agent._execute_tool("get_test_data", {"query": "test"})

    assert "test" in result["result"]


@pytest.mark.asyncio
async def test_mock_agent_execute_tool_error():
    """Test MockAgent tool execution with unknown tool"""
    agent = MockAgent()

    with pytest.raises(ValueError, match="Unknown tool"):
        await agent._execute_tool("unknown_tool", {})


@pytest.mark.asyncio
async def test_agent_execution_with_mock_claude():
    """Test full agent execution with mocked Claude API"""
    agent = MockAgent()

    # Mock Claude API response (no tool use, direct response)
    mock_response = Mock(spec=Message)
    mock_response.stop_reason = "end_turn"
    mock_response.content = [
        Mock(spec=TextBlock, type="text", text="Analysis complete")
    ]
    mock_response.usage = Mock(spec=Usage, input_tokens=100, output_tokens=50)

    # Patch the Claude client
    with patch.object(agent.client.messages, 'create', return_value=mock_response):
        decision = await agent.execute({'trigger': 'test'})

    # Verify decision structure
    assert isinstance(decision, AgentDecision)
    assert decision.metadata['agent_name'] == 'test_agent'
    assert decision.metadata['trigger'] == 'test'
    assert len(decision.actions) > 0


@pytest.mark.asyncio
async def test_agent_tool_calling_loop():
    """Test agent tool-calling loop with multiple iterations"""
    agent = MockAgent()

    # First response: tool use
    tool_use_response = Mock(spec=Message)
    tool_use_response.stop_reason = "tool_use"
    tool_use_response.content = [
        Mock(
            spec=ToolUseBlock,
            type="tool_use",
            id="tool_123",
            name="get_test_data",
            input={"query": "test"}
        )
    ]

    # Second response: end turn
    end_response = Mock(spec=Message)
    end_response.stop_reason = "end_turn"
    end_response.content = [
        Mock(spec=TextBlock, type="text", text="Done")
    ]

    # Mock client to return tool_use first, then end
    responses = [tool_use_response, end_response]
    with patch.object(agent.client.messages, 'create', side_effect=responses):
        decision = await agent.execute({'trigger': 'test'})

    # Should have completed successfully
    assert isinstance(decision, AgentDecision)


@pytest.mark.asyncio
async def test_agent_max_iterations():
    """Test that agent stops after max iterations"""
    agent = MockAgent()
    agent.max_iterations = 3

    # Mock response that always returns tool_use (infinite loop scenario)
    tool_use_response = Mock(spec=Message)
    tool_use_response.stop_reason = "tool_use"
    tool_use_response.content = [
        Mock(
            spec=ToolUseBlock,
            type="tool_use",
            id="tool_123",
            name="get_test_data",
            input={"query": "test"}
        )
    ]

    with patch.object(agent.client.messages, 'create', return_value=tool_use_response):
        decision = await agent.execute({'trigger': 'test'})

    # Should complete even with infinite loop (stops at max_iterations)
    assert isinstance(decision, AgentDecision)


@pytest.mark.asyncio
async def test_agent_execution_error_handling():
    """Test agent error handling during execution"""
    agent = MockAgent()

    # Mock Claude to raise an error
    with patch.object(agent.client.messages, 'create', side_effect=Exception("API Error")):
        decision = await agent.execute({'trigger': 'test'})

    # Should return error decision, not crash
    assert isinstance(decision, AgentDecision)
    assert len(decision.actions) == 0
    assert decision.confidence == 0.0
    assert "failed" in decision.reasoning.lower()
    assert "error" in decision.metadata
