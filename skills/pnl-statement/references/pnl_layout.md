# P&L Excel Layout

## Fixed Structure - DO NOT MODIFY

### Sheet Name
**"P&L"** (single sheet)

### Layout Overview

The template has a fixed structure. The script only fills values in column B; structure remains unchanged.

### Row-by-Row Breakdown

| Row | Column A (Label) | Column B (Value) | Notes |
|-----|------------------|------------------|-------|
| 1 | Operational P&L | (title) | Header |
| 2 | Period: | {start_date} to {end_date} | Dynamic |
| 3 | (blank) | | Spacing |
| 4 | **Revenue** | | Section header |
| 5 | Gross Revenue | =SUM(Total_INR) | Calculated |
| 6 | Less: Promo Discount | =SUM(Promo_Discount_INR) | Calculated |
| 7 | Less: Item Discount | =SUM(Item_Discount_INR) | Calculated |
| 8 | **Net Revenue** | =B5 - B6 - B7 | Calculated |
| 9 | (blank) | | Spacing |
| 10 | **Costs** | | Section header |
| 11 | Tax (GST) | =SUM(Tax_GST_INR) | Calculated |
| 12 | Delivery Fees | =SUM(Delivery_Fee_INR) | Calculated |
| 13 | Packaging | =SUM(Packaging_Charge_INR) | Calculated |
| 14 | COGS (estimate) | =B8 × 0.35 | Estimated |
| 15 | **Total Costs** | =B11 + B12 + B13 + B14 | Calculated |
| 16 | (blank) | | Spacing |
| 17 | **Net Profit** | =B8 - B15 | Calculated |
| 18 | (blank) | | Spacing |
| 19 | **By Channel** | | Section header |
| 20+ | {Channel Name} | =SUM(Total_INR) by channel | One row per channel |

### Channel Breakdown

Starting at row 20, each sales channel gets one row:
- Zomato
- Swiggy
- WalkIn

Format: Channel name in column A, revenue in column B

### Formatting

**Column A (Labels):**
- Width: 30 characters
- Alignment: Left
- Bold for section headers and totals

**Column B (Values):**
- Width: 20 characters
- Alignment: Right
- Number format: ₹#,##0.00 (Indian Rupee currency)
- All values are numeric (decimals)

**Section Headers:**
- Font: Bold, 11pt
- Background: Light blue (#D9E1F2)

**Totals (Net Revenue, Total Costs):**
- Font: Bold
- Background: Light blue (#D9E1F2)

**Net Profit:**
- Font: Bold
- Background: Green (#70AD47)

### Template Location

`/skills/pnl-statement/assets/pnl_template.xlsx`

### Important Notes

1. **Fixed layout**: Row positions never change
2. **Script fills values only**: Template structure is preserved
3. **Currency format**: All monetary values use Indian Rupee format
4. **COGS is estimated**: 35% of net revenue until actual data available
5. **No formulas in output**: Script writes computed values, not Excel formulas

### Future Enhancements

- Add monthly breakdown section (columns for each month)
- Include year-over-year comparison
- Add profit margin percentages
- Chart/graph integration
