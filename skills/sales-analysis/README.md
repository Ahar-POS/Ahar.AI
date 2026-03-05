# Sales Analysis Skill

Deep sales and profit analysis at granular level (item, ingredient, category).

## Overview

This skill enables the chatbot to analyze restaurant performance at a granular level using native tool calling. Unlike the P&L statement skill which generates comprehensive monthly reports, sales-analysis focuses on answering specific questions about:

- **Sales performance** (volume, revenue, top sellers)
- **Profitability** (margins, profit drivers)
- **Item performance** (top/bottom performers)
- **Ingredient costs** and trends
- **Time-based comparisons** (including month-to-month)
- **Loss identification**

## Features

### 0. Sales Queries (NEW)
Query sales performance with volume and revenue focus:
- **Volume**: Quantity sold (best for "which sold most" queries)
- **Revenue**: Total sales value (best for "highest sales" queries)
- **Month-based comparisons**: "Nov vs Dec sales"

**Example queries:**
- "Which item sold the most in December?"
- "Show me top 10 selling items last week"
- "Compare November and December sales"
- "How was my sales in Nov vs Dec?"
- "What's my total revenue for November?"

### 1. Item Performance Analysis
Query top or bottom performers by any metric:
- Revenue (total sales value)
- Profit (revenue - COGS)
- Profit margin %
- Sales volume (quantity sold)
- Average order value

**Example queries:**
- "Show me top 10 items by profit last month"
- "What are my worst performing items by margin?"
- "Top 5 beverages by revenue last 2 weeks"
- "Which items have the best profit margins?"

### 2. Item Deep Dive
Detailed analysis of specific menu items:
- Revenue, profit, margin breakdown
- COGS breakdown by ingredient
- Packaging costs
- Performance trends
- Comparison to previous periods

**Example queries:**
- "How is Chicken Tikka Sandwich performing?"
- "Show me detailed analysis of Paneer Wrap"
- "Why is my burger profit declining?"

### 3. Ingredient Cost Analysis
Track ingredient-level costs and trends:
- Total spend by ingredient
- Unit cost tracking
- Cost changes over time
- Dishes using each ingredient
- Volume usage

**Example queries:**
- "What ingredient cost me most last week?"
- "Show me chicken breast cost trend"
- "Which ingredients have increased in price?"

### 4. Period Comparison
Compare metrics across time periods:
- Month over month
- Week over week
- Custom period comparisons
- Trend identification

**Example queries:**
- "Compare revenue last month vs this month"
- "How has Chicken Tikka changed in last 4 months?"
- "Last 2 weeks vs previous 2 weeks performance"

### 5. Loss Identification
Identify where money is being lost:
- Low margin items
- Negative margin items
- High cost ingredients
- Waste analysis
- Pricing issues

**Example queries:**
- "Where am I losing money in sandwiches?"
- "Show me items with negative margins"
- "What's causing profit loss?"

## Architecture

### Tool-Based Approach (Option B)

The skill uses **native Claude tool calling** instead of scripts:

1. **Intent Detection**: Keyword matching in `chatbot_service.py` (`_is_profit_analysis_intent()`)
2. **Tool Selection**: Claude decides which tools to call based on user query
3. **Data Fetching**: Tools query MongoDB and calculate metrics
4. **Intelligent Presentation**: Claude formats and explains results

### Tools Available

1. **get_top_items**: Rank items by metric
2. **get_item_details**: Deep dive into specific item
3. **get_ingredient_costs**: Ingredient cost tracking
4. **compare_periods**: Time-based comparisons
5. **identify_losses**: Loss source identification

## Data Flow

```
User Query
    ↓
Intent Detection (keyword matching - 0 LLM cost)
    ↓
Claude API (with tool definitions)
    ↓
Tool Execution (MongoDB queries + calculations)
    ↓
Claude Formats Response
    ↓
User sees analysis in chat
```

## Metrics Calculated

### Item-Level Metrics
- **Revenue**: Total sales value (price × quantity)
- **Profit**: Revenue - COGS
- **Margin %**: (Profit / Revenue) × 100
- **Volume**: Quantity sold
- **AOV**: Average order value
- **COGS per serving**: Raw materials + packaging

### Ingredient-Level Metrics
- **Total Cost**: Sum of (unit_cost × quantity_used × portions_sold)
- **Unit Cost**: Cost per unit (kg, liter, etc.)
- **Cost Trend**: % change from previous period
- **Volume**: Total quantity used
- **Dishes Using**: Count of menu items using this ingredient

### COGS Calculation
```
COGS per serving = Raw Material Cost + Packaging Cost

Raw Material Cost:
  For each ingredient in recipe_bom:
    cost += ingredient.quantity × raw_material_inventory.unit_cost_inr

Packaging Cost:
  For each packaging in packaging_bom:
    cost += packaging_materials.unit_cost_inr

Total COGS = COGS per serving × quantity_sold
```

## Token Optimization

This skill is optimized for low token usage:

1. **No Data Sent Upfront**: Unlike uploading full CSV files, data is fetched only when tools are called
2. **Targeted Queries**: Tools fetch only relevant data
3. **Streaming**: Results returned incrementally
4. **Context Reuse**: Follow-up questions use conversation context
5. **Local Intent Detection**: 0 LLM cost for routing

## Integration Points

### Database Collections Used
- `orders` - Order data with line items
- `menu_items` - Menu catalog
- `recipe_bom` - Recipe bill of materials
- `raw_material_inventory` - Ingredient costs
- `packaging_bom` - Packaging requirements
- `packaging_materials` - Packaging costs
- `stock_movement_log` - Waste tracking

### Related Skills
- **pnl-statement**: Comprehensive P&L reports (complementary)
- **Insights Service**: AI-powered insights generation (overlaps with loss identification)

### Service Files
- `chatbot_service.py`: Intent detection, routing, tool execution
- `profit_analysis_service.py`: Business logic and calculations

## Configuration

### Margin Targets
- Premium items: >25%
- Economy items: >15%
- Industry standard food cost: 28-35%

### Period Defaults
- Item details: 30 days
- Ingredient costs: 7 days
- Loss analysis: 30 days
- Top items: User-specified

## Example Interactions

### Example 1: Top Performers
```
User: "Show me top 5 items by profit last 2 weeks"

Response:
📊 Top 5 Items by Profit (Last 14 Days)

1. **Chicken Tikka Sandwich** 💚
   - Revenue: ₹45,230
   - Profit: ₹18,500
   - Margin: 40.9%
   - Volume: 285 orders

2. **Paneer Wrap**
   - Revenue: ₹38,900
   - Profit: ₹16,200
   - Margin: 41.6%
   - Volume: 312 orders

[... top 5 ...]

💡 Insight: Beverages have excellent margins (>70%). Sandwiches are strong revenue drivers.
```

### Example 2: Loss Analysis
```
User: "Where am I losing money in sandwiches?"

Response:
🔴 Loss Analysis: Sandwiches

**1. Low Margin Items (below 25% target):**
- Egg Mayo Sandwich: 18% margin (₹12 profit on ₹67 revenue)
  → Recommendation: Increase price to ₹75 for 25% margin

- Chicken Cheese Sandwich: 22% margin
  → High cheese cost driving down margin

**2. High Cost Ingredients:**
- Cheese: ₹1,240/kg (📈 ↑15% from last month)
- Chicken breast: ₹450/kg (📈 ↑8%)

**3. Waste Issues:**
- Lettuce: 8% waste rate (₹480 lost in 2 weeks)
- Tomato: 5% waste rate (₹320 lost)

💰 Total Recoverable: **₹3,200/month** with pricing + waste fixes

Would you like me to drill deeper into any specific issue?
```

### Example 3: Ingredient Costs
```
User: "Which ingredient cost me most last week?"

Response:
💸 Top Ingredients by Cost (Last 7 Days)

1. **Chicken Breast** - ₹8,450
   - Volume: 18.7 kg
   - Unit cost: ₹452/kg (📈 ↑8% vs last week)
   - Used in: 8 dishes

2. **Paneer** - ₹5,230
   - Volume: 12.3 kg
   - Unit cost: ₹425/kg (➡️ stable)
   - Used in: 6 dishes

3. **Cheese (processed)** - ₹4,890 ⚠️
   - Volume: 3.9 kg
   - Unit cost: ₹1,254/kg (📈 ↑15% vs last week)
   - Used in: 12 dishes

🎯 Action: Cheese price spike detected. Consider alternative supplier or reduce quantity per serving.
```

## Troubleshooting

### No Data Returned
- Check date range matches your order data
- Verify item name spelling (uses fuzzy matching)
- Ensure COGS data exists (recipe_bom, raw_material_inventory)

### Missing COGS
- Add recipe to `recipe_bom` collection
- Ensure all ingredients have costs in `raw_material_inventory`
- Add packaging to `packaging_bom` if needed

### Incorrect Trends
- Verify historical cost data is being tracked
- Currently trends use static costs (TODO: implement historical cost tracking)

## Future Enhancements

1. **Historical Cost Tracking**: Track ingredient cost changes over time
2. **Predictive Analysis**: Forecast profit trends
3. **Automated Alerts**: Notify when margins drop below thresholds
4. **Category Benchmarks**: Compare performance across categories
5. **Supplier Analysis**: Track cost by supplier
6. **Recipe Optimization**: Suggest ingredient substitutions for better margins
7. **Seasonal Analysis**: Identify seasonal performance patterns

## Developer Notes

### Adding New Tools
1. Define tool in `PROFIT_ANALYSIS_TOOLS` in `chatbot_service.py`
2. Implement method in `ProfitAnalysisService`
3. Add execution case in `_execute_profit_analysis_tool()`
4. Update SKILL.md documentation

### Extending Metrics
Add new metrics to `get_top_items()` enum and calculation logic in `profit_analysis_service.py`.

### Testing
Use chatbot queries to test:
```
"Top 10 items by revenue last month"
"Show me Chicken Tikka details"
"Where am I losing money?"
```

## Support

For issues or feature requests, refer to project documentation or raise an issue in the repository.
