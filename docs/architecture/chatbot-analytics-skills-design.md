# Skill-Enabled Claude Analytics Assistant - System Design

**Version:** 2.0
**Date:** 2026-02-18
**Status:** Design Proposal (Revised)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Requirements Analysis](#requirements-analysis)
3. [Prerequisites & Dependencies](#prerequisites--dependencies)
4. [Cost Optimization Strategy](#cost-optimization-strategy)
5. [Architecture Overview](#architecture-overview)
6. [Data Strategy](#data-strategy)
7. [Implementation Details](#implementation-details)
8. [API Contract & Migration](#api-contract--migration)
9. [File Handling](#file-handling)
10. [Error Handling & Resilience](#error-handling--resilience)
11. [Security Considerations](#security-considerations)
12. [Testing Strategy](#testing-strategy)
13. [Deployment Plan](#deployment-plan)
14. [Future Enhancements](#future-enhancements)

---

## Executive Summary

This document outlines the design for upgrading the admin chatbot from a generic advisor to a **skill-enabled analytics assistant** that can:

- Generate downloadable P&L reports as Excel files
- Provide data-driven inventory insights from test data
- Deliver demand prediction analytics from historical data
- Maintain multi-turn conversational context (existing behavior preserved)

**Key Design Principles:**
- **Cost-First Architecture**: Minimize API costs through intelligent intent routing and model selection
- **Progressive Disclosure**: Load skills and data only when needed
- **Hybrid Response Model**: Files for complex reports, text for quick insights
- **Fail-Safe Design**: Graceful degradation when skills fail
- **Non-Breaking Migration**: Frontend changes are additive; existing `reply` field preserved

**Expected Cost Profile:**
- P&L queries: ~$0.30-0.50 per request (Sonnet + xlsx skill + code execution overhead)
- Text analytics: ~$0.02-0.04 per request (Haiku with cached context)
- Conversation maintenance: ~$0.005 per turn (Haiku)

---

## Requirements Analysis

### Functional Requirements

| Requirement | Priority | Complexity |
|-------------|----------|------------|
| Intent classification (P&L vs Inventory vs Demand vs General) | **Critical** | Low |
| P&L Excel generation with downloadable link | **High** | Medium |
| Inventory analytics from lexis_test_data | **High** | Medium |
| Demand prediction analytics from historical data | **High** | Medium |
| Multi-turn conversation with context (must preserve) | **High** | Medium |
| File lifecycle management (cleanup) | **Medium** | Low |
| Admin-only authorization (existing, no changes needed) | **Critical** | None |
| Error fallback to generic responses | **Medium** | Low |

### Non-Functional Requirements

| Requirement | Target | Strategy |
|-------------|--------|----------|
| Response latency | < 5s for text, < 30s for files | Haiku for routing, async execution |
| Cost per request | < $0.10 average | Intent-based model selection |
| Availability | 99% uptime | Graceful skill failure handling |
| Data privacy | No data leakage | Admin-only, session-based access |

---

## Prerequisites & Dependencies

### SDK Upgrade (CRITICAL)

The current `anthropic==0.39.0` does **not** support Skills, Files API, or code execution. These require a significantly newer version.

**Required change in `backend/requirements.txt`:**
```diff
- anthropic==0.39.0
+ anthropic>=0.75.0
```

The following beta APIs are needed:
- `client.beta.messages.create()` with `container` and `skills` parameters
- `client.beta.files.download()` / `client.beta.files.retrieve_metadata()`
- `client.beta.skills.list()` (optional, for listing available skills)

**Verify after upgrade:**
```python
import anthropic
client = anthropic.AsyncAnthropic(api_key="test")
assert hasattr(client.beta, 'files'), "Files API not available"
assert hasattr(client.beta, 'skills'), "Skills API not available"
```

### New Dependencies

**Add to `backend/requirements.txt`:**
```
pandas>=2.0.0
openpyxl>=3.1.0
```

These are required by `DataLoader` to read `.xlsx` files from `lexis_test_data/`.

### Required Beta Headers

```python
BETAS_SKILLS = [
    "code-execution-2025-08-25",   # Enable code execution environment
    "skills-2025-10-02",            # Enable Skills API
]

BETAS_FILES = [
    "files-api-2025-04-14",         # Enable Files API for downloads
]

BETAS_CACHING = [
    "prompt-caching-2024-07-31",    # Enable prompt caching for data context
]
```

### Actual Data Schema (lexis_test_data/)

Column names use **PascalCase with underscores**. All code must reference these exactly.

| File | Rows | Key Columns |
|------|------|-------------|
| `orders.xlsx` | 10,000 | `Order_ID`, `Order_Date`, `Total_INR`, `Subtotal_INR`, `Tax_GST_INR`, `Order_Channel`, `Order_Status`, `Num_Items` |
| `daily_aggregates.xlsx` | 225 | `Date`, `Total_Orders`, `Total_Revenue`, `Avg_Order_Value`, `Cancellation_Rate`, `Avg_Rating` |
| `raw_material_inventory.xlsx` | 25 | `Material_ID`, `Material_Name`, `Category`, `Unit_Cost_INR`, `Current_Stock`, `Reorder_Level` |
| `stock_movement_log.xlsx` | 200 | `Transaction_ID`, `Date`, `Material_ID`, `Material_Name`, `Movement_Type`, `Quantity` |
| `supplier_master.xlsx` | 11 | `Supplier_ID`, `Supplier_Name`, `Category`, `Rating`, `Reliability_Score` |
| `customer_dimension.xlsx` | 2,453 | `Customer_ID`, `Customer_Segment`, `Total_Spend_INR`, `Total_Orders`, `Is_Churned` |
| `time_features.xlsx` | 229 | `Date`, `Day_of_Week`, `Is_Weekend`, `Is_Holiday`, `Quarter` |
| `order_line_items.xlsx` | 25 | `Material_ID`, `Material_Name`, `Unit_Cost_INR`, `Current_Stock` |
| `data_dictionary.xlsx` | 38 | `Sheet`, `Column`, `Data_Type`, `Description` |

---

## Cost Optimization Strategy

### 1. Two-Phase Request Model

**Phase 1: Intent Classification (Cheap & Fast)**
- Use **Claude Haiku** (~$0.001 per request)
- Simple classification prompt: "p_and_l", "inventory", "demand", "general"
- No skills loaded, minimal context
- ~500 tokens total

**Phase 2: Skill Execution (Conditional)**
- Load skills **only** if needed for query type:
  - **P&L**: Sonnet + xlsx skill (~$0.30-0.50)
  - **Inventory/Demand**: Haiku + data context (~$0.02-0.04)
  - **General**: Haiku, no skills (~$0.005)

### 2. Model Selection Matrix

```
+-------------------+--------------+--------------+--------------+
| Query Type        | Model        | Skills       | Est. Cost    |
+-------------------+--------------+--------------+--------------+
| P&L Report        | Sonnet 4.5   | xlsx         | $0.30-0.50   |
| Inventory Query   | Haiku 4.5    | None (data)  | $0.02-0.04   |
| Demand Forecast   | Haiku 4.5    | None (data)  | $0.02-0.04   |
| General Chat      | Haiku 4.5    | None         | $0.005-0.01  |
+-------------------+--------------+--------------+--------------+
```

> **Note on P&L cost**: Code execution container startup, skill loading, and
> potential `pause_turn` continuations add overhead beyond raw token costs.
> The $0.30-0.50 estimate accounts for ~2 API round-trips on average.

### 3. Prompt Caching Strategy

Enable **prompt caching** for inventory and demand queries. This requires the
`prompt-caching-2024-07-31` beta header **and** using `client.beta.messages.create()`.

```python
# Inventory/Demand handlers use beta API with caching
response = await client.beta.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    betas=["prompt-caching-2024-07-31"],
    system=[
        {"type": "text", "text": "You are a restaurant inventory analyst."},
        {
            "type": "text",
            "text": inventory_data,
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=conversation_history,
)
```

**Savings**: ~70% reduction on input tokens for repeated queries within the cache window.

### 4. Skill Usage Optimization

**Use Anthropic's pre-built xlsx skill** (not a custom skill):
- Pre-built xlsx skill: included, well-tested, no upload cost
- Custom analytics skill: upload overhead, 8MB limit, maintenance burden

**When to load xlsx skill:**
- ONLY for P&L Excel generation
- NOT for simple data queries (answer in text)

---

## Architecture Overview

### High-Level Architecture

```
+-------------------------------------------------------------+
|                     Frontend (React)                         |
|  ChatbotPage.tsx -> chatbot.ts (API service)                 |
+----------------------------+--------------------------------+
                             |
                             | POST /api/v1/chatbot/message
                             v
+-------------------------------------------------------------+
|                  Backend (FastAPI)                            |
|  +-------------------------------------------------------+  |
|  |  chatbot.py (Route Handler)                            |  |
|  |  - Uses existing get_admin_user dependency             |  |
|  |  - Calls chatbot_service (async)                       |  |
|  |  - Returns reply + optional file metadata              |  |
|  +------------------------+------------------------------+  |
|                           |                                  |
|                           v                                  |
|  +-------------------------------------------------------+  |
|  |  chatbot_service.py (Core Logic - AsyncAnthropic)      |  |
|  |                                                         |  |
|  |  +--------------------------------------------------+  |  |
|  |  | 1. Intent Classifier (Haiku, no skills)           |  |  |
|  |  |    Returns: p_and_l | inventory | demand | general|  |  |
|  |  +---------------------+----------------------------+  |  |
|  |                        |                                |  |
|  |       +----------------+----------------+               |  |
|  |       v                v                v               |  |
|  |  +---------+  +----------------+  +----------+         |  |
|  |  | P&L     |  | Inventory      |  | Demand   |         |  |
|  |  | Handler |  | Handler        |  | Handler  |         |  |
|  |  | (Sonnet)|  | (Haiku + cache)|  | (Haiku + |         |  |
|  |  | + xlsx  |  |                |  |  cache)  |         |  |
|  |  | skill   |  |                |  |          |         |  |
|  |  +----+----+  +-------+--------+  +-----+----+         |  |
|  |       |               |                  |              |  |
|  |       v               v                  v              |  |
|  |  +--------------------------------------------------+  |  |
|  |  | Response Formatter                                |  |  |
|  |  |  - Always includes reply (text)                   |  |  |
|  |  |  - Optionally includes file_id, filename, url     |  |  |
|  |  +--------------------------------------------------+  |  |
|  |                                                         |  |
|  |  +--------------------------------------------------+  |  |
|  |  | Conversation History (per user, in-memory)        |  |  |
|  |  | - Shared across all handlers                      |  |  |
|  |  | - Trimmed to MAX_HISTORY_MESSAGES                  |  |  |
|  |  +--------------------------------------------------+  |  |
|  +-------------------------------------------------------+  |
+----------------------------+---------------------------------+
                             |
                             v
+-------------------------------------------------------------+
|              Anthropic Claude API                            |
|  - AsyncAnthropic client (non-blocking)                      |
|  - Beta: code-execution, skills, files-api, prompt-caching   |
|  - Skills: xlsx (anthropic pre-built)                        |
|  - Files API: download generated Excel files                 |
+-------------------------------------------------------------+
```

### Component Responsibilities

#### 1. Intent Classifier
- **Model**: Claude Haiku 4.5
- **Input**: User message (standalone; no history needed for classification)
- **Output**: Intent label (`"p_and_l"` | `"inventory"` | `"demand"` | `"general"`)
- **Cost**: ~$0.001 per classification

> **Note**: Intent uses `"p_and_l"` (not `"p&l"`) to avoid ampersand parsing issues
> in LLM output.

#### 2. P&L Handler
- **Model**: Claude Sonnet 4.5
- **Skills**: Anthropic xlsx (pre-built)
- **Data**: Pre-aggregated financial summary (computed server-side from orders.xlsx)
- **Process**:
  1. Load **pre-aggregated** financial data (NOT raw 10K rows)
  2. Send to Sonnet with xlsx skill
  3. Handle `pause_turn` continuations
  4. Extract `file_id` from response
  5. Return file metadata for download
- **Cost**: ~$0.30-0.50 per report

#### 3. Inventory Handler
- **Model**: Claude Haiku 4.5 (via beta API for prompt caching)
- **Data Context**: `raw_material_inventory.xlsx` (25 rows), `stock_movement_log.xlsx` (200 rows), `supplier_master.xlsx` (11 rows)
- **Process**:
  1. Load data into prompt (prompt cached via beta API)
  2. Include conversation history for multi-turn context
  3. Return text response

#### 4. Demand Handler
- **Model**: Claude Haiku 4.5 (via beta API for prompt caching)
- **Data Context**: `daily_aggregates.xlsx` (225 rows), `time_features.xlsx` (229 rows)
- **Process**:
  1. Load historical data (prompt cached via beta API)
  2. Include conversation history for multi-turn context
  3. Return text response

---

## Data Strategy

### The Problem: orders.xlsx Is Too Large for Prompt Context

`orders.xlsx` has **10,000 rows and 43 columns** (2.4MB). Sending this raw as prompt text would:
- Cost ~$1-2 in input tokens per request
- Exceed context window limits
- Slow down response time significantly

### Solution: Server-Side Pre-Aggregation

The `DataLoader` reads the raw Excel files once at startup and computes **aggregated summaries** that are small enough for prompt context but detailed enough for meaningful P&L generation.

```python
# DataLoader computes aggregations like:
# - Monthly revenue, expenses, profit by category
# - Channel breakdown (Zomato, Swiggy, WalkIn)
# - Order status distribution
# - Tax and discount summaries
# - Daily revenue trends
```

This keeps prompt context under ~2,000 tokens while providing the xlsx skill enough detail to build a structured P&L report.

### Data Loading by Handler

| Handler | Files Used | Rows in Context | Estimated Tokens |
|---------|-----------|-----------------|------------------|
| P&L | orders (aggregated), daily_aggregates | ~50 lines summary | ~1,500 |
| Inventory | raw_material_inventory, stock_movement_log, supplier_master | ~256 rows total | ~3,000 |
| Demand | daily_aggregates, time_features | ~454 rows total | ~4,000 |

### Cache Invalidation

The `DataLoader` cache has a **TTL** (default 5 minutes) so data changes
are picked up without server restart:

```python
CACHE_TTL_SECONDS = int(os.getenv("CHATBOT_CACHE_TTL", "300"))
```

---

## Implementation Details

### Backend Service Architecture

```python
# backend/app/services/chatbot_service.py

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

import anthropic
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Intent categories (use underscores to avoid parsing issues in LLM output)
INTENT_CATEGORIES = ["p_and_l", "inventory", "demand", "general"]

# Cap history to avoid token limits
MAX_HISTORY_MESSAGES = 20

# pause_turn retry limit for long-running skill operations
MAX_PAUSE_TURN_RETRIES = 10


@dataclass
class ChatResponse:
    """Response from chatbot service."""
    reply: str                              # Always present (text answer)
    file_id: Optional[str] = None           # Set when a file was generated
    filename: Optional[str] = None          # Original filename
    download_url: Optional[str] = None      # Backend download endpoint


# ---------------------------------------------------------------------------
# Conversation history (in-memory, per user)
# ---------------------------------------------------------------------------
_chat_history: Dict[str, List[Dict[str, str]]] = {}


def _get_history(user_id: str) -> List[Dict[str, str]]:
    if user_id not in _chat_history:
        _chat_history[user_id] = []
    return _chat_history[user_id]


def _trim_history(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages
    return messages[-MAX_HISTORY_MESSAGES:]


def _append_to_history(user_id: str, role: str, content: str):
    history = _get_history(user_id)
    history.append({"role": role, "content": content})
    _chat_history[user_id] = _trim_history(history)


# ---------------------------------------------------------------------------
# Intent classifier
# ---------------------------------------------------------------------------

INTENT_PROMPT = """Classify the user's query into exactly one category.
Respond with ONLY the category label, nothing else.

Categories:
- p_and_l: Profit & Loss reports, revenue analysis, expense breakdown, financial statements
- inventory: Stock levels, raw material availability, supplier info, reorder status
- demand: Sales forecasting, demand prediction, trend analysis, seasonal patterns
- general: General restaurant advice, unrelated questions

User query: "{query}"
"""


async def _classify_intent(client: anthropic.AsyncAnthropic, message: str) -> str:
    """Classify user intent using Haiku (fast & cheap)."""
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{
            "role": "user",
            "content": INTENT_PROMPT.format(query=message)
        }]
    )
    intent = response.content[0].text.strip().lower().replace(" ", "_")
    return intent if intent in INTENT_CATEGORIES else "general"


# ---------------------------------------------------------------------------
# P&L handler (Sonnet + xlsx skill + pause_turn loop)
# ---------------------------------------------------------------------------

async def _handle_pnl_query(
    client: anthropic.AsyncAnthropic,
    user_id: str,
    message: str,
    data_loader: "DataLoader",
) -> ChatResponse:
    """Generate P&L Excel using Sonnet + xlsx skill with pause_turn handling."""
    financial_data = data_loader.load_financial_data()
    history = _get_history(user_id)

    # Build messages: include recent history for multi-turn context
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in _trim_history(history)
    ]

    pnl_system = (
        "You are a restaurant financial analyst. "
        "Generate a professional Profit & Loss Excel report from the data provided. "
        "Include: revenue breakdown by channel, expense categories (COGS, tax, "
        "discounts, delivery fees, packaging), gross and net profit, and a monthly "
        "trend chart. Use the xlsx skill to create the file."
    )

    try:
        response = await client.beta.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8192,
            betas=["code-execution-2025-08-25", "skills-2025-10-02"],
            system=pnl_system,
            container={
                "skills": [{
                    "type": "anthropic",
                    "skill_id": "xlsx",
                    "version": "latest"
                }]
            },
            messages=api_messages + [{
                "role": "user",
                "content": (
                    f"Generate a P&L report as an Excel file.\n\n"
                    f"Financial data:\n{financial_data}\n\n"
                    f"User request: {message}"
                )
            }],
            tools=[{
                "type": "code_execution_20250825",
                "name": "code_execution"
            }]
        )

        # Handle pause_turn for long-running skill operations
        continuation_messages = api_messages + [{
            "role": "user",
            "content": (
                f"Generate a P&L report as an Excel file.\n\n"
                f"Financial data:\n{financial_data}\n\n"
                f"User request: {message}"
            )
        }]

        for _ in range(MAX_PAUSE_TURN_RETRIES):
            if response.stop_reason != "pause_turn":
                break

            continuation_messages.append({
                "role": "assistant",
                "content": response.content
            })

            response = await client.beta.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8192,
                betas=["code-execution-2025-08-25", "skills-2025-10-02"],
                system=pnl_system,
                container={
                    "id": response.container.id,
                    "skills": [{
                        "type": "anthropic",
                        "skill_id": "xlsx",
                        "version": "latest"
                    }]
                },
                messages=continuation_messages,
                tools=[{
                    "type": "code_execution_20250825",
                    "name": "code_execution"
                }]
            )

        # Extract file_id from response
        file_id = _extract_file_id(response)

        # Also extract any text summary from the response
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        reply_text = " ".join(text_parts).strip() or "P&L report generated."

        if file_id:
            return ChatResponse(
                reply=reply_text,
                file_id=file_id,
                filename="pnl_report.xlsx",
                download_url=f"/api/v1/chatbot/download/{file_id}"
            )

    except Exception as e:
        logger.warning(f"P&L Excel generation failed: {e}")

    # Fallback: text-only P&L summary using Haiku
    return await _handle_pnl_text_fallback(client, user_id, message, data_loader)


async def _handle_pnl_text_fallback(
    client: anthropic.AsyncAnthropic,
    user_id: str,
    message: str,
    data_loader: "DataLoader",
) -> ChatResponse:
    """Fallback: generate text P&L summary when xlsx skill fails."""
    financial_data = data_loader.load_financial_data()
    history = _get_history(user_id)

    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in _trim_history(history)
    ]
    api_messages.append({
        "role": "user",
        "content": (
            f"Provide a text-based P&L summary.\n\n"
            f"Financial data:\n{financial_data}\n\n"
            f"User request: {message}"
        )
    })

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=(
            "You are a restaurant financial analyst. Provide a clear, "
            "formatted text P&L summary. Note that Excel generation was "
            "unavailable, so present the data in a readable text format."
        ),
        messages=api_messages,
    )

    reply = response.content[0].text.strip()
    return ChatResponse(
        reply=f"(Excel generation unavailable; text summary below)\n\n{reply}"
    )


# ---------------------------------------------------------------------------
# Inventory handler (Haiku + cached data + multi-turn history)
# ---------------------------------------------------------------------------

async def _handle_inventory_query(
    client: anthropic.AsyncAnthropic,
    user_id: str,
    message: str,
    data_loader: "DataLoader",
) -> ChatResponse:
    """Answer inventory query using Haiku + prompt-cached data."""
    inventory_data = data_loader.load_inventory_data()
    history = _get_history(user_id)

    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in _trim_history(history)
    ]
    api_messages.append({"role": "user", "content": message})

    response = await client.beta.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        betas=["prompt-caching-2024-07-31"],
        system=[
            {
                "type": "text",
                "text": (
                    "You are a restaurant inventory analyst. Answer questions "
                    "about stock levels, suppliers, and material availability "
                    "using the data provided. Be specific with numbers."
                ),
            },
            {
                "type": "text",
                "text": inventory_data,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=api_messages,
    )

    return ChatResponse(reply=response.content[0].text.strip())


# ---------------------------------------------------------------------------
# Demand handler (Haiku + cached data + multi-turn history)
# ---------------------------------------------------------------------------

async def _handle_demand_query(
    client: anthropic.AsyncAnthropic,
    user_id: str,
    message: str,
    data_loader: "DataLoader",
) -> ChatResponse:
    """Answer demand forecast query using Haiku + prompt-cached data."""
    demand_data = data_loader.load_demand_data()
    history = _get_history(user_id)

    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in _trim_history(history)
    ]
    api_messages.append({"role": "user", "content": message})

    response = await client.beta.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        betas=["prompt-caching-2024-07-31"],
        system=[
            {
                "type": "text",
                "text": (
                    "You are a restaurant demand forecasting analyst. "
                    "Identify trends, seasonality, and provide forecasts "
                    "based on the historical data provided."
                ),
            },
            {
                "type": "text",
                "text": demand_data,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=api_messages,
    )

    return ChatResponse(reply=response.content[0].text.strip())


# ---------------------------------------------------------------------------
# General handler (Haiku, no skills, multi-turn history)
# ---------------------------------------------------------------------------

async def _handle_general_query(
    client: anthropic.AsyncAnthropic,
    user_id: str,
    message: str,
) -> ChatResponse:
    """Handle general queries (preserves existing behavior)."""
    history = _get_history(user_id)

    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in _trim_history(history)
    ]
    api_messages.append({"role": "user", "content": message})

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system="You are a helpful restaurant operations advisor.",
        messages=api_messages,
    )

    return ChatResponse(reply=response.content[0].text.strip())


# ---------------------------------------------------------------------------
# File ID extraction (handles multiple response formats)
# ---------------------------------------------------------------------------

def _extract_file_id(response) -> Optional[str]:
    """
    Extract file_id from Claude response.

    The response structure varies between SDK versions and skill types.
    This handles both known patterns:
    1. bash_code_execution_tool_result -> bash_code_execution_result -> content
    2. Flat content blocks with file_id attribute
    """
    for block in response.content:
        # Pattern 1: bash_code_execution_tool_result wrapper
        if hasattr(block, "type") and block.type == "bash_code_execution_tool_result":
            content_item = getattr(block, "content", None)
            if content_item and hasattr(content_item, "type"):
                if content_item.type == "bash_code_execution_result":
                    inner_content = getattr(content_item, "content", [])
                    for file_obj in inner_content:
                        if hasattr(file_obj, "file_id"):
                            return file_obj.file_id

        # Pattern 2: Direct file reference in content block
        if hasattr(block, "file_id"):
            return block.file_id

        # Pattern 3: Nested in tool_use result
        if hasattr(block, "type") and block.type == "tool_use":
            if hasattr(block, "content"):
                for sub in (block.content if isinstance(block.content, list) else []):
                    if hasattr(sub, "file_id"):
                        return sub.file_id

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def get_reply(user_id: str, message: str) -> ChatResponse:
    """
    Process a user message and return the assistant reply.

    Multi-turn: appends user message to history, classifies intent,
    routes to appropriate handler, appends reply to history.

    Args:
        user_id: Identifier for the user (admin id).
        message: The user's message text.

    Returns:
        ChatResponse with reply text and optional file metadata.
    """
    settings = get_settings()

    if not (settings.CLAUDE_API_KEY and settings.CLAUDE_API_KEY.strip()):
        return ChatResponse(
            reply="API key not configured. Add CLAUDE_API_KEY to your .env."
        )

    # Append user message to history
    _append_to_history(user_id, "user", message.strip())

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.CLAUDE_API_KEY.strip())
        data_loader = DataLoader.get_instance()

        # Phase 1: Classify intent (cheap, ~$0.001)
        intent = await _classify_intent(client, message)

        # Phase 2: Route to handler
        if intent == "p_and_l":
            result = await _handle_pnl_query(client, user_id, message, data_loader)
        elif intent == "inventory":
            result = await _handle_inventory_query(
                client, user_id, message, data_loader
            )
        elif intent == "demand":
            result = await _handle_demand_query(
                client, user_id, message, data_loader
            )
        else:
            result = await _handle_general_query(client, user_id, message)

        # Append assistant reply to history
        _append_to_history(user_id, "assistant", result.reply)
        return result

    except Exception as e:
        logger.error(f"Chatbot error for user {user_id}: {e}")
        # Remove the user message from history to keep it in sync
        history = _get_history(user_id)
        if history and history[-1]["role"] == "user":
            history.pop()
        return ChatResponse(
            reply="Sorry, I couldn't process that. Please try again."
        )
```

### Data Loader Component

```python
# backend/app/services/data_loader.py

import os
import time
import logging
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = int(os.getenv("CHATBOT_CACHE_TTL", "300"))


class DataLoader:
    """
    Load and format lexis_test_data for Claude context.

    Singleton with TTL-based cache invalidation.
    """

    _instance: Optional["DataLoader"] = None

    @classmethod
    def get_instance(cls) -> "DataLoader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._data_dir = Path(
            os.getenv("DATA_PATH", "lexis_test_data")
        )
        self._cache: Dict[str, str] = {}
        self._cache_timestamps: Dict[str, float] = {}

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache_timestamps:
            return False
        return (time.time() - self._cache_timestamps[key]) < CACHE_TTL_SECONDS

    def _set_cache(self, key: str, value: str):
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()

    def load_financial_data(self) -> str:
        """
        Load AGGREGATED financial data for P&L generation.

        Does NOT send raw 10K rows. Pre-computes monthly summaries,
        channel breakdowns, and expense categories server-side.
        """
        if self._is_cache_valid("financial"):
            return self._cache["financial"]

        try:
            orders = pd.read_excel(self._data_dir / "orders.xlsx")
            daily_agg = pd.read_excel(self._data_dir / "daily_aggregates.xlsx")

            # --- Server-side aggregation (keeps prompt context small) ---

            # Monthly revenue summary
            orders["Order_Month_Year"] = pd.to_datetime(
                orders["Order_Date"]
            ).dt.to_period("M").astype(str)
            monthly = orders.groupby("Order_Month_Year").agg(
                Total_Revenue=("Total_INR", "sum"),
                Total_Orders=("Order_ID", "count"),
                Subtotal=("Subtotal_INR", "sum"),
                Tax_GST=("Tax_GST_INR", "sum"),
                Discounts=("Promo_Discount_INR", "sum"),
                Item_Discounts=("Item_Discount_INR", "sum"),
                Delivery_Fees=("Delivery_Fee_INR", "sum"),
                Packaging=("Packaging_Charge_INR", "sum"),
                Avg_Order_Value=("Total_INR", "mean"),
            ).round(2)

            # Channel breakdown
            channel = orders.groupby("Order_Channel").agg(
                Orders=("Order_ID", "count"),
                Revenue=("Total_INR", "sum"),
            ).round(2)

            # Order status distribution
            status_dist = orders["Order_Status"].value_counts().to_dict()

            # Cancellation rate
            cancel_rate = orders["Order_Status"].eq("Cancelled").mean() * 100

            context = f"""Financial Data (Pre-Aggregated):

MONTHLY P&L SUMMARY:
{monthly.to_markdown()}

REVENUE BY CHANNEL:
{channel.to_markdown()}

ORDER STATUS DISTRIBUTION:
{status_dist}

OVERALL METRICS:
- Total Orders: {len(orders)}
- Date Range: {orders['Order_Date'].min()} to {orders['Order_Date'].max()}
- Total Revenue: INR {orders['Total_INR'].sum():,.2f}
- Total Tax (GST): INR {orders['Tax_GST_INR'].sum():,.2f}
- Total Discounts: INR {(orders['Promo_Discount_INR'].sum() + orders['Item_Discount_INR'].sum()):,.2f}
- Total Delivery Fees: INR {orders['Delivery_Fee_INR'].sum():,.2f}
- Total Packaging Charges: INR {orders['Packaging_Charge_INR'].sum():,.2f}
- Cancellation Rate: {cancel_rate:.1f}%
- Avg Order Value: INR {orders['Total_INR'].mean():,.2f}

DAILY AGGREGATES (last 30 days):
{daily_agg.tail(30)[['Date', 'Total_Orders', 'Total_Revenue', 'Avg_Order_Value', 'Cancellation_Rate']].to_markdown(index=False)}
"""
            self._set_cache("financial", context)
            return context

        except Exception as e:
            logger.error(f"Failed to load financial data: {e}")
            return "Financial data unavailable. Please check data files."

    def load_inventory_data(self) -> str:
        """Load inventory data for stock queries (small enough for full context)."""
        if self._is_cache_valid("inventory"):
            return self._cache["inventory"]

        try:
            inventory = pd.read_excel(
                self._data_dir / "raw_material_inventory.xlsx"
            )
            suppliers = pd.read_excel(self._data_dir / "supplier_master.xlsx")
            stock_log = pd.read_excel(
                self._data_dir / "stock_movement_log.xlsx"
            )

            context = f"""Inventory Data:

RAW MATERIAL INVENTORY ({len(inventory)} items):
{inventory.to_markdown(index=False)}

SUPPLIER MASTER ({len(suppliers)} suppliers):
{suppliers.to_markdown(index=False)}

RECENT STOCK MOVEMENTS (last 30 entries):
{stock_log.tail(30).to_markdown(index=False)}

LOW STOCK ALERTS (Current_Stock <= Reorder_Level):
{inventory[inventory['Current_Stock'] <= inventory['Reorder_Level']][['Material_Name', 'Current_Stock', 'Reorder_Level', 'Unit']].to_markdown(index=False) if len(inventory[inventory['Current_Stock'] <= inventory['Reorder_Level']]) > 0 else 'No items below reorder level.'}
"""
            self._set_cache("inventory", context)
            return context

        except Exception as e:
            logger.error(f"Failed to load inventory data: {e}")
            return "Inventory data unavailable. Please check data files."

    def load_demand_data(self) -> str:
        """Load historical data for demand forecasting."""
        if self._is_cache_valid("demand"):
            return self._cache["demand"]

        try:
            daily_agg = pd.read_excel(self._data_dir / "daily_aggregates.xlsx")
            time_features = pd.read_excel(self._data_dir / "time_features.xlsx")

            # Compute weekly trends for compact representation
            daily_agg["Date"] = pd.to_datetime(daily_agg["Date"])
            daily_agg["Week"] = daily_agg["Date"].dt.isocalendar().week
            daily_agg["Year"] = daily_agg["Date"].dt.year
            weekly = daily_agg.groupby(["Year", "Week"]).agg(
                Avg_Daily_Orders=("Total_Orders", "mean"),
                Avg_Daily_Revenue=("Total_Revenue", "mean"),
                Avg_Rating=("Avg_Rating", "mean"),
            ).round(2)

            context = f"""Demand & Sales Data:

DAILY AGGREGATES (full dataset, {len(daily_agg)} days):
Columns: {', '.join(daily_agg.columns.tolist())}

RECENT DAILY DATA (last 30 days):
{daily_agg.tail(30)[['Date', 'Total_Orders', 'Total_Revenue', 'Unique_Customers', 'New_Customers', 'Repeat_Orders', 'Avg_Rating']].to_markdown(index=False)}

WEEKLY TRENDS:
{weekly.tail(12).to_markdown()}

CHANNEL MIX (last 30 days):
- Zomato: {daily_agg.tail(30)['Zomato_Orders'].sum()} orders
- Swiggy: {daily_agg.tail(30)['Swiggy_Orders'].sum()} orders
- Walk-in: {daily_agg.tail(30)['WalkIn_Orders'].sum()} orders

TIME FEATURES:
Columns: {', '.join(time_features.columns.tolist())}
Date range: {time_features['Date'].min()} to {time_features['Date'].max()}
"""
            self._set_cache("demand", context)
            return context

        except Exception as e:
            logger.error(f"Failed to load demand data: {e}")
            return "Demand data unavailable. Please check data files."
```

---

## API Contract & Migration

### Breaking Change Mitigation

The current API returns `{"reply": "text"}`. The new API must be **backward-compatible**
while adding optional file metadata. The `reply` field is preserved.

#### POST /api/v1/chatbot/message

**Request** (unchanged):
```json
{
  "message": "Generate P&L report for January 2026"
}
```

**Response (text-only, same as before):**
```json
{
  "success": true,
  "data": {
    "reply": "Based on your inventory data, chicken stock is at 45kg..."
  },
  "message": "OK",
  "timestamp": "2026-02-18T10:00:00Z"
}
```

**Response (with file, additive fields):**
```json
{
  "success": true,
  "data": {
    "reply": "P&L report generated. Click download to get the Excel file.",
    "file_id": "file_01AbCdEfGhIjKlMn",
    "filename": "pnl_report.xlsx",
    "download_url": "/api/v1/chatbot/download/file_01AbCdEfGhIjKlMn"
  },
  "message": "OK",
  "timestamp": "2026-02-18T10:00:00Z"
}
```

> **Key**: The `reply` field is **always present** (never renamed to `message`).
> `file_id`, `filename`, and `download_url` are optional additions.
> The existing frontend `response.data.data?.reply` continues to work unchanged.

### Route Handler Update

```python
# backend/app/api/v1/chatbot.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import anthropic
import tempfile
import os

from app.core.config import get_settings
from app.core.dependencies import get_admin_user
from app.models.user import UserResponse
from app.services.chatbot_service import get_reply, ChatResponse
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

MESSAGE_MAX_LENGTH = 4000


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MESSAGE_MAX_LENGTH)


@router.post("/message", response_model=dict)
async def post_message(
    body: ChatMessageRequest,
    admin_user: UserResponse = Depends(get_admin_user),  # Existing auth
):
    """
    Send a message and receive an assistant reply (admin-only).

    Returns reply text always. For P&L queries, also returns
    file_id, filename, and download_url for Excel download.
    """
    result: ChatResponse = await get_reply(admin_user.id, body.message)

    data = {"reply": result.reply}
    if result.file_id:
        data["file_id"] = result.file_id
        data["filename"] = result.filename
        data["download_url"] = result.download_url

    return success_response(data=data, message="OK")


@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    admin_user: UserResponse = Depends(get_admin_user),  # Existing auth
):
    """Download a generated file from Claude Files API (admin-only)."""
    settings = get_settings()

    if not settings.CLAUDE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured"
        )

    try:
        client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY.strip())

        # Get metadata for filename
        file_meta = client.beta.files.retrieve_metadata(
            file_id=file_id,
            betas=["files-api-2025-04-14"]
        )

        # Download to temp file, then stream
        file_content = client.beta.files.download(
            file_id=file_id,
            betas=["files-api-2025-04-14"]
        )

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        file_content.write_to_file(tmp.name)
        tmp.close()

        def iterfile():
            with open(tmp.name, "rb") as f:
                yield from f
            os.unlink(tmp.name)  # Cleanup after streaming

        return StreamingResponse(
            iterfile(),
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{file_meta.filename}"'
                )
            }
        )

    except anthropic.NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or expired"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )
```

### Frontend Service Update

```typescript
// frontend/src/services/chatbot.ts

import apiClient, { getErrorMessage } from './api';
import { APIResponse } from '../types/api';

/** Response data for POST /chatbot/message */
interface ChatbotMessageData {
  reply: string;                    // Always present
  file_id?: string;                 // Present when file was generated
  filename?: string;                // Original filename
  download_url?: string;            // Backend download endpoint
}

type ChatbotMessageResponse = APIResponse<ChatbotMessageData>;

/**
 * Send a message and get the assistant reply (admin-only).
 *
 * @returns Full response data including optional file metadata
 */
export async function sendMessage(message: string): Promise<ChatbotMessageData> {
  try {
    const response = await apiClient.post<ChatbotMessageResponse>(
      '/chatbot/message',
      { message },
    );
    return response.data.data ?? { reply: '' };
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Download a generated file by its download URL.
 */
export async function downloadFile(downloadUrl: string, filename: string): Promise<void> {
  try {
    const response = await apiClient.get(downloadUrl, {
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}
```

---

## File Handling

### File Lifecycle

```
1. Generation
   +-> Claude creates Excel file in code execution container
   +-> Response includes file_id in content blocks

2. Storage
   +-> File stored in Claude's Files API (temporary)
   +-> Expiry: verify actual retention period (may vary)

3. Download
   +-> Backend retrieves via Files API
   +-> Writes to temp file on server
   +-> Streams to frontend as blob
   +-> Temp file cleaned up after streaming

4. Cleanup
   +-> Files expire automatically in Claude's storage
   +-> No manual cleanup required for normal operation
```

### Download Flow (Detailed)

```python
# The download endpoint does NOT use file_content.stream (doesn't exist).
# Instead:
# 1. file_content = client.beta.files.download(file_id=..., betas=[...])
# 2. file_content.write_to_file(tmp_path)   # Write to temp file
# 3. Stream temp file to client
# 4. Delete temp file after streaming
```

---

## Error Handling & Resilience

### Graceful Skill Failure

```
P&L Request
  |
  +-> Try: Sonnet + xlsx skill
  |   |
  |   +-> Success? Return file + text summary
  |   |
  |   +-> pause_turn? Continue (up to 10 retries)
  |   |
  |   +-> No file_id? Fall through to fallback
  |
  +-> Fallback: Haiku text-only P&L summary
  |   |
  |   +-> Returns text summary with note that Excel was unavailable
  |
  +-> Catch-all: Generic error message
```

### Error Scenarios & Responses

| Error | Cause | Handler | User Sees |
|-------|-------|---------|-----------|
| Skill execution timeout | Complex Excel | Fallback to text P&L summary | "Excel unavailable; text summary below..." |
| pause_turn exhausted | Very long operation | Fallback to text P&L summary | Text summary with explanation |
| File ID not found in response | Response format mismatch | Fallback to text P&L summary | Text summary |
| API key missing | Config error | Early return | "API key not configured..." |
| Data file missing | Deployment issue | Return error string in context | "Data unavailable..." |
| Intent classification fails | Ambiguous query | Default to general | Standard chatbot response |
| Files API download 404 | File expired or invalid ID | HTTP 404 | "File not found or expired" |
| Anthropic API error | Rate limit / outage | Catch-all exception handler | "Couldn't process, try again" |

### Circuit Breaker Pattern

```python
import asyncio

class SkillCircuitBreaker:
    """
    Prevent repeated skill failures from blocking service.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self, failure_threshold: int = 3, timeout: float = 300):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._failures = 0
        self._last_failure_time: float = 0
        self._is_open = False
        self._lock = asyncio.Lock()

    async def record_failure(self):
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            if self._failures >= self.failure_threshold:
                self._is_open = True
                logger.error("Circuit breaker OPEN: xlsx skill disabled")

    async def can_execute(self) -> bool:
        async with self._lock:
            if not self._is_open:
                return True
            if time.time() - self._last_failure_time > self.timeout:
                self._is_open = False
                self._failures = 0
                logger.info("Circuit breaker CLOSED: xlsx skill re-enabled")
                return True
            return False

    async def record_success(self):
        async with self._lock:
            self._failures = 0
            self._is_open = False
```

---

## Security Considerations

### 1. Admin-Only Access (No Changes Needed)

The existing `get_admin_user` dependency handles authorization:

```python
# app/core/dependencies.py (existing, unchanged)
async def get_admin_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, ...)
    return current_user
```

Both `/message` and `/download/{file_id}` use this dependency. No additional
role checks are needed (the `UserRole` enum only has `ADMIN` and `STAFF`).

### 2. File Download Authorization

File IDs are opaque Anthropic identifiers. An attacker would need:
1. A valid admin session cookie
2. A valid file_id (not guessable, generated by Anthropic)

For additional safety, maintain an in-memory set of file IDs generated per user:

```python
# Track which user generated which files
_user_file_ids: Dict[str, set] = {}

def register_file(user_id: str, file_id: str):
    if user_id not in _user_file_ids:
        _user_file_ids[user_id] = set()
    _user_file_ids[user_id].add(file_id)

def can_access_file(user_id: str, file_id: str) -> bool:
    return file_id in _user_file_ids.get(user_id, set())
```

### 3. API Key Protection

```python
# API key loaded from environment only (existing pattern)
CLAUDE_API_KEY: str = ""  # in Settings class, loaded from .env

# Never log the full key
if settings.CLAUDE_API_KEY:
    logger.info(f"Claude API configured (key: ...{settings.CLAUDE_API_KEY[-4:]})")
```

### 4. Input Validation

The existing `ChatMessageRequest` model validates:
- `min_length=1` (no empty messages)
- `max_length=4000` (prevents token abuse)

No additional validation needed.

---

## Testing Strategy

### 1. Unit Tests

```python
# tests/test_chatbot_service.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.chatbot_service import (
    _classify_intent, ChatResponse, get_reply
)


@pytest.mark.asyncio
async def test_intent_classification():
    """Test intent classifier returns valid categories."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="p_and_l")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    intent = await _classify_intent(mock_client, "Generate P&L report")
    assert intent == "p_and_l"


@pytest.mark.asyncio
async def test_intent_defaults_to_general():
    """Test unknown intent defaults to general."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="something_random")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    intent = await _classify_intent(mock_client, "Hello!")
    assert intent == "general"


@pytest.mark.asyncio
async def test_chat_response_always_has_reply():
    """Verify ChatResponse always includes reply field."""
    r = ChatResponse(reply="test")
    assert r.reply == "test"
    assert r.file_id is None

    r2 = ChatResponse(reply="P&L ready", file_id="f123", filename="pnl.xlsx")
    assert r2.reply == "P&L ready"
    assert r2.file_id == "f123"


@pytest.mark.asyncio
async def test_missing_api_key_returns_config_message():
    """Test that missing API key returns a clear message."""
    with patch("app.services.chatbot_service.get_settings") as mock:
        mock.return_value.CLAUDE_API_KEY = ""
        result = await get_reply("user1", "hello")
        assert "API key not configured" in result.reply
```

### 2. Data Loader Tests

```python
# tests/test_data_loader.py

import pytest
from app.services.data_loader import DataLoader


def test_financial_data_uses_correct_columns():
    """Verify DataLoader references actual column names."""
    loader = DataLoader()
    data = loader.load_financial_data()

    # Must reference actual columns, not assumed ones
    assert "Total_INR" not in data or "Total Revenue" in data  # aggregated
    assert "Order_Date" not in data or "Date Range" in data    # summarized


def test_inventory_data_loads():
    """Verify inventory data loads without KeyError."""
    loader = DataLoader()
    data = loader.load_inventory_data()
    assert "Material_Name" in data
    assert "Current_Stock" in data


def test_cache_ttl():
    """Verify cache expires after TTL."""
    loader = DataLoader()
    loader._set_cache("test", "value")
    assert loader._is_cache_valid("test") is True

    # Manually expire
    loader._cache_timestamps["test"] = 0
    assert loader._is_cache_valid("test") is False
```

### 3. Integration Tests

```python
# tests/integration/test_chatbot_api.py

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_message_endpoint_returns_reply(client: AsyncClient, admin_cookies):
    """Test that /message always returns reply field."""
    response = await client.post(
        "/api/v1/chatbot/message",
        json={"message": "How do I manage inventory?"},
        cookies=admin_cookies,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "reply" in data
    assert isinstance(data["reply"], str)
    assert len(data["reply"]) > 0


@pytest.mark.asyncio
async def test_pnl_query_returns_file_metadata(client: AsyncClient, admin_cookies):
    """Test P&L query includes file metadata."""
    response = await client.post(
        "/api/v1/chatbot/message",
        json={"message": "Generate P&L report"},
        cookies=admin_cookies,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "reply" in data  # Always present

    # File fields are optional (may fallback to text)
    if "file_id" in data:
        assert "filename" in data
        assert "download_url" in data
        assert data["download_url"].startswith("/api/v1/chatbot/download/")


@pytest.mark.asyncio
async def test_non_admin_rejected(client: AsyncClient, staff_cookies):
    """Test non-admin users get 403."""
    response = await client.post(
        "/api/v1/chatbot/message",
        json={"message": "Hello"},
        cookies=staff_cookies,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_download_requires_auth(client: AsyncClient):
    """Test download endpoint requires authentication."""
    response = await client.get("/api/v1/chatbot/download/fake_id")
    assert response.status_code == 401
```

### 4. Response Contract Tests

```python
# tests/test_response_contract.py

def test_response_backward_compatible():
    """
    Verify the new response format is backward-compatible.
    Frontend reads: response.data.data?.reply
    This must always work.
    """
    # Text-only response (inventory, demand, general)
    text_response = {
        "success": True,
        "data": {"reply": "Chicken stock is at 45kg."},
        "message": "OK",
    }
    assert text_response["data"]["reply"] == "Chicken stock is at 45kg."
    assert text_response["data"].get("file_id") is None  # Optional, absent

    # File response (P&L)
    file_response = {
        "success": True,
        "data": {
            "reply": "P&L report generated.",
            "file_id": "file_123",
            "filename": "pnl.xlsx",
            "download_url": "/api/v1/chatbot/download/file_123",
        },
        "message": "OK",
    }
    assert file_response["data"]["reply"] == "P&L report generated."
    assert file_response["data"]["file_id"] == "file_123"
```

---

## Deployment Plan

### Phase 1: Backend Implementation (Week 1)

**Day 1-2: Dependencies & Core**
- [ ] Upgrade `anthropic` in requirements.txt to `>=0.75.0`
- [ ] Add `pandas>=2.0.0` and `openpyxl>=3.1.0` to requirements.txt
- [ ] Implement `DataLoader` with TTL cache
- [ ] Verify all column names match actual data schema
- [ ] Unit tests for DataLoader

**Day 3-4: Service Layer**
- [ ] Convert `chatbot_service.py` to async (`AsyncAnthropic`)
- [ ] Implement intent classifier
- [ ] Implement P&L handler with `pause_turn` loop
- [ ] Implement inventory/demand handlers with prompt caching
- [ ] Preserve multi-turn conversation history across all handlers
- [ ] Add text fallback for P&L failures
- [ ] Unit tests with mocked API calls

**Day 5-7: Route & Integration**
- [ ] Update `chatbot.py` route handler (async, new response shape)
- [ ] Add `/download/{file_id}` endpoint with temp file streaming
- [ ] Ensure response contract preserves `reply` field (backward-compatible)
- [ ] Integration tests
- [ ] Response contract tests

### Phase 2: Frontend Integration (Week 2)

**Day 1-2: Service Layer**
- [ ] Update `chatbot.ts`: return full `ChatbotMessageData` (not just string)
- [ ] Add `downloadFile()` function
- [ ] Ensure `ChatbotPage.tsx` still works with `data.reply` (existing code path)

**Day 3-4: UI Enhancements**
- [ ] Add download button when `file_id` is present in response
- [ ] Add loading spinner for P&L generation (longer wait)
- [ ] Update subtitle text to reflect analytics capabilities

**Day 5-7: Testing**
- [ ] End-to-end testing (message -> download)
- [ ] Test fallback behavior (no file generated)
- [ ] Test multi-turn conversation continuity

### Phase 3: Production Deployment (Week 3)

**Day 1-2: Environment**
- [ ] Add new env vars to `.env` and `.env.example`:
  ```
  DATA_PATH=./lexis_test_data
  CHATBOT_CACHE_TTL=300
  ```
- [ ] Ensure `lexis_test_data/` is included in deployment
- [ ] Verify `anthropic` SDK version in production

**Day 3: Deploy**
- [ ] Deploy backend
- [ ] Deploy frontend
- [ ] Smoke test all four query types

**Day 4-5: Monitor**
- [ ] Track API costs
- [ ] Monitor response latencies
- [ ] Watch for `pause_turn` frequency

---

## Cost Projections

### Usage Assumptions

- 100 queries/day total
  - 10 P&L queries (10%)
  - 35 Inventory queries (35%)
  - 35 Demand/General queries (35%)
  - 20 General queries (20%)

### Daily Cost Breakdown

```
Intent Classification: 100 x $0.001 = $0.10
P&L Queries:            10 x $0.40  = $4.00
Inventory:              35 x $0.03  = $1.05
Demand:                 35 x $0.03  = $1.05
General:                20 x $0.008 = $0.16
-------------------------------------------
Daily Total:                         $6.36
Monthly Total (30 days):           $190.80
Annual Total:                    $2,289.60
```

### Cost Optimization Impact

**Without optimization** (all queries use Sonnet + skills):
- 100 queries x $0.40 = $40/day = $1,200/month

**With optimization** (intent routing + model selection):
- $6.36/day = $190.80/month

**Savings: ~84% cost reduction** (~$1,000/month saved)

---

## Future Enhancements

### Phase 4: Advanced Features (Optional)

1. **Custom Analytics Skill**: Create a custom skill with the restaurant's
   specific P&L template and upload via Skills API.

2. **Multi-Format Reports**: Add PDF (`pdf` skill) and PowerPoint (`pptx` skill)
   for executive dashboards.

3. **Real-Time Data Integration**: Replace static Excel files with live MongoDB
   queries. DataLoader becomes a thin adapter over the existing repository layer.

4. **Conversation Persistence**: Move `_chat_history` from in-memory dict to
   MongoDB collection for cross-session context and server restart resilience.

5. **Streaming Responses**: Use Claude's streaming API to show partial
   responses in real-time while the full answer generates.

6. **Rate Limiting**: Add per-user rate limits for P&L generation to control
   costs (e.g., max 5 P&L reports per hour).

---

## Appendix: Changes from v1.0

| Issue | Severity | Fix in v2.0 |
|-------|----------|-------------|
| SDK version 0.39.0 missing Skills/Files API | Blocker | Upgrade to >=0.75.0 |
| Column names wrong (total_amount vs Total_INR) | Blocker | All references use actual PascalCase names |
| Multi-turn conversation dropped | Blocker | History passed to all handlers |
| pause_turn not handled | Blocker | Retry loop with MAX_PAUSE_TURN_RETRIES=10 |
| Data strategy contradictory (upload vs context) | Blocker | Server-side pre-aggregation, text context |
| orders.xlsx too large for context | Blocker | Monthly aggregation computed in DataLoader |
| Response breaks frontend (reply -> message) | Blocker | Always return `reply` field; file fields additive |
| Sync client blocks event loop | Risk | AsyncAnthropic throughout |
| file_content.stream doesn't exist | Risk | Temp file + write_to_file + streaming |
| pandas/openpyxl not in requirements | Risk | Added to requirements.txt |
| Prompt caching missing beta header | Risk | Uses client.beta.messages.create with caching beta |
| UserRole has no "owner" | Risk | Removed; use existing get_admin_user |
| Cache has no TTL | Minor | TTL-based cache with configurable CHATBOT_CACHE_TTL |
| Circuit breaker not thread-safe | Minor | asyncio.Lock in SkillCircuitBreaker |
| File ID extraction may miss formats | Minor | Multi-pattern extraction function |
| Cost estimates too optimistic | Minor | Revised upward with code execution overhead |
