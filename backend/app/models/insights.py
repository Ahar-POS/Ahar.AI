from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class InsightsRequest(BaseModel):
    """Request schema for generating insights"""
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    scope: List[str] = Field(
        default=["financial", "inventory", "operational"],
        description="Analysis scope: financial, inventory, and/or operational"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "scope": ["financial", "inventory", "operational"]
            }
        }


class Issue(BaseModel):
    """Critical issue identified by AI analysis"""
    id: str = Field(..., description="Unique issue identifier")
    category: str = Field(..., description="Category: financial, inventory, or operational")
    title: str = Field(..., description="Brief title summarizing the issue")
    root_cause: str = Field(..., description="Detailed explanation of why this is happening")
    impact: str = Field(..., description="Impact description (e.g., '₹50,000/month revenue loss')")
    recommendation: str = Field(..., description="Specific actionable steps to fix the issue")
    priority: str = Field(..., description="Priority level: high, medium, or low")
    estimated_savings: int = Field(..., description="Estimated monthly savings in paise")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "fin_001",
                "category": "financial",
                "title": "High Cancellation Revenue Loss",
                "root_cause": "₹25,000 lost from 45 cancelled orders in the period. Pattern shows cancellations spike during peak hours (7-9 PM) when kitchen is overwhelmed.",
                "impact": "₹25,000/month revenue loss",
                "recommendation": "Implement order confirmation system and analyze cancellation patterns by staff/time. Consider adding kitchen capacity during peak hours.",
                "priority": "high",
                "estimated_savings": 1750000  # ₹17,500 in paise (70% recoverable)
            }
        }


class FinancialSummary(BaseModel):
    """Summary of financial metrics"""
    total_revenue: int = Field(..., description="Total revenue in paise")
    revenue_loss: int = Field(..., description="Revenue loss from cancellations/issues in paise")
    avg_order_value: int = Field(..., description="Average order value in paise")
    cancelled_orders_count: int = Field(default=0, description="Number of cancelled orders")
    discount_amount: int = Field(default=0, description="Total discounts given in paise")


class InventorySummary(BaseModel):
    """Summary of inventory metrics"""
    total_stock_value: int = Field(..., description="Total inventory value in paise")
    waste_value: int = Field(..., description="Estimated waste value in paise")
    low_stock_items: int = Field(..., description="Number of items below reorder level")
    near_expiry_items: int = Field(default=0, description="Number of items near expiry")


class OperationalSummary(BaseModel):
    """Summary of operational metrics"""
    avg_kitchen_time_mins: float = Field(..., description="Average kitchen preparation time in minutes")
    table_turnover_rate: float = Field(..., description="Average table turnover rate")
    staff_efficiency_score: float = Field(..., description="Staff efficiency score (0-10)")
    orders_completed: int = Field(default=0, description="Total orders completed")
    avg_fulfillment_time_mins: Optional[float] = Field(None, description="Average order fulfillment time")


class AnalysisPeriod(BaseModel):
    """Analysis time period"""
    start: str = Field(..., description="Start date")
    end: str = Field(..., description="End date")


class InsightsResponse(BaseModel):
    """Response schema for insights generation"""
    critical_issues: List[Issue] = Field(..., description="List of critical issues identified")
    financial_summary: FinancialSummary = Field(..., description="Financial metrics summary")
    inventory_summary: InventorySummary = Field(..., description="Inventory metrics summary")
    operational_summary: OperationalSummary = Field(..., description="Operational metrics summary")
    estimated_monthly_savings: int = Field(..., description="Total estimated monthly savings in paise")
    analysis_period: AnalysisPeriod = Field(..., description="Analysis time period")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when insights were generated")
    cache_key: Optional[str] = Field(None, description="Cache key for retrieving cached insights")

    class Config:
        json_schema_extra = {
            "example": {
                "critical_issues": [
                    {
                        "id": "fin_001",
                        "category": "financial",
                        "title": "High Cancellation Revenue Loss",
                        "root_cause": "Analysis shows pattern",
                        "impact": "₹25,000/month",
                        "recommendation": "Implement confirmation system",
                        "priority": "high",
                        "estimated_savings": 1750000
                    }
                ],
                "financial_summary": {
                    "total_revenue": 50000000,
                    "revenue_loss": 7500000,
                    "avg_order_value": 45000,
                    "cancelled_orders_count": 45,
                    "discount_amount": 2500000
                },
                "inventory_summary": {
                    "total_stock_value": 12500000,
                    "waste_value": 1500000,
                    "low_stock_items": 8,
                    "near_expiry_items": 3
                },
                "operational_summary": {
                    "avg_kitchen_time_mins": 18.5,
                    "table_turnover_rate": 2.5,
                    "staff_efficiency_score": 7.2,
                    "orders_completed": 850
                },
                "estimated_monthly_savings": 12500000,
                "analysis_period": {
                    "start": "2024-01-01",
                    "end": "2024-01-31"
                },
                "generated_at": "2024-02-01T10:00:00Z",
                "cache_key": "insights_abc123"
            }
        }


class TokenUsage(BaseModel):
    """Token usage information"""
    input_tokens: int = Field(..., description="Number of input tokens used")
    output_tokens: int = Field(..., description="Number of output tokens generated")
    total_cost: Optional[float] = Field(None, description="Estimated cost in USD")


class InsightsResponseWithUsage(BaseModel):
    """Complete response with insights and token usage"""
    insights: InsightsResponse
    usage: Optional[TokenUsage] = None
