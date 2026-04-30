 # CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ahar.AI is an AI-powered restaurant management platform for restaurant owners in India. Key entities: raw materials, recipes, menu items, orders, inventory BOM, delivery orders, purchase orders (POs), bills. The system includes demand forecasting (Prophet/XGBoost/SARIMA ensemble), autonomous agents (event bus, revenue monitor, expiry tracker, smart approval thresholds), and a Command Center dashboard for owners.

**Stack:** Python/FastAPI backend + React/TypeScript frontend + MongoDB (Motor async driver).

## Agent Usage Rules

**ALWAYS use the `project-structure-explorer` agent for any file reading, code exploration, or codebase searches.**
Never use the Read, Grep, or Glob tools directly. Always delegate to the agent.

## Project Directory Map

Use this map to navigate directly to the right file — do not spend tool calls re-exploring known structure.

```
backend/app/
  api/v1/          → approvals.py, auth.py, chatbot.py, dashboard.py, documents.py,
                     financial.py, forecast.py, forecast_validation.py, health.py,
                     insights.py, inventory.py, menu.py, notifications.py, orders.py,
                     settings.py, tables.py
  core/            → config.py, database.py, security.py, dependencies.py
  models/          → user.py, order.py, inventory.py, menu_item.py, document.py,
                     delivery_order.py, fixed_asset.py, notification.py, packaging_bom.py,
                     packaging_material.py, restaurant_settings.py, insights.py, common.py
  repositories/    → user, session, order, inventory, menu, table, document,
                     delivery_order, shopping_list, notification, ocr, fixed_asset,
                     packaging_bom, packaging_material, bill, purchase_order, recipe,
                     restaurant_settings, strategic_analytics (one file each)
  services/        → auth, order, inventory, shopping_list, ocr, document_processor,
                     chatbot, dashboard, demand_forecaster, forecast_validator,
                     feature_engineering, analytics_aggregator, insights, strategic_insights,
                     profit_analysis, item_matching, settings, notification, expiry_monitor,
                     reorder_calculator, revenue_monitor, event_bus, orchestrator
    agents/        → base_agent.py, inventory_agent.py, financial_agent.py, strategic_analysis_agent.py
    ml/            → ensemble_predictor.py, feature_library.py, training_pipeline.py,
                     base_forecaster.py, hybrid_abc_forecaster.py, prophet_enhanced.py,
                     tier_based_forecaster.py, time_series_utils.py, model_registry.py,
                     hyperparameter_tuner.py, llm_feature_engineer.py, encoders.py,
                     holiday_calendar.py
                     models/ → prophet_forecaster.py, sarima_forecaster.py, xgboost_forecaster.py
    data_quality/  → confidence_calibrator.py, data_tier_classifier.py, outlier_detector.py
    external_data/ → events_service.py, news_service.py, weather_service.py, pytrends_service.py
  utils/           → response.py  ← ALL response helpers (success_response, error_response, paginated_response)
  jobs/            → ml_scheduled_jobs.py
  main.py          → FastAPI entry point

frontend/src/
  pages/           → HomePage, ChatbotPage, ApprovalsPage, FinancialDashboard, InsightsPage,
                     MenuPage, SettingsPage, SignInPage, SignUpPage, AnalyticsPage, ReportsPage,
                     KitchenPage, TablesPage, StaffPage, WaiterPage, LandingPage, AboutPage, PricingPage
                     screens/ → CommandCenterScreen, IntelligenceHubScreen, InventoryScreen,
                                OperationsFloorScreen, SettingsScreen
  components/      → AppNavBar, OwnerDashboard, InventoryTab, FinancialTab, NotificationBell,
                     ProtectedRoute, PublicRoute, TabNavigation, SubTabNavigation, OrderCard,
                     MenuItemCard, TableCard, ConfirmModal
                     dashboard/ → ActionQueue, PulseStrip, StockHealthPanel, PnLSnapshotPanel,
                                  RevenuePatternPanel, MenuPerformancePanel, CatalogueTab,
                                  KitchenTab, CustomerTab, StaffTab
                                  ActionCards/ → ExpirySpecialCard, LowStockCard, POApprovalCard, RevenueAnomalyCard
                     inventory/ → BillsTab, DocumentUploadModal, DocumentsHistoryTab,
                                  OCRReviewStep, PurchaseOrdersTab
  services/        → api.ts (axios base), auth, inventory, menu, orders, approvals, chatbot,
                     documents, financial, notifications, ownerDashboard, settings, tables,
                     staff, agents, insightsService, strategicInsightsService
  types/           → api.ts, auth.ts, inventory.ts, menu.ts, orders.ts, approvals.ts,
                     settings.ts, tables.ts, navigation.ts
  contexts/        → AuthContext.tsx
  hooks/           → useFileUpload.ts
  utils/           → currency.ts, inventoryUnits.ts

docs/
  adr/             → ADR-001 (item-level forecasting) through ADR-007 (inventory agent act layer)
  architecture/    → owner dashboard design, autonomous agent workflows, chatbot analytics design
  features/        → per-feature implementation docs (approvals, inventory, menu, tables, chatbot…)
  api/             → SHOPPING_LIST_API.md
  guides/          → FORECAST_DATA_GUIDE.md, ITEM_LEVEL_FORECASTING.md, QUICK_START.md

.claude/
  commands/        → groom.md, update-adr.md, spinup.md
  agents/          → ux-design-reviewer.md
```

## Development Commands

### Docker (Recommended)
```bash
# Start all services (MongoDB, Backend, Frontend)
docker compose up -d

# View logs
docker compose logs -f [service_name]

# Rebuild after changes
docker compose up -d --build

# Stop all services
docker compose down
```

### Backend (Manual)
```bash
cd backend

# Setup
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest
```

### Frontend (Manual)
```bash
cd frontend

# Setup
npm install

# Development
npm run dev          # Start dev server on port 3000
npm run build        # Build for production
npm run lint         # Run ESLint
npm run preview      # Preview production build
```

## Architecture

### Backend Structure (FastAPI + MongoDB)

**Three-layer architecture** - strictly separate concerns:

1. **Routes** (`app/api/v1/`) - HTTP handling, request/response serialization
2. **Services** (`app/services/`) - Business logic, orchestration
3. **Repositories** (`app/repositories/`) - Database operations only

Key patterns:
- **Database**: Motor async MongoDB client singleton in `app/core/database.py`
- **Configuration**: Pydantic Settings in `app/core/config.py` (loads from .env)
- **Response formatting**: Always use helpers from `app/utils/response.py`:
  - `success_response(data, message)` for successful responses
  - `error_response(code, message, details)` for errors
  - `paginated_response(data, page, limit, total)` for lists
- **API versioning**: All routes under `/api/v1/` prefix
- **Auth**: Session-based (HTTP-only cookies), managed by `auth_service.py`
- **Models**: Pydantic models in `app/models/` for validation and serialization

**Adding new endpoints:**
1. Create route handler in `app/api/v1/{resource}.py`
2. Create service in `app/services/{resource}_service.py` for business logic
3. Create repository in `app/repositories/{resource}_repository.py` for DB access
4. Register router in `app/api/v1/__init__.py`
5. Use response helpers - never return raw dicts

### Frontend Structure (React + TypeScript)

**Directory organization:**
- `pages/` - Route-level components (one per URL)
- `components/` - Reusable UI components
- `services/` - API client functions (one file per resource)
- `contexts/` - React Context providers (AuthContext provides user state)
- `types/` - TypeScript interfaces
- `hooks/` - Custom React hooks
- `utils/` - Helper functions

**Routing:**
- Public routes: `/`, `/features`, `/about`, `/pricing`
- Auth routes: `/signin`, `/signup` (redirect to `/home` if authenticated)
- Protected routes: `/home` (requires authentication, redirects to `/signin` if not)
- Use `<ProtectedRoute>` wrapper for authenticated pages
- Use `<PublicRoute>` wrapper for public pages

**Authentication:**
- `AuthContext` provides `user`, `login()`, `logout()`, `register()`
- Session token stored in HTTP-only cookie (managed by backend)
- Check `user` from context to determine auth state

**API calls:**
- All API services in `src/services/` use axios client from `services/api.ts`
- API client automatically includes credentials (cookies)
- Base URL from `VITE_API_URL` env var (defaults to `http://localhost:8000`)

## Data Standards

### API Response Format
All endpoints return consistent structure (defined in `backend/app/utils/response.py`):

**Success:**
```json
{
  "success": true,
  "data": {},
  "message": "Success message",
  "timestamp": "2026-01-19T10:00:00Z"
}
```

**Error:**
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "User-friendly message",
    "details": {}
  },
  "timestamp": "2026-01-19T10:00:00Z"
}
```

**Paginated:**
```json
{
  "success": true,
  "data": [],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "total_pages": 5
  },
  "timestamp": "2026-01-19T10:00:00Z"
}
```

### Other Data Conventions
- **Timestamps**: Store in UTC, ISO 8601 format. Field names: `created_at`, `updated_at`
- **Monetary values**: Store as integers in smallest currency unit (paise/cents). Field suffix: `_amount`
- **Database IDs**: MongoDB ObjectId as `_id`
- **Phone numbers**: Store with country code in E.164 format

## Data & Database

- **Always query MongoDB directly** for any data checks — never use CSV files, conversation context, or cached files as a proxy for live data.
- **Collection names** (use exactly, don't guess — verify in `backend/app/repositories/` if unsure):
  `raw_materials`, `recipes`, `menu_items`, `orders`, `inventory_logs`, `delivery_orders`,
  `purchase_orders`, `bills`, `sessions`, `users`, `restaurant_settings`, `notifications`
- When fixing data issues, update **both** the source file (CSV/script) AND MongoDB — not just one.
- Local DB access: `mongosh ahar_pos` | Motor client singleton: `backend/app/core/database.py`
- Never assume collection names — check the relevant repository file first.

## File Operations

- **Always write output files under the project root** (`/Users/pandiarajan/Ahar.AI/`) unless told otherwise.
- `kanban.json` and `BOARD.md` → project root (or `.claude/` if Claude-specific).
- Documentation → `docs/<subfolder>/` with UPPERCASE filename (e.g. `docs/features/MY_FEATURE.md`).
- Never create `.md` files in the project root except `CLAUDE.md` and `README.md`.

## Documentation Organization

**IMPORTANT: All .md/.MD files MUST be placed in the `docs/` directory, never in the project root.**

Structure:
- `docs/api/` - API specifications, endpoint documentation
- `docs/data/` - Data requirements, schemas, migration guides
- `docs/features/` - Feature specifications and implementation details
- `docs/guides/` - User guides, how-tos, quick starts
- `docs/summaries/` - Implementation summaries, sprint/week reports
- `docs/architecture/` - System design, architectural decision records
- `docs/deployment/` - Deployment guides, infrastructure docs

Rules:
- Never create .md files in the project root (except CLAUDE.md and README.md)
- When creating documentation, place it in the most appropriate docs/ subfolder
- If no suitable folder exists, create a new one following the naming pattern above
- Use UPPERCASE filenames for documentation (e.g., `API_GUIDE.md`)
- Keep folder names lowercase and descriptive

## Naming Conventions

- **API endpoints**: `/api/v1/{resource}/{action}` (plural nouns, kebab-case)
- **MongoDB collections**: plural snake_case (e.g., `menu_items`, `orders`)
- **Python**: snake_case for functions/variables, PascalCase for classes
- **TypeScript**: camelCase for functions/variables, PascalCase for components/types
- **React components**: PascalCase files (e.g., `HomePage.tsx`)
- **Constants**: UPPERCASE_WITH_UNDERSCORES in both languages
- **Environment variables**: UPPERCASE_WITH_UNDERSCORES

## Role-Based Access Control

The system has different user roles (defined in `backend/app/models/user.py`):
- Staff roles determine which features are accessible in `/home` page
- HomePage uses role-based tabs to show different views

## Environment Variables

### Backend (.env)
- `MONGODB_URI` - MongoDB connection string (default: `mongodb://localhost:27017`)
- `DB_NAME` - Database name (default: `ahar_pos`)
- `FRONTEND_URL` - Frontend URL for CORS (default: `http://localhost:3000`)
- `API_PORT` - Backend port (default: `8000`)
- `DEBUG` - Enable debug mode (default: `false`)
- `SESSION_EXPIRE_HOURS` - Session expiration time (default: `24`)

### Frontend (.env)
- `VITE_API_URL` - Backend API URL (default: `http://localhost:8000`)

## Code Quality Requirements

### Python
- Follow PEP 8, max line length 100
- Use type hints for function parameters and returns
- Use async/await for I/O operations
- Add docstrings to public functions and classes

### TypeScript
- Enable strict mode
- Define interfaces for all data structures
- Avoid `any` type

### General
- Keep functions under 50 lines
- Max nesting depth: 3-4 levels
- Use early returns to reduce nesting
- Comment "why" not "what"

## Git Commit Format
```
<type>: <description>

Types: feat, fix, refactor, docs, style, test, chore
Example: feat: add user authentication endpoint
```

## Testing

Backend uses pytest with async support:
```bash
cd backend
pytest                    # Run all tests
pytest tests/test_*.py    # Run specific test file
pytest -v                 # Verbose output
```

## Access Points

When services are running:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs
- API Docs (ReDoc): http://localhost:8000/redoc
- MongoDB: localhost:27017
