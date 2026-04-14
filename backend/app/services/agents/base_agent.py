"""
Base Agent Class - Abstract Template for All Autonomous Agents

Provides:
- Tool-calling loop pattern (similar to chatbot_service.py)
- Decision structure and parsing
- Approval logic framework
- Common utilities for agents

All agents (Inventory, Financial, Kitchen) extend this class.
"""

import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime
from pydantic import BaseModel, Field

from anthropic import Anthropic
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ===== Decision Data Structures =====

class Action(BaseModel):
    """
    Represents a single action an agent wants to take

    Examples:
    - Create purchase order
    - Send waste alert
    - Update stock level
    - Flag revenue anomaly
    """
    action_type: str = Field(..., description="Type of action: purchase_order, waste_alert, etc.")
    data: Dict[str, Any] = Field(..., description="Action-specific data payload")
    estimated_cost: float = Field(0.0, description="Financial impact in paise (0 for informational)")
    reasoning: str = Field(..., description="Why this action is recommended")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Agent confidence (0.0 to 1.0)")

    def requires_approval(self) -> bool:
        """
        Determine if action requires manual approval

        Approval thresholds:
        - High cost (>50000 paise = ₹500): Always require approval
        - Medium cost (20000-50000 paise = ₹200-₹500) + low confidence (<0.8): Require approval
        - Informational actions (cost=0): Auto-execute
        - Low cost + high confidence: Auto-execute

        Returns:
            True if approval needed, False if can auto-execute
        """
        # Informational actions (alerts, logs)
        if self.estimated_cost == 0:
            return False

        # High-cost actions always need approval
        if self.estimated_cost > 50000:  # > ₹500
            return True

        # Medium-cost with low confidence
        if self.estimated_cost > 20000 and self.confidence < 0.8:  # ₹200-₹500 range
            return True

        # Low-cost, high-confidence: auto-execute
        return False


class AgentDecision(BaseModel):
    """
    Complete decision output from an agent

    Contains:
    - List of recommended actions
    - Overall reasoning
    - Aggregate confidence score
    - Metadata (timestamp, agent name, etc.)
    """
    actions: List[Action] = Field(default_factory=list, description="List of recommended actions")
    reasoning: str = Field("", description="Overall reasoning for decisions")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Overall confidence score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def has_high_priority_actions(self) -> bool:
        """Check if any actions require immediate attention"""
        return any(
            action.estimated_cost > 50000 or action.confidence < 0.7
            for action in self.actions
        )

    def get_approval_required_count(self) -> int:
        """Count how many actions need approval"""
        return sum(1 for action in self.actions if action.requires_approval())


# ===== Base Agent Class =====

class BaseAgent(ABC):
    """
    Abstract base class for all autonomous agents

    Subclasses must implement:
    - _gather_data(): Fetch data needed for decision-making
    - _build_prompt(): Construct prompt for Claude
    - _execute_tool(): Execute tool calls from Claude
    - _parse_response(): Parse Claude's response into AgentDecision

    Tool-calling loop pattern (from chatbot_service.py):
    1. Build prompt with context
    2. Call Claude with tools
    3. While response contains tool_use:
        a. Execute tools
        b. Append results to messages
        c. Call Claude again
    4. Parse final response into AgentDecision
    """

    def __init__(self, agent_name: str, max_tokens: int = 4096):
        """
        Initialize base agent

        Args:
            agent_name: Unique identifier for this agent
            max_tokens: Max output tokens per API call (subclasses may override for long outputs)
        """
        self.agent_name = agent_name
        self.client = Anthropic(api_key=settings.CLAUDE_API_KEY)
        # Use insights model (Sonnet) for better tool calling
        self.model = settings.INSIGHTS_MODEL if settings.INSIGHTS_MODEL else settings.CHATBOT_MODEL
        self.max_iterations = 10  # Prevent infinite loops
        self.max_tokens = max_tokens
        self.tools: List[Dict] = []  # Tool definitions (override in subclass)
        self.system_prompt = ""  # System instructions (override in subclass)

    async def execute(self, context: Dict[str, Any]) -> AgentDecision:
        """
        Main execution entry point

        Args:
            context: Execution context (trigger type, timestamp, etc.)

        Returns:
            AgentDecision with recommended actions
        """
        logger.info(f"Executing {self.agent_name} agent")

        try:
            # Persist context for tool execution paths (subclasses may consult it).
            self._execution_context = context

            # Step 1: Gather data
            data = await self._gather_data(context)

            # Step 2: Build prompt
            prompt = await self._build_prompt(data, context)

            # Step 3: Tool-calling loop with Claude
            decision = await self._run_agent_loop(prompt)

            # Step 4: Add metadata
            decision.metadata.update({
                'agent_name': self.agent_name,
                'timestamp': datetime.utcnow().isoformat(),
                'trigger': context.get('trigger', 'unknown')
            })

            logger.info(
                f"{self.agent_name} completed: {len(decision.actions)} actions, "
                f"{decision.get_approval_required_count()} need approval"
            )

            return decision

        except Exception as e:
            logger.error(f"{self.agent_name} execution failed: {e}", exc_info=True)

            # Return empty decision on failure
            return AgentDecision(
                actions=[],
                reasoning=f"Agent execution failed: {str(e)}",
                confidence=0.0,
                metadata={
                    'error': str(e),
                    'agent_name': self.agent_name
                }
            )

    async def _run_agent_loop(self, initial_prompt: str) -> AgentDecision:
        """
        Run tool-calling loop with Claude

        Pattern from chatbot_service.py (lines 795-825):
        - Call Claude with tools
        - If stop_reason is "tool_use", execute tools and continue
        - Repeat until stop_reason is "end_turn"
        - Parse final response

        Args:
            initial_prompt: Initial prompt for Claude

        Returns:
            Parsed AgentDecision
        """
        messages = [{"role": "user", "content": initial_prompt}]
        iterations = 0
        self._last_tool_results: Dict[str, Any] = {}

        while iterations < self.max_iterations:
            iterations += 1

            # Call Claude
            logger.info(f"{self.agent_name} calling Claude with {len(self.tools)} tools, model={self.model}")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                tools=self.tools if self.tools else None,
                messages=messages
            )

            logger.info(f"{self.agent_name} iteration {iterations}: stop_reason={response.stop_reason}, blocks={len(response.content)}")

            # If no tools used, we're done
            if response.stop_reason != "tool_use":
                logger.info(f"{self.agent_name} finished without tool use")
                break

            # Execute tool calls
            tool_results = await self._process_tool_calls(response.content)

            # Append to conversation
            # Serialize content blocks properly for Anthropic SDK
            content_serialized = []
            for block in response.content:
                if hasattr(block, 'model_dump'):
                    content_serialized.append(block.model_dump(mode='json'))
                else:
                    content_serialized.append(block)

            messages.append({"role": "assistant", "content": content_serialized})
            messages.append({"role": "user", "content": tool_results})

        # Parse final response
        decision = await self._parse_response(response)
        return decision

    async def _process_tool_calls(self, content_blocks: List[Any]) -> List[Dict]:
        """
        Process tool use blocks from Claude's response

        Args:
            content_blocks: Response content blocks

        Returns:
            Tool results to send back to Claude
        """
        tool_results = []

        for block in content_blocks:
            if block.type == "tool_use":
                try:
                    # Execute tool
                    result = await self._execute_tool(block.name, block.input)
                    # Store raw result for _parse_response (e.g. InventoryAgent uses calculate_reorder_needs)
                    if not hasattr(self, "_last_tool_results"):
                        self._last_tool_results = {}
                    self._last_tool_results[block.name] = result

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })

                except Exception as e:
                    logger.error(f"Tool execution failed: {block.name}, {e}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {str(e)}",
                        "is_error": True
                    })

        return tool_results

    # ===== Abstract Methods (must be implemented by subclasses) =====

    @abstractmethod
    async def _gather_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gather data needed for agent decision-making

        Examples:
        - InventoryAgent: Fetch current inventory levels, forecasts
        - FinancialAgent: Fetch yesterday's orders, calculate metrics

        Args:
            context: Execution context

        Returns:
            Dictionary of data for prompt building
        """
        pass

    @abstractmethod
    async def _build_prompt(self, data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Build prompt for Claude based on gathered data

        Args:
            data: Data from _gather_data()
            context: Execution context

        Returns:
            Formatted prompt string
        """
        pass

    @abstractmethod
    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a tool call from Claude

        Args:
            tool_name: Name of tool to execute
            tool_input: Tool input parameters

        Returns:
            Tool execution result (will be stringified)
        """
        pass

    @abstractmethod
    async def _parse_response(self, response: Any) -> AgentDecision:
        """
        Parse Claude's final response into AgentDecision

        Args:
            response: Claude API response object

        Returns:
            Structured AgentDecision
        """
        pass
