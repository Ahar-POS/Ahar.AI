# Chatbot Analytics Assistant — Cost-Optimized Design (v3.0)

**Version:** 3.0  
**Date:** 2026-02-18  
**Status:** Design Proposal — Economically Viable for ₹20,000/Year Product

---

## Table of Contents

1. [Reality Check: Current Design vs Target Economics](#reality-check-current-design-vs-target-economics)
2. [Cost-Effective Architecture Principles](#cost-effective-architecture-principles)
3. [New Architecture: Hybrid Local + Minimal AI](#new-architecture-hybrid-local--minimal-ai)
4. [Strategy 1: Replace xlsx Skill with Python Libraries](#strategy-1-replace-xlsx-skill-with-python-libraries)
5. [Strategy 2: Use Claude Only for NLU](#strategy-2-use-claude-only-for-nlu-intent--parameter-extraction)
6. [Strategy 3: Pre-Compute Everything Possible](#strategy-3-pre-compute-everything-possible)
7. [Revised Cost Model](#revised-cost-model)
8. [Implementation Recommendations](#implementation-recommendations)
9. [Architecture Changes Summary](#architecture-changes-summary)

---

## Reality Check: Current Design vs Target Economics

| Metric | Value |
|--------|--------|
| **Current design cost** | ~$190/month = $2,280/year |
| **Target product price** | ₹20,000/year ≈ $240/year |
| **Problem** | AI costs exceed the entire product price by **10x** |

Skills-heavy designs (Sonnet + xlsx skill + Files API) are not economically viable at this price point.

---

## Cost-Effective Architecture Principles

**Core principle:** Skills are expensive luxury items we cannot afford.

Design constraints:

- **No xlsx skill** (costs $0.30–0.50 per use)
- **No Sonnet** (≈3× more expensive than Haiku)
- **Minimal Claude calls** (cache aggressively, pre-compute locally)
- **Maximum code, minimum AI**

---

## New Architecture: Hybrid Local + Minimal AI

### Cost Breakdown

| Approach | Monthly | Annual |
|----------|---------|--------|
| **OLD (Skills-heavy)** | $190/month | $2,280/year |
| **NEW (Code-heavy)** | $5/month | $60/year ✅ |
| **Savings** | $185/month | $2,220/year (**97% less**) |

---

## Strategy 1: Replace xlsx Skill with Python Libraries

Do not use Claude to generate Excel files. Use Python directly.

### ReportGenerator (Pure Python)

**Location:** `backend/app/services/report_generator.py`

```python
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, PatternFill
from pathlib import Path
import time

class ReportGenerator:
    """Generate reports using pure Python (no AI, zero cost)."""

    def __init__(self, data_loader):
        self.data_loader = data_loader

    def generate_pnl_excel(self, user_id: str, filters: dict = None) -> Path:
        """
        Generate P&L Excel file using openpyxl (no Claude, no cost).

        Returns: Path to generated file in temp directory.
        """
        # Load data
        orders = pd.read_excel("lexis_test_data/orders.xlsx")

        # Apply filters if provided
        if filters:
            if 'start_date' in filters:
                orders = orders[orders['Order_Date'] >= filters['start_date']]
            if 'end_date' in filters:
                orders = orders[orders['Order_Date'] <= filters['end_date']]

        # Compute P&L metrics (hardcoded business logic)
        monthly = orders.groupby(
            pd.to_datetime(orders['Order_Date']).dt.to_period('M')
        ).agg({
            'Total_INR': 'sum',
            'Subtotal_INR': 'sum',
            'Tax_GST_INR': 'sum',
            'Promo_Discount_INR': 'sum',
            'Delivery_Fee_INR': 'sum',
            'Packaging_Charge_INR': 'sum',
        }).round(2)

        # Calculate profit (hardcoded formula)
        monthly['Gross_Revenue'] = monthly['Total_INR']
        monthly['COGS'] = monthly['Subtotal_INR'] * 0.35  # Assume 35% COGS
        monthly['Operating_Expenses'] = (
            monthly['Delivery_Fee_INR'] +
            monthly['Packaging_Charge_INR']
        )
        monthly['Net_Profit'] = (
            monthly['Gross_Revenue'] -
            monthly['COGS'] -
            monthly['Operating_Expenses'] -
            monthly['Promo_Discount_INR']
        )

        # Create Excel file
        wb = Workbook()
        ws = wb.active
        ws.title = "P&L Report"

        # Header styling
        header_fill = PatternFill(start_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)

        # Write headers
        headers = list(monthly.columns)
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font

        # Write data
        for row_idx, (period, row) in enumerate(monthly.iterrows(), start=2):
            ws.cell(row=row_idx, column=1, value=str(period))
            for col_idx, value in enumerate(row, start=2):
                ws.cell(row=row_idx, column=col_idx, value=value)

        # Add chart
        chart = BarChart()
        chart.title = "Monthly Net Profit"
        data = Reference(ws, min_col=len(headers), min_row=1,
                         max_row=len(monthly)+1)
        categories = Reference(ws, min_col=1, min_row=2,
                               max_row=len(monthly)+1)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(categories)
        ws.add_chart(chart, f"A{len(monthly)+3}")

        # Save to temp file
        output_path = Path(f"/tmp/pnl_report_{user_id}_{int(time.time())}.xlsx")
        wb.save(output_path)

        return output_path
```

**Cost:** $0.00 per report (pure Python, no AI)  
**Time:** ~100 ms (vs 10–30 s with Claude)

---

## Strategy 2: Use Claude Only for NLU (Intent + Parameter Extraction)

Claude is used only to understand what the user wants; execution is done in code.

### Chatbot Service Flow

**Location:** `backend/app/services/chatbot_service.py`

- **Single Haiku call** to understand intent and extract parameters (e.g. dates, material name, days_ahead).
- Return a **JSON command** from Claude; backend executes the command with **zero-cost code**.

### Available Commands (JSON from Claude)

| Action | Example Parameters | Execution |
|--------|--------------------|-----------|
| `pnl_report` | `filters: { start_date, end_date }` | `ReportGenerator.generate_pnl_excel()` |
| `inventory_query` | `material: string` | Pandas lookup on `raw_material_inventory.xlsx` |
| `demand_forecast` | `days_ahead: int` | Pre-computed cache or simple moving average |
| `chat` | `response: string` | Store in history, return reply |

### Example System Prompt (Haiku)

```
You are a restaurant analytics assistant.

Your job is to understand what the user wants and return a JSON command.

Available commands:
- {"action": "pnl_report", "filters": {"start_date": "2024-01", "end_date": "2024-12"}}
- {"action": "inventory_query", "material": "chicken"}
- {"action": "demand_forecast", "days_ahead": 7}
- {"action": "chat", "response": "your conversational reply"}

Examples:
User: "Show me P&L for last quarter"
You: {"action": "pnl_report", "filters": {"start_date": "2024-10", "end_date": "2024-12"}}

User: "How much chicken do we have?"
You: {"action": "inventory_query", "material": "chicken"}

User: "What's the forecast for next week?"
You: {"action": "demand_forecast", "days_ahead": 7}

User: "How do I hire staff?"
You: {"action": "chat", "response": "Here's how to hire staff..."}

ALWAYS respond with valid JSON only.
```

### Execution Stubs (No AI Cost)

- **`_execute_pnl_report(user_id, filters)`** — Uses `ReportGenerator`, writes to `static/reports/`, returns `ChatResponse` with `download_url`.
- **`_execute_inventory_query(material)`** — Pandas read of `raw_material_inventory.xlsx`, filter by material or return summary; format as markdown reply.
- **`_execute_demand_forecast(days_ahead)`** — Read from pre-computed cache if available; otherwise simple 7-day moving average + day-of-week pattern (pandas only).
- **Default (`chat`)** — Append to history, return `command["response"]`.

**Cost per query:** ~$0.001 (Haiku NLU only); execution is $0.00. **~200× cheaper than Skills approach.**

---

## Strategy 3: Pre-Compute Everything Possible

A **nightly job** (e.g. 2 AM) pre-computes expensive analytics so query-time work is a cache lookup.

### Nightly Job

**Location:** `backend/app/tasks/nightly_analytics.py`

- Load once: `orders.xlsx`, `raw_material_inventory.xlsx`, `daily_aggregates.xlsx`.
- Compute and cache:
  - `daily_summary`, `weekly_summary`, `monthly_summary`
  - `inventory_status`
  - `demand_forecast_7d`, `demand_forecast_30d`
  - `top_selling_items`, `channel_performance`
- Write to `cache/analytics_cache.json` (or Redis if available).

At query time, read from cache (instant, zero cost). Use a scheduler (e.g. APScheduler) with a cron trigger.

---

## Revised Cost Model

**Assumption:** 100 queries/day mix.

| Query Type      | Approach                    | Cost per Query | Daily Count | Daily Cost |
|-----------------|-----------------------------|----------------|-------------|------------|
| P&L Report      | Python (openpyxl) + Haiku NLU | $0.001         | 10          | $0.01      |
| Inventory       | Pandas lookup + Haiku NLU   | $0.001         | 35          | $0.035     |
| Demand Forecast | Pre-computed cache + Haiku NLU | $0.001      | 35          | $0.035     |
| General Chat    | Haiku only (with history)   | $0.005         | 20          | $0.10      |
| **Total**       |                             |                | 100         | **$0.18/day** |

- **Monthly:** ~$5.40  
- **Annual:** ~$64.80  

**Margin on ₹20,000 product:**

- Product price: ~$240/year  
- AI cost: ~$65/year  
- **AI cost as % of revenue: ~27%** ✅ (sustainable)

---

## Implementation Recommendations

### What to Build

1. **Replace xlsx skill entirely**
   - Use **openpyxl** for Excel generation.
   - Use **pandas** for data analysis.
   - Use **matplotlib/seaborn** for charts (e.g. embedded in Excel if needed).

2. **Use Claude only for NLU**
   - Intent classification.
   - Parameter extraction (dates, filters, materials, days_ahead).
   - General chat responses.
   - No report generation, no file creation, no heavy reasoning in Claude.

3. **Pre-compute heavy analytics**
   - Nightly job for forecasts, trends, summaries.
   - Store in JSON cache or Redis.
   - Instant retrieval at query time.

4. **Simplify file serving**
   - Generate files under `static/reports/`.
   - Serve via FastAPI `StaticFiles` (no Claude Files API).
   - Auto-cleanup files older than 24 hours.

### Dependencies to Add

```text
# requirements.txt additions
pandas>=2.0.0
openpyxl>=3.1.0
matplotlib>=3.7.0
apscheduler>=3.10.0   # For nightly jobs
```

---

## Architecture Changes Summary

### Remove

- Skills API integration  
- Files API integration  
- Sonnet model usage  
- Multi-turn skill continuations  
- `pause_turn` handling  

### Keep

- Haiku for NLU  
- Conversation history  
- Admin authorization  
- DataLoader (can be enhanced with caching)  

### Add

- **ReportGenerator** class (pure Python, openpyxl/pandas).  
- **Nightly analytics pre-computation** (APScheduler + cache).  
- **JSON command pattern** (Claude returns one JSON blob; backend executes).  
- **Local file serving** (`static/reports/` + cleanup).  

---

## Summary

This v3.0 design is **economically viable** for a ₹20,000/year product by treating **Skills as a luxury** and replacing them with **deterministic Python**: openpyxl for Excel, pandas for analytics, and Haiku only for understanding user intent and extracting parameters. Heavy analytics are pre-computed; file handling is local and simple.
