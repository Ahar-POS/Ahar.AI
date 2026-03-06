"""
Strategic Analysis Agent

Implements Mitigation #2 (Tool Call Efficiency) and #3 (Prompt Caching)

Autonomous agent that iteratively explores restaurant data to identify
business opportunities and risks using 8 analytical tools.

Key features:
- Tool call tracking with deduplication
- Prompt caching for cost optimization
- Phased prompting (discovery → investigation → synthesis)
- Early termination when confidence threshold met
- Evidence-based insight generation
"""

import logging
import json
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.services.agents.base_agent import BaseAgent, AgentDecision
from app.repositories.strategic_analytics_repository import StrategicAnalyticsRepository
from app.core.config import get_settings
from app.models.strategic_insights import (
    Opportunity,
    Risk,
    Evidence,
    StrategicInsights,
    AnalysisPeriod,
    AnalysisCheckpoint
)

logger = logging.getLogger(__name__)
settings = get_settings()


class ToolCallTracker:
    """
    Tracks tool calls to prevent duplication and enforce budgets

    Implements Mitigation #2: Tool call efficiency
    """

    def __init__(self, max_calls: int = 15):
        self.max_calls = max_calls
        self.call_history: List[str] = []
        self.call_count = 0

    def validate_call(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """
        Validate that a tool call is allowed

        Args:
            tool_name: Name of the tool
            params: Tool parameters

        Returns:
            True if call is allowed, False if duplicate or budget exceeded
        """
        # Create signature for deduplication
        param_str = json.dumps(params, sort_keys=True)
        signature = f"{tool_name}_{hashlib.md5(param_str.encode()).hexdigest()}"

        # Check for duplicate
        if signature in self.call_history:
            logger.warning(f"Duplicate tool call blocked: {tool_name} with {params}")
            return False

        # Check budget
        if self.call_count >= self.max_calls:
            logger.warning(f"Tool call budget exceeded: {self.call_count}/{self.max_calls}")
            return False

        # Record call
        self.call_history.append(signature)
        self.call_count += 1
        return True

    def get_remaining_calls(self) -> int:
        """Get number of remaining allowed calls"""
        return max(0, self.max_calls - self.call_count)


class StrategicAnalysisAgent(BaseAgent):
    """
    Strategic analysis agent for identifying opportunities and risks

    Uses iterative tool calling to explore data and form hypotheses
    """

    def __init__(self, repository: StrategicAnalyticsRepository, model: str = "claude-sonnet-4-5"):
        """
        Initialize strategic analysis agent

        Args:
            repository: Strategic analytics repository for data access
            model: Claude model to use (defaults to Opus 4.6 for deep reasoning)
        """
        max_out = getattr(settings, "STRATEGIC_INSIGHTS_MAX_OUTPUT_TOKENS", 16384)
        super().__init__(agent_name="StrategicAnalysisAgent", max_tokens=max_out)
        self.repository = repository
        self.model = model
        self.max_iterations = settings.STRATEGIC_INSIGHTS_MAX_ITERATIONS
        self.tool_tracker = ToolCallTracker(max_calls=settings.STRATEGIC_INSIGHTS_MAX_TOOL_CALLS)
        self.current_phase = "discovery"
        self.checkpoints: List[AnalysisCheckpoint] = []

        # Define 8 analytical tools
        self.tools = [
            {
                "name": "get_sales_trends",
                "description": "Get sales trends, revenue patterns, and growth signals. Returns daily/weekly trends, order type breakdown, and peak hours analysis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format"
                        },
                        "granularity": {
                            "type": "string",
                            "enum": ["daily", "weekly", "monthly"],
                            "description": "Granularity of trends (default: daily)"
                        }
                    },
                    "required": ["start_date", "end_date"]
                }
            },
            {
                "name": "get_item_performance",
                "description": "Analyze menu item performance. Returns top/bottom performers, pricing opportunities, and menu optimization insights.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                        "top_n": {"type": "integer", "description": "Number of top/bottom items (default: 20)"}
                    },
                    "required": ["start_date", "end_date"]
                }
            },
            {
                "name": "get_inventory_risks",
                "description": "Identify inventory risks including waste, stockouts, and expiry issues. Returns waste analysis, low stock items, and overstock situations.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                    },
                    "required": ["start_date", "end_date"]
                }
            },
            {
                "name": "get_supplier_patterns",
                "description": "Analyze supplier cost trends, reliability, and lead times. Returns supplier spend concentration, delivery patterns, and negotiation opportunities.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                    },
                    "required": ["start_date", "end_date"]
                }
            },
            {
                "name": "get_customer_behavior",
                "description": "Understand customer ordering patterns and preferences. Returns peak times, weekday/weekend patterns, category preferences, and upsell opportunities.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                    },
                    "required": ["start_date", "end_date"]
                }
            },
            {
                "name": "get_operational_metrics",
                "description": "Measure operational efficiency including kitchen performance and order completion. Returns kitchen times, completion rates, and efficiency benchmarks.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                    },
                    "required": ["start_date", "end_date"]
                }
            },
            {
                "name": "get_financial_health",
                "description": "Analyze financial health metrics including revenue, costs, and margins. Returns profitability analysis and cost structure.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                    },
                    "required": ["start_date", "end_date"]
                }
            },
            {
                "name": "get_comparative_analysis",
                "description": "Compare performance across time periods. Returns growth rates, trends, and key drivers of change.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "current_start": {"type": "string", "description": "Current period start (YYYY-MM-DD)"},
                        "current_end": {"type": "string", "description": "Current period end (YYYY-MM-DD)"},
                        "compare_start": {"type": "string", "description": "Comparison period start (YYYY-MM-DD)"},
                        "compare_end": {"type": "string", "description": "Comparison period end (YYYY-MM-DD)"}
                    },
                    "required": ["current_start", "current_end", "compare_start", "compare_end"]
                }
            }
        ]

        # System prompt with phased approach
        # Mark for caching to implement Mitigation #3
        self.system_prompt = """You are a strategic business analyst for a restaurant. Your goal is to identify HIGH-IMPACT opportunities and risks by iteratively exploring the data.

**Analysis Framework - 3 Phases:**

**Phase 1: Discovery (iterations 1-5)**
- Call get_sales_trends, get_financial_health, get_item_performance
- Build baseline understanding of the business
- Identify obvious patterns or anomalies

**Phase 2: Investigation (iterations 6-10)**
- Deep dive into interesting signals from Phase 1
- Call get_customer_behavior, get_supplier_patterns, get_inventory_risks
- Form hypotheses about opportunities and risks
- Cross-reference data to validate patterns

**Phase 3: Synthesis (iterations 11-15)**
- Call get_comparative_analysis, get_operational_metrics
- Validate hypotheses with additional data
- Calculate impact estimates with assumptions
- Generate final insights with evidence

**Critical Requirements:**

1. **Evidence-Based Insights**: Every opportunity/risk MUST have:
   - Minimum 2 pieces of evidence from different tools
   - Specific metrics and values (not vague statements)
   - Sample sizes and statistical context
   - Clear assumptions for impact estimates

2. **Impact Estimates**: Provide min/max/expected in paise
   - Use conservative assumptions (pessimistic for opportunities, optimistic for risks)
   - State all assumptions explicitly
   - Show your calculation logic

3. **Actionability**: Each insight needs:
   - Concrete steps (not generic advice)
   - Realistic timelines
   - Effort estimates

4. **Tool Efficiency**:
   - You have max 15 tool calls - use them wisely
   - Don't repeat identical queries
   - Focus on high-signal data

5. **Confidence Scoring**:
   - Assign confidence 0.0-1.0 based on:
     * Evidence quality and quantity
     * Sample size adequacy
     * Statistical significance
     * Pattern consistency
   - Flag insights <0.7 confidence

**Output Format:**

After completing your analysis, provide a JSON response with:

{
  "opportunities": [
    {
      "id": "OPP-001",
      "category": "revenue_growth|cost_reduction|operational_efficiency|menu_optimization|customer_experience",
      "title": "Short title under 70 chars",
      "description": "Detailed explanation",
      "evidence": [
        {
          "metric": "Metric name",
          "value": "Specific value",
          "source_tool": "tool_name",
          "sample_size": 450,
          "statistically_significant": true
        }
      ],
      "impact_min": 10000000,
      "impact_max": 30000000,
      "impact_expected": 20000000,
      "assumptions": ["Assumption 1", "Assumption 2"],
      "confidence": 0.85,
      "actionable_steps": ["Step 1", "Step 2"],
      "timeline": "1-2 weeks",
      "effort": "low|medium|high"
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "category": "supply_chain|financial|operational|compliance|market",
      "title": "Short title",
      "description": "Detailed explanation",
      "evidence": [...],
      "impact_min": 200000000,
      "impact_max": 600000000,
      "impact_expected": 400000000,
      "probability": 0.4,
      "severity": "low|medium|high|critical",
      "mitigation_steps": ["Step 1", "Step 2"],
      "timeline": "Within 2 weeks"
    }
  ],
  "executive_summary": "High-level summary for decision makers",
  "phase_completed": "discovery|investigation|synthesis"
}

**Quality Checklist:**
- [ ] Each insight has 2+ evidence points
- [ ] Impact estimates include min/max/expected
- [ ] All assumptions are stated
- [ ] Confidence scores are realistic
- [ ] Actionable steps are specific
- [ ] No duplicate tool calls
- [ ] Statistical significance considered

Focus on finding 3-7 opportunities and 2-5 risks with strong evidence and high business impact."""

    async def _gather_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gather initial context for analysis

        Args:
            context: Execution context with date range

        Returns:
            Dictionary with analysis parameters
        """
        return {
            "start_date": context.get("start_date"),
            "end_date": context.get("end_date"),
            "compare_to_previous": context.get("compare_to_previous", False)
        }

    async def _build_prompt(self, data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Build initial prompt for Claude

        Args:
            data: Data from _gather_data()
            context: Execution context

        Returns:
            Formatted prompt string
        """
        start_date = data["start_date"]
        end_date = data["end_date"]

        # Calculate previous period for comparison
        from datetime import datetime, timedelta
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        period_days = (end_dt - start_dt).days

        prev_end = start_dt - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days)

        prompt = f"""Analyze restaurant performance for the period {start_date} to {end_date} ({period_days} days).

Previous period for comparison: {prev_start.strftime('%Y-%m-%d')} to {prev_end.strftime('%Y-%m-%d')}

Your mission:
1. Identify 3-7 HIGH-IMPACT business opportunities (revenue growth, cost reduction, efficiency gains)
2. Identify 2-5 CRITICAL risks (supply chain, financial, operational issues)
3. Provide evidence-based insights with specific metrics and actionable recommendations

Use the 8 analytical tools to explore the data iteratively. Follow the 3-phase framework in your system prompt.

You have a maximum of 15 tool calls. Use them strategically to build a comprehensive picture.

Begin with Phase 1: Discovery. Call get_sales_trends, get_financial_health, and get_item_performance to establish baseline understanding."""

        return prompt

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a tool call

        Args:
            tool_name: Name of tool to execute
            tool_input: Tool input parameters

        Returns:
            Tool execution result
        """
        # Validate tool call
        if not self.tool_tracker.validate_call(tool_name, tool_input):
            return {
                "error": "Tool call blocked - either duplicate or budget exceeded",
                "remaining_calls": self.tool_tracker.get_remaining_calls()
            }

        logger.info(f"Executing tool: {tool_name} with {tool_input}")

        # Execute tool via repository
        try:
            if tool_name == "get_sales_trends":
                result = await self.repository.get_sales_trends(**tool_input)
            elif tool_name == "get_item_performance":
                result = await self.repository.get_item_performance(**tool_input)
            elif tool_name == "get_inventory_risks":
                result = await self.repository.get_inventory_risks(**tool_input)
            elif tool_name == "get_supplier_patterns":
                result = await self.repository.get_supplier_patterns(**tool_input)
            elif tool_name == "get_customer_behavior":
                result = await self.repository.get_customer_behavior(**tool_input)
            elif tool_name == "get_operational_metrics":
                result = await self.repository.get_operational_metrics(**tool_input)
            elif tool_name == "get_financial_health":
                result = await self.repository.get_financial_health(**tool_input)
            elif tool_name == "get_comparative_analysis":
                result = await self.repository.get_comparative_analysis(**tool_input)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {e}", exc_info=True)
            return {"error": str(e)}

    async def _parse_response(self, response: Any) -> AgentDecision:
        """
        Parse Claude's final response into structured insights

        Args:
            response: Claude API response object

        Returns:
            AgentDecision (will be converted to StrategicInsights later)
        """
        # Extract text content from response
        text_content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                text_content += block.text

        logger.info(f"Parsing response, length: {len(text_content)}")

        # Try to extract JSON from response
        try:
            # Find JSON block in markdown code blocks or raw JSON.
            # NOTE: Do not try to regex-match braces; it truncates nested JSON.
            import re

            json_str: str

            # 1) Prefer ```json ... ``` fenced block content (capture the full block).
            fenced = re.search(r"```json\s*([\s\S]*?)\s*```", text_content, re.IGNORECASE)
            if fenced:
                json_str = fenced.group(1).strip()
            else:
                # 2) Next, take the substring from the first "{" to the last "}".
                # This is robust against pre/postamble text.
                first = text_content.find("{")
                last = text_content.rfind("}")
                if first != -1 and last != -1 and last > first:
                    json_str = text_content[first:last + 1].strip()
                else:
                    # 3) Fallback: entire response might be JSON.
                    json_str = text_content.strip()

            def _repair_common_json_issues(s: str) -> str:
                """
                Best-effort repair for common model JSON issues:
                - trailing commas before } or ]
                - accidental ``` fences included
                """
                # Remove any stray code fences if the model nested them
                s = re.sub(r"^```(?:json)?\s*", "", s.strip(), flags=re.IGNORECASE)
                s = re.sub(r"\s*```$", "", s.strip())
                # Remove trailing commas:  { "a": 1, } or [1,2,]
                s = re.sub(r",\s*([}\]])", r"\1", s)
                return s

            repaired = _repair_common_json_issues(json_str)
            parsed = json.loads(repaired)

            if not isinstance(parsed, dict):
                raise json.JSONDecodeError("Top-level JSON must be an object", json_str, 0)

            logger.info(
                f"Parsed {len(parsed.get('opportunities', []))} opportunities, "
                f"{len(parsed.get('risks', []))} risks"
            )

            # Store parsed data in metadata for service layer to use
            return AgentDecision(
                actions=[],  # Not using Action structure for this agent
                reasoning=parsed.get("executive_summary", ""),
                confidence=1.0,
                metadata={
                    "opportunities": parsed.get("opportunities", []),
                    "risks": parsed.get("risks", []),
                    "executive_summary": parsed.get("executive_summary", ""),
                    "phase_completed": parsed.get("phase_completed", "synthesis"),
                    "iterations_used": self.tool_tracker.call_count
                }
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {e}")
            logger.debug(f"Response text: {text_content[:1500]}")

            return AgentDecision(
                actions=[],
                reasoning="Failed to parse structured response",
                confidence=0.0,
                metadata={
                    "error": "JSON parse error",
                    "raw_response": text_content[:1000],
                    "opportunities": [],
                    "risks": []
                }
            )

    def save_checkpoint(self, opportunities: List[Opportunity], risks: List[Risk], phase: str):
        """
        Save checkpoint for graceful degradation

        Implements Mitigation #4: Save partial insights
        """
        checkpoint = AnalysisCheckpoint(
            phase=phase,
            completed=True,
            opportunities=opportunities,
            risks=risks,
            iterations_used=self.tool_tracker.call_count
        )
        self.checkpoints.append(checkpoint)
        logger.info(f"Checkpoint saved: {phase}, {len(opportunities)} opps, {len(risks)} risks")
