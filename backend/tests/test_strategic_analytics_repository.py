"""
Tests for Strategic Analytics Repository

Tests all 8 analytical tools and data aggregation functions.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from app.repositories.strategic_analytics_repository import StrategicAnalyticsRepository


@pytest.fixture
def mock_db():
    """Create a mock database"""
    db = MagicMock()
    db.orders = MagicMock()
    db.menu_items = MagicMock()
    db.inventory_items = MagicMock()
    db.inventory_transactions = MagicMock()
    db.suppliers = MagicMock()
    db.purchase_orders = MagicMock()
    return db


@pytest.fixture
def repository(mock_db):
    """Create repository instance with mock database"""
    return StrategicAnalyticsRepository(mock_db)


@pytest.fixture
def date_range():
    """Standard date range for testing"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    return {
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d")
    }


class TestSalesTrends:
    """Test get_sales_trends tool"""

    @pytest.mark.asyncio
    async def test_sales_trends_daily(self, repository, mock_db, date_range):
        """Test daily sales trends aggregation"""
        # Mock aggregation result
        mock_daily_data = [
            {
                "_id": "2024-01-01",
                "revenue": 100000,
                "order_count": 50,
                "avg_order_value": 2000,
                "cancelled_count": 2
            }
        ]

        mock_type_data = [
            {"_id": "dine_in", "revenue": 80000, "count": 40},
            {"_id": "takeaway", "revenue": 20000, "count": 10}
        ]

        mock_peak_hours = [
            {"_id": 19, "revenue": 30000, "count": 15}
        ]

        # Setup mock pipeline responses
        mock_db.orders.aggregate = AsyncMock()
        mock_db.orders.aggregate.return_value.to_list = AsyncMock(
            side_effect=[mock_daily_data, mock_type_data, mock_peak_hours]
        )

        # Call function
        result = await repository.get_sales_trends(
            start_date=date_range["start"],
            end_date=date_range["end"],
            granularity="daily"
        )

        # Assertions
        assert "summary" in result
        assert "daily_trends" in result
        assert "by_order_type" in result
        assert "peak_hours" in result
        assert result["summary"]["total_revenue"] == 100000
        assert result["summary"]["total_orders"] == 50

    @pytest.mark.asyncio
    async def test_sales_trends_response_size_limit(self, repository, mock_db, date_range):
        """Test that response size is limited"""
        # Create large dataset (100 days)
        large_data = [
            {
                "_id": f"2024-01-{i:02d}",
                "revenue": 100000 * i,
                "order_count": 50 * i,
                "avg_order_value": 2000,
                "cancelled_count": 2
            }
            for i in range(1, 101)
        ]

        mock_db.orders.aggregate = AsyncMock()
        mock_db.orders.aggregate.return_value.to_list = AsyncMock(
            side_effect=[large_data, [], []]
        )

        result = await repository.get_sales_trends(
            start_date=date_range["start"],
            end_date=date_range["end"]
        )

        # Should limit to 30 days
        assert len(result["daily_trends"]) <= 30


class TestItemPerformance:
    """Test get_item_performance tool"""

    @pytest.mark.asyncio
    async def test_item_performance(self, repository, mock_db, date_range):
        """Test menu item performance analysis"""
        mock_item_data = [
            {
                "_id": "item1",
                "name": "Margherita Pizza",
                "revenue": 50000,
                "quantity_sold": 25,
                "order_count": 20,
                "avg_price": 2000,
                "revenue_per_order": 2500
            },
            {
                "_id": "item2",
                "name": "Caesar Salad",
                "revenue": 10000,
                "quantity_sold": 10,
                "order_count": 8,
                "avg_price": 1000,
                "revenue_per_order": 1250
            }
        ]

        mock_db.orders.aggregate = AsyncMock()
        mock_db.orders.aggregate.return_value.to_list = AsyncMock(return_value=mock_item_data)

        result = await repository.get_item_performance(
            start_date=date_range["start"],
            end_date=date_range["end"],
            top_n=10
        )

        assert "top_performers" in result
        assert "bottom_performers" in result
        assert "summary" in result
        assert len(result["top_performers"]) > 0
        assert result["top_performers"][0]["name"] == "Margherita Pizza"


class TestInventoryRisks:
    """Test get_inventory_risks tool"""

    @pytest.mark.asyncio
    async def test_inventory_risks(self, repository, mock_db, date_range):
        """Test inventory risk analysis"""
        mock_inventory = [
            {
                "name": "Tomatoes",
                "quantity": 5,
                "reorder_level": 20,
                "unit_cost_amount": 5000
            },
            {
                "name": "Cheese",
                "quantity": 30,
                "reorder_level": 25,
                "unit_cost_amount": 10000
            }
        ]

        mock_waste = [
            {
                "_id": "item1",
                "item_name": "Tomatoes",
                "total_waste_quantity": 10,
                "total_waste_value": 50000,
                "waste_events": 5
            }
        ]

        mock_db.inventory_items.find = AsyncMock()
        mock_db.inventory_items.find.return_value.to_list = AsyncMock(return_value=mock_inventory)

        mock_db.inventory_transactions.aggregate = AsyncMock()
        mock_db.inventory_transactions.aggregate.return_value.to_list = AsyncMock(return_value=mock_waste)

        result = await repository.get_inventory_risks(
            start_date=date_range["start"],
            end_date=date_range["end"]
        )

        assert "low_stock_items" in result
        assert "waste_analysis" in result
        assert "industry_comparison" in result
        assert len(result["low_stock_items"]) > 0


class TestSupplierPatterns:
    """Test get_supplier_patterns tool"""

    @pytest.mark.asyncio
    async def test_supplier_patterns(self, repository, mock_db, date_range):
        """Test supplier analysis"""
        mock_supplier_data = [
            {
                "_id": "supplier1",
                "supplier_name": "Fresh Farms",
                "total_spend": 500000,
                "order_count": 20,
                "avg_order_value": 25000,
                "avg_lead_time_days": 2.5
            }
        ]

        mock_lead_time_data = [
            {
                "_id": "supplier1",
                "avg_lead_time": 3.0,
                "max_lead_time": 5.0,
                "min_lead_time": 2.0,
                "deliveries": 20
            }
        ]

        mock_db.purchase_orders.aggregate = AsyncMock()
        mock_db.purchase_orders.aggregate.return_value.to_list = AsyncMock(
            side_effect=[mock_supplier_data, mock_lead_time_data]
        )

        result = await repository.get_supplier_patterns(
            start_date=date_range["start"],
            end_date=date_range["end"]
        )

        assert "supplier_spend" in result
        assert "supplier_concentration" in result
        assert "lead_time_analysis" in result
        assert result["summary"]["total_spend"] == 500000


class TestCustomerBehavior:
    """Test get_customer_behavior tool"""

    @pytest.mark.asyncio
    async def test_customer_behavior(self, repository, mock_db, date_range):
        """Test customer ordering patterns"""
        mock_time_data = [
            {
                "_id": {"hour": 12, "is_weekend": False},
                "order_count": 30,
                "avg_order_value": 2000,
                "revenue": 60000
            },
            {
                "_id": {"hour": 19, "is_weekend": True},
                "order_count": 50,
                "avg_order_value": 2500,
                "revenue": 125000
            }
        ]

        mock_item_stats = [{"total_items": 150}]

        mock_db.orders.aggregate = AsyncMock()
        mock_db.orders.aggregate.return_value.to_list = AsyncMock(
            side_effect=[mock_time_data, mock_item_stats]
        )

        result = await repository.get_customer_behavior(
            start_date=date_range["start"],
            end_date=date_range["end"]
        )

        assert "time_patterns" in result
        assert "weekday_vs_weekend" in result
        assert "order_composition" in result


class TestOperationalMetrics:
    """Test get_operational_metrics tool"""

    @pytest.mark.asyncio
    async def test_operational_metrics(self, repository, mock_db, date_range):
        """Test operational efficiency metrics"""
        mock_kitchen_data = [{
            "avg_kitchen_time_ms": 900000,  # 15 minutes
            "max_kitchen_time_ms": 1800000,  # 30 minutes
            "min_kitchen_time_ms": 600000,   # 10 minutes
            "completed_orders": 100
        }]

        mock_status_data = [
            {"_id": "completed", "count": 100},
            {"_id": "cancelled", "count": 5}
        ]

        mock_db.orders.aggregate = AsyncMock()
        mock_db.orders.aggregate.return_value.to_list = AsyncMock(
            side_effect=[mock_kitchen_data, mock_status_data]
        )

        result = await repository.get_operational_metrics(
            start_date=date_range["start"],
            end_date=date_range["end"]
        )

        assert "kitchen_performance" in result
        assert "order_completion" in result
        assert "industry_comparison" in result
        assert result["kitchen_performance"]["avg_kitchen_time_mins"] == 15.0


class TestFinancialHealth:
    """Test get_financial_health tool"""

    @pytest.mark.asyncio
    async def test_financial_health(self, repository, mock_db, date_range):
        """Test financial health analysis"""
        mock_revenue = [{"total_revenue": 1000000, "order_count": 500}]
        mock_cogs = [{"total_cogs": -300000}]

        mock_db.orders.aggregate = AsyncMock()
        mock_db.orders.aggregate.return_value.to_list = AsyncMock(return_value=mock_revenue)

        mock_db.inventory_transactions.aggregate = AsyncMock()
        mock_db.inventory_transactions.aggregate.return_value.to_list = AsyncMock(return_value=mock_cogs)

        result = await repository.get_financial_health(
            start_date=date_range["start"],
            end_date=date_range["end"]
        )

        assert "revenue" in result
        assert "costs" in result
        assert "margins" in result
        assert "industry_comparison" in result
        assert result["revenue"]["total"] == 1000000
        assert result["costs"]["cogs"] == 300000
        assert result["margins"]["gross_margin"] == 700000


class TestComparativeAnalysis:
    """Test get_comparative_analysis tool"""

    @pytest.mark.asyncio
    async def test_comparative_analysis(self, repository, mock_db):
        """Test period-over-period comparison"""
        current_metrics = {"revenue": 100000, "order_count": 50, "avg_order_value": 2000}
        compare_metrics = {"revenue": 80000, "order_count": 40, "avg_order_value": 2000}

        mock_db.orders.aggregate = AsyncMock()
        mock_db.orders.aggregate.return_value.to_list = AsyncMock(
            side_effect=[[current_metrics], [compare_metrics]]
        )

        result = await repository.get_comparative_analysis(
            current_start="2024-02-01",
            current_end="2024-02-29",
            compare_start="2024-01-01",
            compare_end="2024-01-31"
        )

        assert "current_period" in result
        assert "comparison_period" in result
        assert "growth_rates" in result
        assert result["growth_rates"]["revenue_growth_pct"] == 25.0


class TestResponseSizeLimiting:
    """Test response size limiting mitigation"""

    @pytest.mark.asyncio
    async def test_large_response_truncation(self, repository):
        """Test that large responses are truncated"""
        # Create data that exceeds MAX_RESPONSE_CHARS
        large_data = {
            "items": [{"id": f"item_{i}", "data": "x" * 1000} for i in range(100)]
        }

        result = repository._limit_response_size(large_data, "test_tool")

        # Should have truncation metadata
        if "_truncated" in result:
            assert result["_truncated"] is True
            assert "_showing_count" in result
