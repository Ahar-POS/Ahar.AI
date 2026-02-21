"""
Test script for insights generation
"""
import asyncio
import json
from datetime import datetime, timedelta
from app.core.database import connect_to_database
from app.services.insights_service import insights_service

async def test_insights():
    """Test insights generation"""

    # Connect to database
    await connect_to_database()

    # Set date range (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    print(f"\n{'='*60}")
    print(f"TESTING INSIGHTS GENERATION")
    print(f"{'='*60}")
    print(f"Date Range: {start_str} to {end_str}")
    print(f"Scope: financial, inventory, operational")
    print(f"{'='*60}\n")

    try:
        # Generate insights
        print("🔄 Generating insights (this may take 30-60 seconds)...\n")

        result = await insights_service.generate_insights(
            start_date=start_str,
            end_date=end_str,
            scope=['financial', 'inventory', 'operational'],
            user_id='test_admin'
        )

        print(f"✅ Insights generated successfully!\n")

        # Display results
        insights = result.insights

        print(f"{'='*60}")
        print(f"ANALYSIS SUMMARY")
        print(f"{'='*60}\n")

        print(f"📊 POTENTIAL MONTHLY SAVINGS: ₹{insights.estimated_monthly_savings / 100:,.2f}")
        print(f"📅 Analysis Period: {insights.analysis_period.start} to {insights.analysis_period.end}")
        print(f"🔑 Cache Key: {insights.cache_key}")

        if result.usage:
            print(f"\n💰 TOKEN USAGE:")
            print(f"   Input Tokens: {result.usage.input_tokens:,}")
            print(f"   Output Tokens: {result.usage.output_tokens:,}")
            print(f"   Total Tokens: {result.usage.input_tokens + result.usage.output_tokens:,}")

        print(f"\n{'='*60}")
        print(f"FINANCIAL SUMMARY")
        print(f"{'='*60}")
        fs = insights.financial_summary
        print(f"Total Revenue: ₹{fs.total_revenue / 100:,.2f}")
        print(f"Revenue Loss: ₹{fs.revenue_loss / 100:,.2f}")
        print(f"Avg Order Value: ₹{fs.avg_order_value / 100:,.2f}")
        print(f"Cancelled Orders: {fs.cancelled_orders_count}")
        print(f"Discount Amount: ₹{fs.discount_amount / 100:,.2f}")

        print(f"\n{'='*60}")
        print(f"INVENTORY SUMMARY")
        print(f"{'='*60}")
        inv = insights.inventory_summary
        print(f"Total Stock Value: ₹{inv.total_stock_value / 100:,.2f}")
        print(f"Waste Value: ₹{inv.waste_value / 100:,.2f}")
        print(f"Low Stock Items: {inv.low_stock_items}")
        print(f"Near Expiry Items: {inv.near_expiry_items}")

        print(f"\n{'='*60}")
        print(f"OPERATIONAL SUMMARY")
        print(f"{'='*60}")
        ops = insights.operational_summary
        print(f"Avg Kitchen Time: {ops.avg_kitchen_time_mins:.1f} mins")
        print(f"Table Turnover Rate: {ops.table_turnover_rate:.2f}")
        print(f"Staff Efficiency Score: {ops.staff_efficiency_score:.1f}/10")
        print(f"Orders Completed: {ops.orders_completed}")

        print(f"\n{'='*60}")
        print(f"CRITICAL ISSUES ({len(insights.critical_issues)})")
        print(f"{'='*60}\n")

        if insights.critical_issues:
            for idx, issue in enumerate(insights.critical_issues, 1):
                print(f"{idx}. [{issue.priority.upper()}] {issue.title}")
                print(f"   Category: {issue.category}")
                print(f"   Root Cause: {issue.root_cause}")
                print(f"   Impact: {issue.impact}")
                print(f"   Recommendation: {issue.recommendation}")
                print(f"   Estimated Savings: ₹{issue.estimated_savings / 100:,.2f}/month")
                print()
        else:
            print("✅ No critical issues found! Operations running smoothly.\n")

        print(f"{'='*60}")
        print(f"TEST COMPLETED SUCCESSFULLY")
        print(f"{'='*60}\n")

        # Save to file for inspection
        output_file = f"/app/static/insights/test_insights_{insights.cache_key}.json"
        with open(output_file, 'w') as f:
            json.dump(insights.model_dump(), f, indent=2, default=str)
        print(f"📁 Full results saved to: {output_file}\n")

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_insights())
