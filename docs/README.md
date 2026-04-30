# Ahar.AI — Documentation

All project documentation lives here. Organised by purpose, not chronology.

---

## Structure

| Folder | What goes here |
|---|---|
| [**adr/**](adr/) | Architecture Decision Records — *why* we made key technical choices |
| [**architecture/**](architecture/) | System design docs, strategic direction, agent design |
| [**features/**](features/) | How each feature works; pending features tracked here too |
| [**api/**](api/) | API reference docs |
| [**deployment/**](deployment/) | How to run this in production |
| [**data/**](data/) | Data requirements for onboarding restaurants |
| [**guides/**](guides/) | Developer how-to guides |

---

## Decision Records (ADRs)

| ADR | Title | Status |
|---|---|---|
| [ADR-001](adr/ADR-001-antara-item-level-forecasting.md) | AnTeRa Item-Level Sales Forecasting | Accepted |
| [ADR-002](adr/ADR-002-ocr-po-bill-review-workflow.md) | OCR-Driven PO and Bill Review Workflow | Accepted |
| [ADR-003](adr/ADR-003-autonomous-real-time-restaurant-operations.md) | Autonomous Real-Time Restaurant Operations | Accepted |
| [ADR-004](adr/ADR-004-owner-dashboard-unified-design.md) | Owner Dashboard — Unified 3-Zone Design | Accepted |
| [ADR-005](adr/ADR-005-chatbot-analytics-architecture.md) | Chatbot & Analytics Assistant Architecture | Accepted |
| [ADR-006](adr/ADR-006-data-foundation-strategy.md) | Data Foundation Strategy — Real + Synthetic Data | Accepted |
| [ADR-007](adr/ADR-007-inventory-agent-act-layer.md) | Inventory Agent — Act Layer Design (Hyperpure MVP) | Accepted |
| [ADR-008](adr/ADR-008-shopping-list-approval-ux.md) | Shopping List Approval UX — Permanent Panel & Hyperpure Orders | Accepted |

> Run `/update-adr` in Claude Code to create or update ADRs after any significant technical decision.

---

## Architecture

| Doc | What it covers |
|---|---|
| [AI Workflow Transformation Analysis](architecture/AI_WORKFLOW_TRANSFORMATION_ANALYSIS.md) | Strategic direction: autonomous ops platform vs AI wrapper |
| [Autonomous Agent Implementation Example](architecture/AUTONOMOUS_AGENT_IMPLEMENTATION_EXAMPLE.md) | Concrete code showing wrapper → autonomous transformation |
| [Autonomous Roadmap](architecture/QUICK_START_ROADMAP.md) | 8-week plan toward first autonomous workflow in production |
| [Chatbot Analytics Design v2](architecture/chatbot-analytics-skills-design.md) | Skill-enabled Claude analytics assistant system design |
| [Chatbot Analytics Design v3](architecture/chatbot-analytics-v3-cost-optimized.md) | Cost-optimised chatbot design (₹20K/year target) |

---

## Features

**Implemented:**

| Doc | Feature |
|---|---|
| [Approval Dashboard](features/APPROVAL_DASHBOARD_FRONTEND.md) | Shopping list approval flow (frontend) |
| [Home Page Role-Based Tabs](features/home-page-role-based-tabs.md) | Staff role → tab visibility logic |
| [Inventory Chatbot](features/inventory-chatbot-implementation.md) | AI-powered inventory management |
| [Menu Management](features/menu-management-implementation.md) | Menu CRUD and upload |
| [P&L Chatbot](features/pnl-chatbot-implementation.md) | Profit & loss analysis via chatbot |
| [Tables Management](features/tables-management-implementation.md) | Table layout and status management |
| [Waiter & Kitchen Tabs](features/waiter-kitchen-tabs-implementation.md) | Order flow: waiter → kitchen (KOT) |

**Pending:**

| Doc | Feature |
|---|---|
| [Multi-Tenancy Data Isolation](features/multi-tenancy-data-isolation.md) | Per-restaurant data isolation (Priority: High) |

---

## API Reference

| Doc | What it covers |
|---|---|
| [Shopping List API](api/SHOPPING_LIST_API.md) | Inventory agent shopping list endpoints |

---

## Deployment

| Doc | What it covers |
|---|---|
| [Production Setup](deployment/PRODUCTION_SETUP.md) | Full production deployment guide |
| [Quick Reference](deployment/QUICK_REFERENCE.md) | Commands cheat sheet for running services |

---

## Data Requirements

| Doc | What it covers |
|---|---|
| [For Restaurants (detailed)](data/DATA_REQUIREMENTS_FOR_RESTAURANTS.md) | Full data spec for onboarding a new restaurant |
| [For Restaurants (simple)](data/DATA_REQUIREMENTS_SIMPLE.md) | Plain-English version for non-technical stakeholders |

---

## Developer Guides

| Doc | What it covers |
|---|---|
| [Quick Start](guides/QUICK_START.md) | Getting the system running locally |
| [Forecast Data Guide](guides/FORECAST_DATA_GUIDE.md) | How to access demand predictions via API and MongoDB |
| [Item-Level Forecasting](guides/ITEM_LEVEL_FORECASTING.md) | Item-level vs restaurant-level forecasting explained |

---

## Rules for this folder

- **Never add a doc here unless it reflects the current or intended state of the system.** Historical summaries, week reports, and 100%-complete progress trackers belong in git history, not here.
- **Completed feature progress docs go in `features/` as implementation references, not trackers.**
- **Pending features and open architectural questions go in `features/` until they have an ADR.**
- **All technical decisions must have an ADR entry.** Run `/update-adr` after any significant decision.
- Filenames: UPPERCASE for guides/API/deployment docs, kebab-case for feature and architecture docs.
