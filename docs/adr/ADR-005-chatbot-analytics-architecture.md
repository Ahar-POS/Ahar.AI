# ADR-005: Chatbot & Analytics Assistant Architecture

**Date**: 2026-04-14
**Status**: Accepted (P&L + Inventory + Profit Analysis implemented; cost optimisation partially in flight)
**Decider**: Pandiarajan
**Context**: The AI-powered conversational assistant that lets restaurant staff query P&L reports, inventory status, and profit analytics in natural language via the Chatbot screen

---

## Problem

Restaurant owners and managers need to answer operational questions — "What is my food cost % this month?", "Which items are low on stock?", "Which dishes are hurting my margin?" — without navigating multiple dashboards or running manual spreadsheet analysis. The goal is a single conversational interface that:

- Generates a full P&L statement for any date range on demand
- Lets staff query and update inventory in plain language
- Surfaces profit analytics (top items, loss items, period comparisons)
- Runs affordably inside the ₹20,000/year product price

---

## System Architecture

### High-Level Flow

```
User types message
      ↓
POST /api/v1/chatbot/message   (auth: admin only)
      ↓
ChatbotService.process_message()
      ├─ Intent classification  (local keyword match — 0 LLM cost)
      ├─ Date parsing           (local regex; LLM fallback for ambiguous)
      │
      ├─ [P&L intent]
      │     ├─ subprocess → generate_pnl.py (MongoDB → text/XLSX)
      │     └─ return reply + optional download_url
      │
      ├─ [Inventory intent]
      │     └─ Claude tool-calling agentic loop
      │           tools: search_inventory, get_low_stock_items,
      │                  get_inventory_item, update_inventory_field
      │
      ├─ [Profit Analysis intent]
      │     └─ Claude tool-calling agentic loop
      │           tools: get_top_items, get_item_details,
      │                  get_ingredient_costs, compare_periods,
      │                  identify_losses
      │
      └─ [General intent]
            └─ Claude direct response (no tools)
      ↓
Response: { reply, download_url?, filename?, usage?, needs_clarification? }
      ↓
Frontend renders Markdown + optional Download button
```

---

## Decisions Made

### Decision: Local keyword intent classification — no LLM for routing

- **Chosen**: Local keyword match in `ChatbotService.process_message()` to route to one of four handlers: `pnl`, `inventory`, `profit_analysis`, `general`. Keywords like "p&l", "profit and loss", "revenue", "stock", "ingredient", "margin" determine the path before any API call.
- **Rejected**: Using Claude to classify intent — adds ~$0.001 per message for a task that keyword matching handles with zero cost.
- **Reason**: Intent boundaries are predictable in a restaurant context. Misclassifications fall through to `general`, which still gives a sensible answer. This is the highest-leverage cost reduction.

---

### Decision: P&L generation via subprocess — not in-process

- **Chosen**: `generate_pnl.py` runs as a child process via `subprocess.Popen` with a 30-second timeout. MongoDB URI, DB_NAME, and REPORTS_DIR are passed as environment variables. Output is captured from stdout (text format) or from the filesystem (XLSX format).
- **Rejected**: Running P&L logic inside FastAPI as an in-process function call.
- **Reason**: The P&L script is long-running (aggregates across 8+ MongoDB collections), imports heavy dependencies (pandas, openpyxl, xlsxwriter), and was initially designed as a standalone Anthropic Skill. Running it as a subprocess isolates crashes, enforces the timeout, and keeps the FastAPI event loop unblocked.

**Subprocess config added in commit `fbc7f86`:**
- Mongo URI and DB_NAME injected via `env=` argument (not inherited from parent process environment)
- `REPORTS_DIR` injected so the script writes Excel to the correct path

---

### Decision: P&L date parsing — local regex first, LLM fallback

- **Chosen**: A local parser handles the common cases:
  - Explicit ranges: `2025-01-01 to 2025-12-31`
  - Ordinal dates: "1st Dec 2025", "Dec 1 2025"
  - Relative: "last week", "this month", "last year"
  - Month names: "January 2024", "jan 2024"
  - Week anchors: "week of 1st Dec 2025"
  - First-N-days: "first 21 days of November 2025"
  - If no pattern matches → single Haiku call to extract start/end dates from the raw message.
- **Rejected**: Always calling LLM for date parsing — unnecessary for the majority of structured queries.
- **Reason**: Local parsing handles ~90% of cases at zero cost. The LLM fallback handles unusual phrasings without requiring exhaustive regex coverage.

**Date parsing expanded in commit `fbc7f86`.**

---

### Decision: Inventory queries use Claude native tool-calling — not Skills API

- **Chosen**: Four tools defined in `ChatbotService` as Python dicts passed to `client.messages.create(tools=[...])`. Claude decides which tool to call; the service executes it and returns results in a multi-turn agentic loop.

| Tool | What it does |
|---|---|
| `search_inventory` | Search items by name or category |
| `get_low_stock_items` | Items where current_stock ≤ reorder_level |
| `get_inventory_item` | Full detail for a single item |
| `update_inventory_field` | Update `current_stock`, `unit_cost_inr`, or `reorder_level` only |

- **Rejected**: Skills API for inventory — the data is live in MongoDB; wrapping it in a Skill container would require passing MongoDB credentials into the container at runtime, adding latency and complexity for no benefit.
- **Reason**: Native tool-calling is simpler, faster, and cheaper. The tool executor runs directly against MongoDB, so responses reflect the current inventory state.

**Implemented in commit `dd5ba36`.**

---

### Decision: Profit analysis uses a separate tool-calling handler

- **Chosen**: Five tools for financial analytics, handled in a dedicated `_handle_profit_analysis()` method with its own system prompt and tool set:

| Tool | What it does |
|---|---|
| `get_top_items` | Rank items by revenue / profit / margin / volume / AOV |
| `get_item_details` | Deep-dive revenue, cost, margin for a single item |
| `get_ingredient_costs` | Ingredient cost breakdown for an item |
| `compare_periods` | Compare two date ranges across any metric |
| `identify_losses` | Surface low-margin or high-cost items |

- **Rejected**: Adding profit-analysis tools into the inventory tool set — the system prompts and data shapes are different enough that merging would compromise both.
- **Reason**: Profit analytics requires ordering across the full menu catalogue; inventory queries focus on stock state. Separate handlers keep each context window focused.

**Implemented in commit `3377ca3`.**

---

### Decision: Anthropic Skills API used for the P&L skill package — upload-once, cache skill_id

- **Chosen**: The `pnl-statement` skill (SKILL.md + scripts + references) is uploaded via `client.beta.skills.create()` on first use and the returned `skill_id` is cached in `skills/.skill_cache.json`. On subsequent requests, the service calls `client.beta.skills.retrieve(skill_id)` to verify the skill still exists before reusing. If not found, it re-uploads.
- **Rejected**: Re-uploading the skill on every request — each upload triggers a new container build in the Skills API, adding latency and cost.
- **Reason**: The skill package rarely changes. Caching avoids repeated uploads while the verify step prevents using stale/deleted skill IDs.

**Beta header required**: `anthropic-beta: skills-2025-10-02`

**Skills API calls used:**
```
client.beta.skills.create()          # upload
client.beta.skills.retrieve(id)      # verify
client.beta.skills.delete(id)        # cleanup
client.beta.skills.versions.list(id) # inspect
```

**Implemented in `skill_uploader.py`, wired in commit `fe838ba`.**

---

### Decision: P&L script executes inside Skill container at Skills API — original design

- **Note**: The original implementation (`6d184d0`) routed P&L generation through the Anthropic Skills API: Claude would call `python scripts/generate_pnl.py` inside a managed container, and the resulting Excel file was returned via the Files API. This required uploading the skill, passing MongoDB credentials to the container environment, and downloading the output file.

- **Current state (post `fbc7f86`)**: The execution path was changed to a **direct subprocess** — `generate_pnl.py` runs locally on the backend server, not inside the Skills container. The Skills API upload/cache infrastructure (`skill_uploader.py`) is retained but the P&L generation path no longer routes through it.

- **Why changed**: Container execution added 10–30 s cold start latency and required passing MongoDB credentials out of the backend environment. Running the subprocess locally achieves the same result with lower latency and no credential leakage to an external container.

**This is a partial reversal of the Skills API approach.** The skill package and SKILL.md documentation remain as reference; the execution infrastructure is local.

---

### Decision: Conversation history stored in-memory per user, capped at 20 messages

- **Chosen**: `Dict[str, List[dict]]` keyed by user session ID. Passed as `messages=` to every Claude call so the model has multi-turn context. Capped at 20 messages to prevent token overflow.
- **Rejected**: Persisting conversation history in MongoDB — adds latency and storage cost for data with no business value after the session ends.
- **Reason**: Restaurant chatbot sessions are short and task-focused. In-memory history is sufficient; the 20-message cap prevents runaway context from degrading response quality.

---

### Decision: Excel reports saved to filesystem, served via dedicated download endpoint

- **Chosen**: `generate_pnl.py` writes to `backend/static/reports/PnL_{start}_{end}_{timestamp}.xlsx`. The API response includes `download_url: /api/v1/chatbot/download/{filename}`. The download endpoint reads from the filesystem with directory traversal protection (rejects paths containing `..` or absolute paths).
- **Rejected**: Returning the Excel file as base64 in the JSON response — large files bloat the response and break streaming.
- **Reason**: Filesystem serving is simple and fast. The timestamped filename prevents collisions. The download endpoint is the only path to the reports directory, keeping the access surface small.

---

### Decision: Auth scope — chatbot restricted to admin role only

- **Chosen**: `POST /api/v1/chatbot/message` requires an authenticated session; role check limits access to admin. No other roles can query the chatbot.
- **Rejected**: Allowing all authenticated users — inventory update capability would be a significant risk in the hands of kitchen staff.
- **Reason**: The `update_inventory_field` tool can modify stock quantities and costs. Admin-only access prevents accidental or malicious data changes by non-manager staff.

---

### Decision: Frontend renders assistant replies as GitHub-flavoured Markdown

- **Chosen**: `ChatbotPage.tsx` uses a Markdown renderer so Claude's structured responses (tables, bullet lists, headers) display correctly. Assistant bubbles are full-width; user bubbles are right-aligned.
- **Chosen**: Session-level token counter in the UI, showing `input↑ output↓` per response, sourced from the `usage` field in the API response.
- **Reason**: P&L and profit-analysis responses are inherently tabular. Plain-text rendering would make them unreadable. Token display gives the owner visibility into API cost per query.

**Implemented in commit `c54451d`.**

---

## Skills Package Contents

```
skills/
├── pnl-statement/
│   ├── SKILL.md                        # 498 lines — workflow, P&L structure, config guide, troubleshooting
│   ├── README_MONGODB.md               # MongoDB connection instructions for container
│   ├── scripts/
│   │   ├── generate_pnl.py             # 1091 lines — full P&L calculator (stdout or XLSX)
│   │   ├── validate_dates.py           # 78 lines — date format/range validation
│   │   └── requirements.txt            # pandas, openpyxl, xlsxwriter, pymongo
│   ├── assets/
│   │   ├── cloud_kitchen_pl.xlsx       # Reference template
│   │   └── pnl_template.xlsx           # Excel output template
│   └── references/
│       ├── data_sources.md             # MongoDB collection/field mappings
│       └── pnl_layout.md               # Excel row positions, formatting, column widths
└── sales-analysis/
    ├── SKILL.md
    ├── README.md
    └── TESTING.md
```

### P&L Script — MongoDB Collections Queried

| Collection | Data extracted |
|---|---|
| `orders` | Dine-in revenue, order counts |
| `delivery_orders` | Delivery revenue, channel breakdown, commissions |
| `menu_items` | Item categories and tags (veg/non-veg/beverage etc.) |
| `recipe_bom` | Ingredient ratios per dish (for COGS calculation) |
| `raw_material_inventory` | Raw material unit costs |
| `packaging_bom` | Packaging ratios per dish |
| `packaging_materials` | Packaging unit costs |
| `stock_movement_log` | Wastage and staff meals (COGS add-back) |
| `users` | Staff count and roles (for labour cost) |
| `restaurant_settings` | Commission rates, salary config, tax rates, OPEX budgets |
| `fixed_assets` | Asset values and depreciation schedules |

### P&L Sections Generated (A–M)

| Section | Content |
|---|---|
| A | Gross Merchandise Value (GMV) — dine-in + delivery |
| B | Net Revenue — after commissions, GST deducted |
| C | Cost of Goods Sold — raw materials + packaging + wastage |
| D | Gross Profit |
| E | Operating Expenses — occupancy, technology, marketing, G&A |
| F | EBITDA |
| G | Depreciation & Amortisation |
| H | EBIT |
| I | Finance Costs |
| J | Profit Before Tax |
| K | Income Tax |
| L | Profit After Tax |
| M | Key Performance Indicators (food cost %, labour %, EBITDA %) |

---

## Cost Model

### Current cost per request (as of 2026-04-14)

| Query type | Model | Approx tokens | Approx cost |
|---|---|---|---|
| P&L text/Excel | Local subprocess only | 0 LLM tokens for generation | ~$0 (subprocess) |
| P&L date clarification (fallback) | claude-haiku-4-5 | ~300 in + 50 out | ~$0.0001 |
| Inventory query | claude-sonnet-4-5 | ~1,500 in + 300 out | ~$0.006 |
| Profit analysis | claude-sonnet-4-5 | ~2,000 in + 500 out | ~$0.010 |
| General chat | claude-sonnet-4-5 | ~500 in + 200 out | ~$0.002 |

### Target economics

| Volume | Monthly cost | Annual cost |
|---|---|---|
| 100 queries/day mix | ~$6–18/month | ~$72–216/year |
| 50 queries/day | ~$3–9/month | ~$36–108/year |

This is within the ₹20,000/year (~$240/year) product price target when query volume is moderate. High inventory/profit query volume (Sonnet) is the main cost driver.

---

## Commit History

| Commit | Description |
|---|---|
| `6d184d0` | Initial chatbot with P&L via Anthropic Skills API (original Skills-container path) |
| `afb7294` | Fix menu category visibility, improve chatbot UI |
| `c54451d` | Markdown rendering, full-width assistant layout |
| `dd5ba36` | Inventory tool-calling handler with 4 tools |
| `fe838ba` | Settings API, chatbot & P&L skill wiring, SkillUploader |
| `3377ca3` | Profit analysis handler with 5 tools |
| `fbc7f86` | Date parsing improvements, subprocess Mongo config (moves P&L off Skills container) |

---

## Decisions Rejected / Deferred

### Rejected: Skills API container execution for P&L (reversed in `fbc7f86`)
- **Reason**: Cold-start latency (10–30 s), MongoDB credential passing to external container, and no accuracy benefit over local subprocess.

### Rejected: LLM for intent classification
- **Reason**: Restaurant queries fall into predictable domains. Keyword matching achieves the same result at zero cost.

### Rejected: Persisting conversation history in MongoDB
- **Reason**: Session data has no post-session value. In-memory with a 20-message cap is sufficient.

### Deferred: Nightly pre-computation of analytics
- **Why**: Would reduce Sonnet token costs significantly for inventory and profit queries by pre-aggregating daily/weekly/monthly summaries. Blocked on: deciding what to pre-compute, where to store it (MongoDB collection vs Redis), and wiring APScheduler. Revisit when query volume justifies the infrastructure.

### Deferred: Prompt caching for inventory/demand system prompts
- **Why**: Anthropic prompt caching requires a `cache_control: {"type": "ephemeral"}` block on the system prompt and a minimum 1,024 cached tokens. Inventory system prompt is shorter than that. Worth adding once system prompts are expanded with more context.

### Deferred: Haiku model for general and inventory queries (cost optimisation)
- **Why**: Current implementation uses `claude-sonnet-4-5` for all handlers. Switching inventory and general queries to `claude-haiku-4-5` would cut those costs by ~20×. Deferred to measure quality degradation first.

### Deferred: `sales-analysis` skill integration
- **Why**: The `skills/sales-analysis/` package exists (SKILL.md, README, TESTING.md) but is not wired into `ChatbotService`. No handler or intent routing for it yet. The profit analysis tool-calling handler partially covers its use case.

### Deferred: Admin UI to clear skill cache / re-upload skills
- **Why**: Currently done by deleting `skills/.skill_cache.json` manually. A `/api/v1/chatbot/admin/refresh-skill` endpoint would make this operationally safe.

---

## Known Limitations

| Issue | Impact | Path forward |
|---|---|---|
| In-memory conversation history lost on server restart | Users lose context across deployments | Acceptable for now; persist to MongoDB if sessions need to survive restarts |
| Reports directory fills up over time | Disk usage grows with every P&L request | Add a retention job to delete reports older than 7 days |
| 30-second subprocess timeout | Long date ranges (full year, large dataset) may time out | Profile `generate_pnl.py` execution time; add progress indicator or async job pattern |
| Sonnet used for all tool-calling intents | Higher cost than necessary for simple queries | Route low-complexity inventory queries to Haiku |
| `sales-analysis` skill not wired | Sales trend analysis unavailable in chatbot | Add intent keywords and handler for `sales-analysis` skill |
| No streaming | Long responses appear all at once after full generation | Add SSE streaming via `client.messages.stream()` for better perceived performance |
| Skills API contract is beta | `anthropic-beta: skills-2025-10-02` header may change | Monitor Anthropic SDK changelog; pin SDK version in requirements.txt |

---

## Output / Affected Files

| File | Purpose |
|---|---|
| `backend/app/api/v1/chatbot.py` | HTTP layer — message endpoint, download endpoint, auth guard |
| `backend/app/services/chatbot_service.py` | Core orchestration — intent routing, all handlers, date parser, conversation history |
| `backend/app/services/skill_uploader.py` | Skills API client — upload, cache, verify, delete |
| `backend/app/core/config.py` | Claude model names, Skills API settings, reports dir path |
| `backend/app/services/data_loader.py` | Excel data access for profit analysis queries |
| `skills/pnl-statement/SKILL.md` | Skill documentation (workflow, config guide, troubleshooting) |
| `skills/pnl-statement/scripts/generate_pnl.py` | Full P&L calculator — text + XLSX output |
| `skills/pnl-statement/scripts/validate_dates.py` | Date validation before P&L generation |
| `skills/pnl-statement/references/data_sources.md` | MongoDB field mappings for the P&L script |
| `skills/pnl-statement/references/pnl_layout.md` | Excel layout spec (row positions, formatting) |
| `skills/sales-analysis/` | Sales-analysis skill package (not yet wired into chatbot) |
| `skills/.skill_cache.json` | Runtime cache — skill IDs from last upload (gitignored) |
| `frontend/src/pages/ChatbotPage.tsx` | Chat UI — message list, input, token counter, download button |
| `frontend/src/services/chatbot.ts` | Frontend API client — sendMessage, getDownloadUrl |

---

## Next Decisions Pending

1. **Haiku for low-complexity queries** — Switch `general` and simple `inventory` queries from Sonnet to Haiku. Define what "simple" means (no tool calls? single-tool?) and measure quality difference before committing.
2. **Nightly analytics pre-computation** — Decide what summaries to pre-compute (daily_summary, weekly_summary, inventory_status, top_items_7d), where to store them, and which chatbot handlers should read from cache vs live MongoDB.
3. **`sales-analysis` skill wiring** — Add intent routing and a handler for sales trend queries. Define what Claude does with the skill output vs what the Python script computes independently.
4. **Report retention policy** — How long to keep Excel files in `backend/static/reports/`. Add a cleanup job (APScheduler cron or OS-level cron).
5. **Streaming responses** — When, if ever, to add SSE streaming. P&L generation is subprocess-bound (can't stream mid-generation); tool-calling responses could stream Claude's text output between tool calls.
6. **Skills API graduation** — The beta header `skills-2025-10-02` will change when the API exits beta. Track in `requirements.txt` and pin the SDK version to avoid breaking changes.
7. **Profit analysis data source** — Profit analysis tools currently query MongoDB live. As query complexity grows, consider whether `analytics_aggregator.py` (already exists as a service) should pre-aggregate the data profit tools need.
