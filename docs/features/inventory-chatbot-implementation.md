# Inventory Chatbot Feature — Implementation Plan

## Overview

Add inventory query and limited update capabilities to the existing chatbot using **Claude native tool/function calling**. The chatbot will be able to answer natural language questions about inventory and allow updates to three operational fields (`current_stock`, `unit_cost_inr`, `reorder_level`).

**No add, no delete. Read + limited update only.**

---

## Architecture Decision

The existing P&L feature uses the **Anthropic Skills API** (container + code execution) because it needs to run Python scripts server-side. Inventory operations don't need that — they just need to call our existing MongoDB service layer.

**Claude native tool calling** is the correct fit:
1. Define tool schemas for Claude
2. Claude picks which tool to call based on user intent
3. Backend executes the tool against `InventoryService` / `InventoryRepository`
4. Result is fed back to Claude
5. Claude generates a natural language response

This avoids container overhead entirely — significantly cheaper than the Skills API.

---

## Files to Change

| File | Type | Change |
|---|---|---|
| `backend/app/repositories/inventory_repository.py` | Backend | Add `search_by_name()` |
| `backend/app/services/inventory_service.py` | Backend | Add `search_items_by_name()` |
| `backend/app/services/chatbot_service.py` | Backend | Add intent detection, tool definitions, tool executor, inventory handler, update routing |
| `frontend/src/pages/ChatbotPage.tsx` | Frontend | Add inventory suggestion pills |

---

## Step 1 — `inventory_repository.py`

Add a new method for case-insensitive substring search on `material_name`:

```python
async def search_by_name(self, query: str) -> List[dict]:
    """Search inventory items by name substring (case-insensitive)"""
    collection = self._get_collection()
    cursor = collection.find(
        {"material_name": {"$regex": query, "$options": "i"}}
    ).sort("material_id", 1)
    return await cursor.to_list(length=None)
```

---

## Step 2 — `inventory_service.py`

Add a service-layer wrapper:

```python
async def search_items_by_name(self, query: str) -> List[InventoryItemResponse]:
    """Search inventory items by name substring"""
    items = await inventory_repository.search_by_name(query)
    return [self._format_item_response(item) for item in items]
```

---

## Step 3 — `chatbot_service.py`

This is the core of the feature. Four additions:

### 3a. Intent Detection — `_is_inventory_intent()`

Local keyword matching (zero LLM cost), similar to the existing `_is_pnl_intent()`.

```python
def _is_inventory_intent(self, message: str) -> bool:
    msg_lower = message.lower()
    keywords = [
        'inventory', 'stock', 'ingredient', 'item', 'material',
        'low stock', 'reorder', 'restock', 'category', 'supplier',
        'perishable', 'shelf life', 'out of stock',
        # common food category words
        'bread', 'dairy', 'meat', 'vegetable', 'spice', 'grain',
        'protein', 'sauce', 'oil', 'flour', 'rice',
        # action words
        'update stock', 'update cost', 'update reorder',
        'how much', 'how many', 'do we have',
    ]
    return any(kw in msg_lower for kw in keywords)
```

If the message is ambiguous (not matched locally), Claude still handles it with tools available — Claude itself decides whether to call an inventory tool or give a general answer.

### 3b. Tool Definitions — `INVENTORY_TOOLS`

Four tools passed to Claude in the `tools` parameter of `messages.create()`:

```python
INVENTORY_TOOLS = [
    {
        "name": "search_inventory",
        "description": (
            "Search inventory items by name keyword and/or category. "
            "Use when the user asks about specific ingredients, lists items in a category, "
            "or asks what items are available. "
            "Either query or category can be omitted but at least one must be provided."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Substring to search in item name (e.g. 'bread', 'flour')"
                },
                "category": {
                    "type": "string",
                    "description": "Exact category filter (e.g. 'Bakery', 'Dairy', 'Meat')"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_low_stock_items",
        "description": (
            "Get all inventory items where current stock is at or below the reorder level. "
            "Use when the user asks about low stock, what needs restocking, or reorder alerts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_inventory_item",
        "description": (
            "Get full details of a single inventory item by its name or material ID. "
            "Use when the user asks about a specific item's stock, cost, supplier, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name_or_id": {
                    "type": "string",
                    "description": "Item name (partial match) or material ID (e.g. 'RM001')"
                }
            },
            "required": ["name_or_id"]
        }
    },
    {
        "name": "update_inventory_field",
        "description": (
            "Update one of three allowed fields on an inventory item: "
            "current_stock, unit_cost_inr, or reorder_level. "
            "Use when the user explicitly asks to update/change/set one of these values. "
            "unit_cost_inr is stored in paise (multiply INR by 100)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name_or_id": {
                    "type": "string",
                    "description": "Item name or material ID to identify the item"
                },
                "field": {
                    "type": "string",
                    "enum": ["current_stock", "unit_cost_inr", "reorder_level"],
                    "description": "The field to update"
                },
                "value": {
                    "type": "number",
                    "description": "New value for the field"
                }
            },
            "required": ["name_or_id", "field", "value"]
        }
    }
]
```

### 3c. Tool Executor — `_execute_inventory_tool()`

Dispatches tool calls to the service layer and returns serialisable results:

```python
async def _execute_inventory_tool(self, tool_name: str, tool_input: dict) -> str:
    """Execute an inventory tool call and return result as a JSON string"""
    import json

    try:
        if tool_name == "search_inventory":
            query    = tool_input.get("query", "")
            category = tool_input.get("category")

            if query:
                items = await inventory_service.search_items_by_name(query)
            else:
                items, _ = await inventory_service.get_all_items(limit=200, category=category)

            if category and query:
                # Intersect: filter name results by category
                items = [i for i in items if i.category.lower() == category.lower()]

            return json.dumps([_item_to_dict(i) for i in items])

        elif tool_name == "get_low_stock_items":
            items = await inventory_service.get_low_stock_items()
            return json.dumps([_item_to_dict(i) for i in items])

        elif tool_name == "get_inventory_item":
            name_or_id = tool_input["name_or_id"]
            # Try material_id first, then name search
            item = await inventory_repository.get_by_material_id(name_or_id)
            if not item:
                results = await inventory_repository.search_by_name(name_or_id)
                item = results[0] if results else None
            if not item:
                return json.dumps({"error": f"No item found matching '{name_or_id}'"})
            item["_id"] = str(item["_id"])
            return json.dumps(item, default=str)

        elif tool_name == "update_inventory_field":
            ALLOWED_FIELDS = {"current_stock", "unit_cost_inr", "reorder_level"}
            field = tool_input["field"]
            value = tool_input["value"]
            name_or_id = tool_input["name_or_id"]

            if field not in ALLOWED_FIELDS:
                return json.dumps({"error": f"Field '{field}' is not updatable via chatbot"})

            # Resolve item
            item = await inventory_repository.get_by_material_id(name_or_id)
            if not item:
                results = await inventory_repository.search_by_name(name_or_id)
                item = results[0] if results else None
            if not item:
                return json.dumps({"error": f"No item found matching '{name_or_id}'"})

            item_id = str(item["_id"])
            update_data = InventoryItemUpdate(**{field: int(value)})
            updated = await inventory_service.update_item(item_id, update_data)
            updated_dict = _item_to_dict(updated)
            return json.dumps({"success": True, "updated": updated_dict})

    except Exception as e:
        logger.error(f"Inventory tool '{tool_name}' failed: {e}", exc_info=True)
        return json.dumps({"error": str(e)})
```

Helper at module level:
```python
def _item_to_dict(item: InventoryItemResponse) -> dict:
    """Convert InventoryItemResponse to a plain dict safe for JSON serialisation"""
    return {
        "material_id":    item.material_id,
        "material_name":  item.material_name,
        "category":       item.category,
        "unit":           item.unit,
        "current_stock":  item.current_stock,
        "reorder_level":  item.reorder_level,
        "reorder_qty":    item.reorder_qty,
        "max_stock":      item.max_stock,
        "unit_cost_inr":  item.unit_cost_inr,   # in paise
        "is_perishable":  item.is_perishable,
        "supplier_id":    item.supplier_id,
    }
```

### 3d. Inventory Handler — `_handle_inventory_message()`

Sends to Claude with tools, processes tool_use blocks in a loop (Claude may call multiple tools in one turn), then returns the final text reply:

```python
async def _handle_inventory_message(self, message: str, user_id: str) -> dict:
    """Handle inventory-related messages using Claude tool calling"""
    if not self.client:
        return {"reply": "API key not configured.", "success": False}

    history = self._get_history(user_id)

    INVENTORY_SYSTEM_PROMPT = (
        "You are an inventory assistant for a restaurant. "
        "Answer questions about the restaurant's raw material inventory using the provided tools. "
        "Be concise. Format lists clearly. "
        "For monetary values, convert paise to INR (divide by 100) when displaying to the user. "
        "Only update fields when the user explicitly asks you to."
    )

    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in self._trim_history(history)
    ]

    try:
        response = self.client.messages.create(
            model=self.settings.CHATBOT_MODEL,
            max_tokens=1024,
            system=INVENTORY_SYSTEM_PROMPT,
            tools=INVENTORY_TOOLS,
            messages=api_messages,
        )

        # Agentic loop: keep processing until Claude stops calling tools
        while response.stop_reason == "tool_use":
            tool_results = []
            assistant_content = response.content

            for block in response.content:
                if block.type == "tool_use":
                    result_str = await self._execute_inventory_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            # Append assistant turn + tool results and call Claude again
            api_messages.append({"role": "assistant", "content": assistant_content})
            api_messages.append({"role": "user",      "content": tool_results})

            response = self.client.messages.create(
                model=self.settings.CHATBOT_MODEL,
                max_tokens=1024,
                system=INVENTORY_SYSTEM_PROMPT,
                tools=INVENTORY_TOOLS,
                messages=api_messages,
            )

        # Extract final text reply
        reply_text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        ).strip() or "I couldn't generate a reply."

        return {
            "reply": reply_text,
            "success": True,
            "usage": {
                "input_tokens":  response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        }

    except Exception as e:
        logger.error(f"Inventory message handling failed: {e}", exc_info=True)
        return {"reply": "Sorry, I couldn't process that inventory query.", "success": False}
```

### 3e. Update `process_message()` Routing

Add inventory routing before the existing P&L check:

```python
async def process_message(self, user_id: str, message: str) -> dict:
    history = self._get_history(user_id)
    history.append({"role": "user", "content": message.strip()})

    # Route 1: Inventory intent (local keywords OR ambiguous → Claude decides via tools)
    if self._is_inventory_intent(message):
        result = await self._handle_inventory_message(message, user_id)
        history.append({"role": "assistant", "content": result["reply"]})
        _chat_history[user_id] = self._trim_history(history)
        return result

    # Route 2: P&L intent (existing flow — unchanged)
    if self._is_pnl_intent(message):
        ...  # existing code, no changes

    # Route 3: General chat (existing flow — unchanged)
    result = await self._general_chat(message, user_id)
    ...
```

> **Note on ambiguous messages**: If a message isn't caught by `_is_inventory_intent()` but the user asks something inventory-adjacent (e.g. "what bread should I order?"), it falls through to `_general_chat` which has no tools — Claude answers in general terms. If this proves too limiting, the threshold on `_is_inventory_intent` can be widened.

---

## Step 4 — `ChatbotPage.tsx` (Frontend)

Update the `SUGGESTION_PILLS` constant to add three inventory-focused pills. Replace the existing `'Check Inventory'` pill (which currently exists) with more specific ones:

```typescript
const SUGGESTION_PILLS = [
  { label: 'Generate P&L Report',      prompt: 'Generate a P&L report for last month' },
  { label: 'Analyse Sales Trends',     prompt: 'Analyse my sales trends for the past week' },
  { label: 'Low Stock Alerts',         prompt: 'Which items are low in stock and need restocking?' },
  { label: 'Browse Ingredients',       prompt: 'List all ingredients grouped by category' },
  { label: 'Operational Tips',         prompt: 'Give me tips to improve my restaurant operational efficiency' },
];
```

The "Check Inventory" pill already exists and maps to a good prompt — it can be kept or replaced by the two more specific ones above.

---

## Imports to Add

In `chatbot_service.py`, add to the existing imports:
```python
from app.services.inventory_service import inventory_service
from app.repositories.inventory_repository import inventory_repository
from app.models.inventory import InventoryItemUpdate, InventoryItemResponse
```

---

## What Is NOT Changed

- `inventory.py` (routes) — no changes, REST endpoints remain independent
- `chatbot.py` (route) — no changes to the HTTP handler
- `InventoryRepository.get_all()`, `get_low_stock_items()` etc. — used as-is
- The P&L Skills API flow — completely untouched
- Auth system — chatbot already requires authentication; the service layer is called directly (no HTTP re-auth needed)

---

## Data Notes

- `unit_cost_inr` is stored in **paise** (e.g. ₹60 = `6000`). The system prompt instructs Claude to display it in INR (divide by 100).
- `is_perishable` is stored as `"Yes"` / `"No"` string, not a boolean.
- `current_stock`, `reorder_level` values are integers (no decimals).
- When Claude calls `update_inventory_field` with `unit_cost_inr`, the value from the user (e.g. `"60"` for ₹60) must be multiplied by 100 before saving — this is handled in `_execute_inventory_tool` via `int(value)` after Claude is instructed on the paise convention via the tool description.

> **Clarification needed at implementation time**: The system prompt should tell Claude to convert INR → paise when calling `update_inventory_field` for `unit_cost_inr`. The tool description already notes this. Verify during testing.

---

## Testing Checklist

| Query | Expected Tool | Expected Outcome |
|---|---|---|
| "Which items are low in stock?" | `get_low_stock_items` | List of items below reorder level |
| "List all the breads I have" | `search_inventory(query="bread")` | Items with "bread" in name |
| "Show me all dairy items" | `search_inventory(category="Dairy")` | Items in Dairy category |
| "How much flour do we have?" | `get_inventory_item("flour")` | Single item details |
| "Update flour stock to 100" | `update_inventory_field("flour", "current_stock", 100)` | Updated successfully |
| "What's the cost of ciabatta?" | `get_inventory_item("ciabatta")` | Item details with cost in INR |
| "Generate P&L for last month" | _(falls through to P&L flow)_ | P&L report generated |
| "What are tips to reduce waste?" | _(falls through to general chat)_ | General advice, no tools |
