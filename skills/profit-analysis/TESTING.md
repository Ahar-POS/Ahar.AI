# Testing Profit Analysis Skill

## Issue Fixed

**Problem:** Query "Which are my top items last 2 weeks?" was being routed to inventory instead of profit analysis.

**Root Cause:**
1. Inventory intent was checked BEFORE profit analysis intent
2. The word "item" matched inventory keywords first

**Solution Applied:**
1. ✅ Moved profit analysis intent check BEFORE inventory check (more specific routing)
2. ✅ Strengthened profit analysis keyword matching with tiered detection:
   - **Strong keywords**: "top items", "top performing", "profit", "margin", "losing money", etc.
   - **Context-aware**: Weak keywords + time indicators (e.g., "revenue" + "last 2 weeks")
   - **Pattern matching**: "how has X changed", dish names + analysis words

## Test Queries

### ✅ Should Route to Profit Analysis

**Performance Queries:**
```
"Which are my top items last 2 weeks?"
"Show me top 10 items by profit last month"
"What are my best selling sandwiches?"
"Top 5 beverages by revenue this week"
"Worst performing items last quarter"
```

**Deep Dive:**
```
"How is Chicken Tikka Sandwich performing?"
"Show me detailed analysis for Paneer Wrap"
"Analyze burger performance last month"
"Why is my profit declining on wraps?"
```

**Ingredient Costs:**
```
"What ingredient cost me most last week?"
"Show me chicken breast cost trend"
"Which ingredients increased in price?"
"Ingredient spend analysis for last month"
```

**Comparisons:**
```
"Compare revenue last month vs this month"
"How has Chicken Tikka changed in last 4 months?"
"Last 2 weeks vs previous 2 weeks"
```

**Loss Analysis:**
```
"Where am I losing money in sandwiches?"
"Show me items with negative margins"
"What's causing my profit loss?"
"Items with low margins"
```

### ✅ Should Route to Inventory

**Stock Queries:**
```
"Show me current stock of chicken breast"
"What items are low on stock?"
"Do we have enough flour?"
"Update stock for paneer to 50 kg"
```

**Inventory Details:**
```
"Show me all dairy items"
"What's the cost of chicken breast?"
"Which items need restocking?"
"Search for bread in inventory"
```

### ✅ Should Route to P&L Statement

**Report Generation:**
```
"Generate P&L for January 2026"
"Show me profit and loss statement for last month"
"P&L report for Q1 2026"
"Financial statement for last quarter"
```

## How to Test

### 1. Start the Backend
```bash
cd backend
docker compose up -d
# OR
uvicorn app.main:app --reload --port 8000
```

### 2. Open Chatbot UI
Navigate to: `http://localhost:3000/chatbot` (or wherever your frontend is running)

### 3. Try Test Queries
Paste the queries above one by one and verify:
- Profit analysis queries call the profit analysis tools
- Inventory queries work for stock management
- P&L queries generate reports

### 4. Expected Response Format

**For "Which are my top items last 2 weeks?"**

Should see:
```
📊 Top Items by Revenue (Last 14 Days)

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

[...more items...]

💡 Insight: [Intelligent analysis from Claude]
```

**Should NOT see:**
```
"I don't have access to a tool that tracks sales..."
```

## Debugging

If profit analysis still doesn't work:

### Check 1: Verify Service is Running
```bash
# Check if backend is running
curl http://localhost:8000/health

# Should return: {"success": true, "status": "healthy"}
```

### Check 2: Check Logs
```bash
# View backend logs
docker compose logs -f backend
# OR
tail -f backend/logs/app.log
```

Look for:
- "Profit analysis intent detected" (confirms routing)
- Tool execution logs
- Any error messages

### Check 3: Test Intent Detection Directly
You can test intent detection in Python:
```python
from app.services.chatbot_service import ChatbotService

service = ChatbotService()
message = "Which are my top items last 2 weeks?"

print(f"Profit analysis: {service._is_profit_analysis_intent(message)}")  # Should be True
print(f"Inventory: {service._is_inventory_intent(message)}")  # Should be False
print(f"P&L: {service._is_pnl_intent(message)}")  # Should be False
```

### Check 4: Database Has Data
Ensure you have order data in MongoDB:
```bash
# Connect to MongoDB
docker exec -it mongodb mongosh

# Check orders
use ahar_pos
db.orders.countDocuments()  // Should be > 0

# Check recent orders
db.orders.find().limit(5).pretty()
```

If no orders exist, the tools will return empty results but should still work (just with "No data found" message).

## Common Issues

### Issue 1: "API key not configured"
**Solution:** Add `CLAUDE_API_KEY` to `backend/.env`

### Issue 2: "No orders found"
**Solution:** Ensure you have order data in the database for the requested time period

### Issue 3: "COGS data unavailable"
**Solution:** Ensure you have:
- Recipe BOM data (`recipe_bom` collection)
- Raw material inventory with costs (`raw_material_inventory` collection)
- Packaging data (optional but recommended)

### Issue 4: Still routing to inventory
**Solution:**
1. Restart backend to reload code changes
2. Clear browser cache if using frontend
3. Check the exact query wording matches test queries above

## Success Criteria

✅ Query "Which are my top items last 2 weeks?" should:
1. Be detected as profit analysis intent
2. Call `get_top_items` tool with period_days=14
3. Return formatted table with top items
4. Show revenue, profit, margin, volume for each item
5. Include intelligent insights from Claude

✅ No errors in backend logs
✅ Response time < 10 seconds (depending on data size)
✅ Token usage tracked correctly

## Next Steps After Testing

Once basic queries work:
1. Test edge cases (empty results, invalid item names)
2. Test follow-up questions (multi-turn conversation)
3. Test all 5 tools (top_items, item_details, ingredient_costs, compare_periods, identify_losses)
4. Add more sophisticated queries
5. Integrate with frontend dashboards (optional)

## Need Help?

If issues persist:
1. Check backend logs for detailed error messages
2. Verify MongoDB connection and data
3. Test with simpler queries first ("top items last week")
4. Ensure all dependencies are installed (`pip install -r requirements.txt`)
