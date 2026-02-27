---
name: profit-analysis
description: Deep profit & loss analysis at granular level (item, ingredient, dish). Analyze performance, margins, costs, losses, and trends across time periods. Use when user asks about top performers, profit drivers, cost analysis, margin issues, or comparative performance.
---

# Profit Analysis Skill

## When to use

User asks about performance, profitability, or cost analysis:
- "Which are my top performing items for last 2 weeks?"
- "How has Chicken Tikka Sandwich performance changed in last 4 months?"
- "Where am I losing money most in my sandwiches?"
- "Which ingredient has cost me the most last week?"
- "Show me items with negative margins"
- "Why is my burger profit declining?"
- "Compare revenue last month vs this month"
- "What's my best margin item?"

## How it works

**Tool-based approach** - Claude has access to multiple analysis tools:

1. **get_top_items** - Get top/bottom performers by any metric
2. **get_item_details** - Deep dive into specific item (revenue, profit, margin, COGS, trends)
3. **get_ingredient_costs** - Ingredient-level cost breakdown and trends
4. **compare_periods** - Compare metrics across time periods
5. **identify_losses** - Find loss sources (low margins, waste, pricing issues)

Claude intelligently:
- Calls appropriate tools based on user query
- Decides which metrics to show (revenue, profit, margin, volume, trends)
- Chooses presentation format (tables, lists, summaries)
- Provides overview first, goes deeper on follow-up questions

## Metrics Available

**Item-level:**
- Total revenue (sales value)
- Total profit (revenue - COGS)
- Profit margin % ((profit / revenue) × 100)
- Sales volume (quantity sold)
- Average order value
- COGS per serving
- Contribution margin
- Trend (growing/declining/stable with %)

**Ingredient-level:**
- Total cost (across all dishes using it)
- Cost per unit
- Cost trend over time
- Usage volume
- Dishes using this ingredient
- Waste amount (if tracked)

**Category-level:**
- Aggregated metrics for groups (sandwiches, beverages, etc.)
- Category contribution to total profit
- Best/worst items in category

## Data Sources

### Collections Used

1. **orders** - Order data with line items
   - order_date, total_amount, status, items[]

2. **order_line_items** (embedded in orders)
   - menu_item_id, quantity, price_snapshot, name_snapshot

3. **menu_items** - Menu catalog
   - name, category, price, tags

4. **recipe_bom** - Recipe Bill of Materials
   - menu_item_id, ingredients[] (material_id, quantity)

5. **raw_material_inventory** - Ingredient costs
   - material_id, material_name, unit_cost_inr, category

6. **packaging_bom** - Packaging per item
   - menu_item_id, packaging items

7. **packaging_materials** - Packaging costs
   - packaging_id, unit_cost_inr

8. **stock_movement_log** - Waste tracking
   - material_id, quantity, movement_type (WASTE, STAFF_MEAL, etc.)

## Cost Calculation

**Item COGS** = Raw Material Cost + Packaging Cost

**Raw Material Cost** (per serving):
```
For each ingredient in recipe_bom:
  cost += ingredient.quantity × raw_material_inventory.unit_cost_inr
```

**Packaging Cost** (per serving):
```
For each packaging in packaging_bom:
  cost += packaging_materials.unit_cost_inr
```

**Total COGS** (for period) = COGS per serving × quantity sold

**Profit** = Revenue - Total COGS

**Margin %** = (Profit / Revenue) × 100

## Intelligent Presentation

Based on user query, Claude decides:

**"Top items last 2 weeks"**
→ Table format with revenue, profit, margin, volume

**"Why is profit down on Chicken Tikka?"**
→ Item deep dive: COGS breakdown by ingredient, margin trend, pricing analysis

**"Where am I losing money in sandwiches?"**
→ Overview: low margin items, high cost ingredients, waste
→ On follow-up: Drill into specific problem

**"Compare last month vs this month"**
→ Period comparison table with % changes and trends

## Time Period Parsing

Supports natural language:
- "last week" → 7 days ago to yesterday
- "last 2 weeks" → 14 days ago to yesterday
- "last month" → Previous calendar month
- "this month" → Current month to today
- "last quarter" → Previous 3 months
- "January" → 2026-01-01 to 2026-01-31
- "last 4 months" → 4 months ago to yesterday
- Custom: "2026-01-01 to 2026-01-31"

## Loss Analysis Depth

**First query: Overview**
```
Problems detected in Sandwiches:
1. Chicken Tikka Sandwich: -5% margin (below target 25%)
   → High chicken breast cost (₹45/serving)
2. Veg Club Sandwich: Declining sales (-30% vs last month)
   → Pricing vs competitors?
3. Paneer Sandwich: High waste (12% of ingredient)
   → Portion control issue
```

**Follow-up: Deeper dive**
```
User: "Tell me more about Chicken Tikka margin issue"

→ Deep analysis:
- Chicken breast cost: ₹45/serving (was ₹38 last month)
- Total COGS: ₹52/serving
- Selling price: ₹65
- Profit: ₹13 (20% margin, target: 25%)
- Recommendations:
  1. Increase price to ₹72 for 25% margin
  2. Reduce chicken quantity by 15g (saves ₹5)
  3. Negotiate better chicken prices
```

## Ingredient Cost Tracking

**Weekly ingredient cost changes** are automatically calculated:

Tool: `get_ingredient_costs` can show:
- Current unit cost
- Cost 1 week ago
- Cost 1 month ago
- % change
- Total spend on ingredient
- Trend (rising/falling/stable)

This data is used in P&L calculations to show true cost changes over time.

## Important Notes

- All monetary values in paise (convert to rupees for display: `/100`)
- Only include completed orders (status != 'cancelled')
- COGS includes both raw materials AND packaging
- Margin targets: Premium items >25%, Economy items >15%
- Compare same periods (7d vs 7d, not 7d vs 30d)
- Waste tracked via stock_movement_log (movement_type = 'WASTE')

## Token Optimization

This skill uses **native tool calling** (not Skills API):
- Claude decides which tools to call based on query
- No data sent until tools are invoked
- Only relevant data fetched from DB
- Results presented directly in chat (no file generation)
- Follow-up questions use conversation context (minimal tokens)

## Example Interactions

### Example 1: Top Performers
```
User: "Show me top 5 items by profit last 2 weeks"

Claude calls: get_top_items(metric="profit", period="14d", limit=5, order="desc")

Response (table format):
┌─────────────────────────────┬──────────┬─────────┬────────┬────────┐
│ Item                        │ Revenue  │ Profit  │ Margin │ Volume │
├─────────────────────────────┼──────────┼─────────┼────────┼────────┤
│ Chicken Tikka Sandwich      │ ₹45,230  │ ₹18,500 │  40.9% │    285 │
│ Paneer Wrap                 │ ₹38,900  │ ₹16,200 │  41.6% │    312 │
│ Veg Club Sandwich           │ ₹32,450  │ ₹14,800 │  45.6% │    268 │
│ Masala Chai                 │ ₹28,600  │ ₹21,450 │  75.0% │  1,145 │
│ Cold Coffee                 │ ₹25,800  │ ₹18,900 │  73.3% │    892 │
└─────────────────────────────┴──────────┴─────────┴────────┴────────┘

Insight: Beverages have excellent margins (>70%). Sandwiches strong revenue drivers.
```

### Example 2: Loss Identification
```
User: "Where am I losing money in sandwiches?"

Claude calls: identify_losses(category="sandwich")

Response (overview):
🔴 Loss Analysis: Sandwiches

1. Low Margin Items (below 25% target):
   - Egg Mayo Sandwich: 18% margin (₹12 profit on ₹67 revenue)
   - Chicken Cheese Sandwich: 22% margin (high cheese cost)

2. High Cost Ingredients:
   - Cheese: ₹1,240/kg (↑15% from last month)
   - Chicken breast: ₹450/kg (↑8% from last month)

3. Waste Issues:
   - Lettuce: 8% waste rate (₹480 lost last 2 weeks)
   - Tomato: 5% waste rate (₹320 lost)

Total recoverable: ₹3,200/month with pricing + waste fixes
```

### Example 3: Ingredient Deep Dive
```
User: "What ingredient cost me most last week?"

Claude calls: get_ingredient_costs(period="7d", sort_by="total_cost", limit=10)

Response:
Top 10 Ingredients by Cost (Last 7 Days):

1. Chicken Breast
   - Total spent: ₹8,450
   - Volume: 18.7 kg
   - Unit cost: ₹452/kg (↑8% vs last week)
   - Used in: 8 dishes

2. Paneer
   - Total spent: ₹5,230
   - Volume: 12.3 kg
   - Unit cost: ₹425/kg (stable)
   - Used in: 6 dishes

3. Cheese (processed)
   - Total spent: ₹4,890
   - Volume: 3.9 kg
   - Unit cost: ₹1,254/kg (↑15% vs last week) ⚠️
   - Used in: 12 dishes

Action: Cheese price spike - consider alternative supplier or reduce quantity per serving.
```

### Example 4: Trend Comparison
```
User: "How has Chicken Tikka Sandwich changed in last 4 months?"

Claude calls:
- get_item_details(item_name="Chicken Tikka Sandwich", period="120d")
- compare_periods(item_name="Chicken Tikka Sandwich", period1="30d", period2="90d-120d")

Response:
Chicken Tikka Sandwich Performance Trend:

Last Month vs 3 Months Ago:
┌──────────────┬────────────┬───────────────┬─────────┐
│ Metric       │ Last 30d   │ 3 Months Ago  │ Change  │
├──────────────┼────────────┼───────────────┼─────────┤
│ Revenue      │ ₹22,450    │ ₹28,600       │  -21.5% │
│ Volume       │    142     │     186       │  -23.7% │
│ Profit       │ ₹9,200     │ ₹13,850       │  -33.6% │
│ Margin       │   41.0%    │    48.4%      │   -7.4% │
│ COGS/serving │    ₹52     │     ₹45       │  +15.6% │
└──────────────┴────────────┴───────────────┴─────────┘

📉 Trend: DECLINING

Root Causes:
1. Sales volume down 24% - demand issue or competition?
2. COGS increased 16% - ingredient cost inflation
3. Margin compressed from 48% to 41%

Recommendations:
1. Price increase from ₹65 to ₹72 (+10%)
2. Investigate volume decline (promotion ended?)
3. Review chicken breast supplier pricing
```

## Integration with P&L

Ingredient cost data from this skill feeds into:
- P&L Statement generation (COGS section)
- Cost variance analysis
- Budget vs actual tracking

When user asks "generate P&L", it uses latest ingredient costs from raw_material_inventory which are tracked weekly via this skill.

## Error Handling

**No data for period:**
```
"No orders found for [period]. Please verify date range or try a different period."
```

**Item not found:**
```
"Item '[name]' not found. Did you mean: [suggestions]?"
```

**Missing COGS data:**
```
"COGS data unavailable for [item]. Recipe BOM or ingredient costs missing in database."
```
