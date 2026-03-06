"""
Strategic Insights Data Models

Implements Mitigation #1 (Hallucination Prevention) and #7 (Impact Estimate Validation)

Data structures for agent-based strategic analysis system that provides:
- Opportunity detection with impact estimates
- Risk identification with probability and severity
- Evidence-based insights with statistical validation
- Checkpointing for graceful degradation
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """
    Evidence supporting an insight

    Implements Mitigation #1: Every insight MUST cite specific evidence
    with metrics, values, and statistical context
    """
    metric: str = Field(..., description="Metric name (e.g., 'Lunch beverage attach rate')")
    value: str = Field(..., description="Metric value (e.g., '60%', '₹2L/month')")
    source_tool: str = Field(..., description="Tool that provided this data")
    sample_size: int = Field(..., description="Number of data points in sample")
    confidence_interval: Optional[str] = Field(
        None,
        description="Confidence interval if applicable (e.g., '±5%')"
    )
    statistically_significant: bool = Field(
        default=True,
        description="Whether the pattern exceeds significance threshold"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "metric": "Lunch beverage attach rate",
                "value": "60%",
                "source_tool": "get_customer_behavior",
                "sample_size": 450,
                "confidence_interval": "±3%",
                "statistically_significant": True
            }
        }


class Opportunity(BaseModel):
    """
    Business opportunity identified by strategic analysis

    Implements Mitigation #7: Impact estimates with min/max/expected ranges
    and explicit assumptions
    """
    id: str = Field(..., description="Unique opportunity ID (e.g., 'OPP-001')")
    category: Literal[
        "revenue_growth",
        "cost_reduction",
        "operational_efficiency",
        "menu_optimization",
        "customer_experience"
    ] = Field(..., description="Opportunity category")
    title: str = Field(..., description="Brief title (under 70 chars)")
    description: str = Field(..., description="Detailed explanation of the opportunity")
    evidence: List[Evidence] = Field(
        ...,
        min_length=2,
        description="Supporting evidence (minimum 2 data points required)"
    )
    impact_min: int = Field(..., description="Minimum estimated impact in paise (pessimistic)")
    impact_max: int = Field(..., description="Maximum estimated impact in paise (optimistic)")
    impact_expected: int = Field(..., description="Expected impact in paise (realistic)")
    assumptions: List[str] = Field(
        ...,
        description="Key assumptions underlying the impact estimate"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0). <0.7 flagged for review"
    )
    actionable_steps: List[str] = Field(
        ...,
        description="Concrete steps to capture this opportunity"
    )
    timeline: str = Field(..., description="Implementation timeline (e.g., '1-2 weeks')")
    effort: Literal["low", "medium", "high"] = Field(
        ...,
        description="Implementation effort level"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "OPP-001",
                "category": "revenue_growth",
                "title": "Increase beverage par levels during lunch",
                "description": "60% of lunch customers order beverages but inventory is stocked for 40% demand. Stockouts occur 3x per week, resulting in lost sales.",
                "evidence": [
                    {
                        "metric": "Lunch beverage attach rate",
                        "value": "60%",
                        "source_tool": "get_customer_behavior",
                        "sample_size": 450,
                        "statistically_significant": True
                    },
                    {
                        "metric": "Current stock allocation",
                        "value": "40%",
                        "source_tool": "get_inventory_risks",
                        "sample_size": 90,
                        "statistically_significant": True
                    }
                ],
                "impact_min": 15000000,  # ₹1.5L/month
                "impact_max": 25000000,  # ₹2.5L/month
                "impact_expected": 20000000,  # ₹2L/month
                "assumptions": [
                    "60% attach rate maintains with increased supply",
                    "Current stockouts represent 3 lost sales per day",
                    "Average beverage price ₹100"
                ],
                "confidence": 0.85,
                "actionable_steps": [
                    "Increase beverage par from 40% to 60% of lunch capacity",
                    "Monitor demand elasticity for 2 weeks",
                    "Adjust supplier order quantities"
                ],
                "timeline": "Implement within 1 week",
                "effort": "low"
            }
        }


class Risk(BaseModel):
    """
    Business risk identified by strategic analysis

    Implements Mitigation #1: Evidence-based risk identification
    with probability, severity, and mitigation steps
    """
    id: str = Field(..., description="Unique risk ID (e.g., 'RISK-001')")
    category: Literal[
        "supply_chain",
        "financial",
        "operational",
        "compliance",
        "market"
    ] = Field(..., description="Risk category")
    title: str = Field(..., description="Brief title (under 70 chars)")
    description: str = Field(..., description="Detailed explanation of the risk")
    evidence: List[Evidence] = Field(
        ...,
        min_length=2,
        description="Supporting evidence (minimum 2 data points required)"
    )
    impact_min: int = Field(..., description="Minimum potential loss in paise (optimistic)")
    impact_max: int = Field(..., description="Maximum potential loss in paise (pessimistic)")
    impact_expected: int = Field(..., description="Expected loss in paise (realistic)")
    probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability of occurrence (0.0-1.0)"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Risk severity level"
    )
    mitigation_steps: List[str] = Field(
        ...,
        description="Actionable steps to mitigate this risk"
    )
    timeline: str = Field(..., description="Timeframe to act (e.g., 'Within 2 weeks')")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "RISK-001",
                "category": "supply_chain",
                "title": "Single supplier dependency for high-margin items",
                "description": "80% of ingredient Y comes from Supplier X. Delivery times increased 60% in 3 months (2 days → 5 days).",
                "evidence": [
                    {
                        "metric": "Supplier concentration",
                        "value": "80% from single source",
                        "source_tool": "get_supplier_patterns",
                        "sample_size": 45,
                        "statistically_significant": True
                    },
                    {
                        "metric": "Lead time trend",
                        "value": "2 days → 5 days (+150%)",
                        "source_tool": "get_supplier_patterns",
                        "sample_size": 90,
                        "statistically_significant": True
                    }
                ],
                "impact_min": 300000000,  # -₹3L at risk
                "impact_max": 700000000,  # -₹7L at risk
                "impact_expected": 500000000,  # -₹5L at risk
                "probability": 0.4,
                "severity": "high",
                "mitigation_steps": [
                    "Qualify secondary supplier for ingredient Y",
                    "Negotiate backup capacity with Supplier Z",
                    "Increase safety stock for next 30 days"
                ],
                "timeline": "Act within 2 weeks"
            }
        }


class AnalysisPeriod(BaseModel):
    """Time period analyzed"""
    start: str = Field(..., description="Start date (YYYY-MM-DD)")
    end: str = Field(..., description="End date (YYYY-MM-DD)")
    duration_days: int = Field(..., description="Duration in days")


class AnalysisCheckpoint(BaseModel):
    """
    Checkpoint for graceful degradation

    Implements Mitigation #4: Save partial insights after each phase
    so users get value even if analysis fails partway through
    """
    phase: Literal["discovery", "investigation", "synthesis"] = Field(
        ...,
        description="Analysis phase"
    )
    completed: bool = Field(..., description="Whether this phase completed successfully")
    opportunities: List[Opportunity] = Field(
        default_factory=list,
        description="Opportunities identified so far"
    )
    risks: List[Risk] = Field(
        default_factory=list,
        description="Risks identified so far"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Checkpoint timestamp"
    )
    iterations_used: int = Field(default=0, description="Tool iterations used so far")


class StrategicInsights(BaseModel):
    """
    Complete strategic insights analysis output
    """
    opportunities: List[Opportunity] = Field(
        default_factory=list,
        description="Business opportunities identified"
    )
    risks: List[Risk] = Field(
        default_factory=list,
        description="Business risks identified"
    )
    executive_summary: str = Field(
        ...,
        description="High-level summary for decision makers"
    )
    analysis_period: AnalysisPeriod = Field(..., description="Analysis time period")
    iterations_used: int = Field(..., description="Number of agent iterations used")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Generation timestamp"
    )
    checkpoint: Optional[AnalysisCheckpoint] = Field(
        None,
        description="Last checkpoint (for partial results)"
    )


class TokenUsage(BaseModel):
    """Token usage and cost tracking"""
    input_tokens: int = Field(..., description="Input tokens used")
    output_tokens: int = Field(..., description="Output tokens generated")
    cached_tokens: int = Field(default=0, description="Cached tokens (prompt caching)")
    total_tokens: int = Field(..., description="Total tokens")
    model: str = Field(..., description="Model used")
    cost_usd: float = Field(..., description="Estimated cost in USD")


class StrategicInsightsResponse(BaseModel):
    """
    Complete response with insights and usage metadata
    """
    insights: StrategicInsights
    usage: TokenUsage
    cache_hit: bool = Field(
        default=False,
        description="Whether result was served from cache"
    )
    cache_key: Optional[str] = Field(
        None,
        description="Cache key for this analysis"
    )


class StrategicInsightsRequest(BaseModel):
    """Request schema for strategic insights generation"""
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    compare_to_previous: bool = Field(
        default=False,
        description="Whether to compare to previous period"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "compare_to_previous": True
            }
        }


class InsightFeedback(BaseModel):
    """
    User feedback on insights

    Implements Mitigation #8: Human feedback loop for continuous improvement
    """
    insight_id: str = Field(..., description="ID of the opportunity or risk")
    insight_type: Literal["opportunity", "risk"] = Field(..., description="Type of insight")
    helpful: bool = Field(..., description="Was this insight helpful?")
    action_taken: bool = Field(
        default=False,
        description="Did you take action based on this insight?"
    )
    actual_impact: Optional[int] = Field(
        None,
        description="Actual impact realized in paise (for tracking accuracy)"
    )
    comments: Optional[str] = Field(
        None,
        description="Additional feedback or context"
    )
    submitted_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Feedback submission timestamp"
    )
