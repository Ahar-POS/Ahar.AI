
---
name: pnl-statement
description: Generate operational P&L (Profit & Loss) Excel reports from order data. Use when user requests P&L, profit and loss statement, financial report, or mentions date ranges like "last week", "this month", or specific dates.
---

# P&L Statement Generator

## When to use

User requests P&L report with date range:
- "Generate P&L for last week"
- "P&L for January 2024"
- "Show me profit and loss from 2024-01-01 to 2024-12-31"

## Workflow

Copy this checklist and check off as you complete:

```
P&L Generation Progress:
- [ ] Step 1: Validate dates
- [ ] Step 2: Generate report
- [ ] Step 3: Verify output
```

**Step 1: Validate dates**

Run validation script:
```bash
python scripts/validate_dates.py <start_date> <end_date>
```

If output is "ERROR:", stop and report the issue to the user.
If output is "VALID", proceed to Step 2.

**Step 2: Generate report**

Execute the generation script:
```bash
python scripts/generate_pnl.py <start_date> <end_date> /data/orders.csv
```

Script will:
- Load filtered order data from CSV
- Compute revenue, costs, and profit metrics
- Fill the template with calculated values
- Save output to `/output/pnl_report_{start}_{end}.xlsx`

**Step 3: Verify output**

Check script output for "SUCCESS:" message.
If successful, inform user: "P&L report generated for {start_date} to {end_date}"

## Report structure

- **Single sheet named "P&L"**
- Fixed layout with revenue, costs, and profit sections
- Channel breakdown (Zomato, Swiggy, WalkIn)

For detailed layout, see [references/pnl_layout.md](references/pnl_layout.md)

## Data sources

**Primary data:** `/data/orders.csv`
- Pre-filtered by date range (backend handles filtering)
- Contains order details: Total_INR, Tax_GST_INR, discounts, fees

**Column naming:** PascalCase_With_Underscores

For complete schema, see [references/data_sources.md](references/data_sources.md)

## Important notes

- Dates must be in YYYY-MM-DD format
- COGS (Cost of Goods Sold) is currently estimated at 35% of net revenue
- Template file location: `/skills/pnl-statement/assets/pnl_template.xlsx`
- Do NOT modify the template structure, only fill values
