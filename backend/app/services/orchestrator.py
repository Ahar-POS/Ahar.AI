"""
Orchestrator Service - Central Coordinator for Autonomous Agents

Manages:
- Agent scheduling (APScheduler for cron-like jobs)
- Event routing (EventBus subscriptions)
- Decision logging (MongoDB persistence)
- Approval processing (auto-execute vs manual approval)

Architecture:
    Orchestrator
    ├── Scheduler (APScheduler)
    ├── Event Bus (pub/sub)
    ├── Agent Registry
    └── Decision Logger
"""

import logging
from datetime import datetime
from app.utils.timezone import now_ist
from typing import Dict, Any, List, Optional
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.core.database import get_database
from app.services.event_bus import get_event_bus
from app.services.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)


class OrchestratorService:
    """
    Central coordinator for all autonomous operations

    Responsibilities:
    1. Schedule agents to run at specific times
    2. Route events to appropriate handlers
    3. Log all agent decisions to MongoDB
    4. Process approval workflows
    """

    def __init__(self):
        """Initialize orchestrator components"""
        self.scheduler = AsyncIOScheduler()
        self.event_bus = get_event_bus()
        self.agents: Dict[str, Any] = {}
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize orchestrator and register agents

        Called during FastAPI startup
        """
        if self._initialized:
            logger.warning("Orchestrator already initialized")
            return

        logger.info("Initializing Orchestrator Service...")

        # Get database connection
        self.db = get_database()

        # Create MongoDB collections if needed
        await self._ensure_collections()

        # Register agents (will be populated later)
        await self._register_agents()

        # Set up event subscriptions
        await self._subscribe_to_events()

        # Register scheduled jobs
        self._register_schedules()

        # Start scheduler
        self.scheduler.start()

        self._initialized = True
        logger.info("Orchestrator Service initialized successfully")

    async def shutdown(self) -> None:
        """
        Shutdown orchestrator gracefully

        Called during FastAPI shutdown
        """
        logger.info("Shutting down Orchestrator Service...")

        # Stop scheduler
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)

        self._initialized = False
        logger.info("Orchestrator Service shut down")

    async def _ensure_collections(self) -> None:
        """
        Create MongoDB collections and indexes if they don't exist
        """
        # Create agent_decisions collection with indexes
        await self.db.agent_decisions.create_index("agent_name")
        await self.db.agent_decisions.create_index("timestamp")
        await self.db.agent_decisions.create_index("status")
        await self.db.agent_decisions.create_index([("agent_name", 1), ("timestamp", -1)])

        # Create demand_forecasts collection with indexes
        await self.db.demand_forecasts.create_index("material_id")
        await self.db.demand_forecasts.create_index("forecast_date")
        await self.db.demand_forecasts.create_index(
            "generated_at",
            expireAfterSeconds=86400  # TTL: 24 hours
        )

        # Create recipe_bom collection with indexes (one recipe per menu item)
        # Drop and recreate if a non-unique index with the same name already exists
        try:
            await self.db.recipe_bom.create_index("menu_item_id", unique=True)
        except Exception:
            await self.db.recipe_bom.drop_index("menu_item_id_1")
            await self.db.recipe_bom.create_index("menu_item_id", unique=True)
        await self.db.recipe_bom.create_index("ingredients.material_id")

        # Create shopping_lists collection with indexes
        await self.db.shopping_lists.create_index("list_id", unique=True)
        await self.db.shopping_lists.create_index("status")
        await self.db.shopping_lists.create_index("generated_at")
        await self.db.shopping_lists.create_index([("status", 1), ("generated_at", -1)])

        # Create financial_alerts collection with indexes
        await self.db.financial_alerts.create_index("alert_type")
        await self.db.financial_alerts.create_index("status")
        await self.db.financial_alerts.create_index("created_at")
        await self.db.financial_alerts.create_index([("status", 1), ("created_at", -1)])

        # Create notifications collection with TTL (7 days) and role index
        await self.db.notifications.create_index("notification_id", unique=True)
        await self.db.notifications.create_index("target_roles")
        await self.db.notifications.create_index("is_read")
        await self.db.notifications.create_index([("target_roles", 1), ("is_read", 1), ("created_at", -1)])
        await self.db.notifications.create_index(
            "created_at",
            expireAfterSeconds=604800  # TTL: 7 days
        )

        # Create expiry_specials collection with 14-day TTL and status index
        await self.db.expiry_specials.create_index("special_id", unique=True)
        await self.db.expiry_specials.create_index("status")
        await self.db.expiry_specials.create_index("restaurant_id")
        await self.db.expiry_specials.create_index(
            "created_at",
            expireAfterSeconds=1209600  # TTL: 14 days
        )

        # Create promotion_suggestions collection with indexes
        await self.db.promotion_suggestions.create_index("suggestion_id", unique=True)
        await self.db.promotion_suggestions.create_index("status")
        await self.db.promotion_suggestions.create_index("restaurant_id")
        await self.db.promotion_suggestions.create_index([("restaurant_id", 1), ("status", 1), ("created_at", -1)])
        await self.db.promotion_suggestions.create_index(
            "created_at",
            expireAfterSeconds=604800  # TTL: 7 days
        )

        # Create promotions collection (approved/active promotions) with indexes
        await self.db.promotions.create_index("restaurant_id")
        await self.db.promotions.create_index("status")
        await self.db.promotions.create_index([("restaurant_id", 1), ("status", 1), ("end_date", 1)])

        logger.info("MongoDB collections and indexes created")

    async def _register_agents(self) -> None:
        """
        Register all agents

        Agents will be imported and initialized here
        """
        # Import agents
        from app.services.agents.inventory_agent import get_inventory_agent
        from app.services.agents.financial_agent import get_financial_agent
        from app.services.agents.customer_experience_agent import get_customer_experience_agent

        # Initialize agents
        self.agents = {
            'inventory': get_inventory_agent(),
            'financial': get_financial_agent(),
            'customer_experience': get_customer_experience_agent(),
            # 'forecaster': DemandForecaster()  # Already runs independently
        }

        logger.info(f"Registered {len(self.agents)} agents")

    async def _subscribe_to_events(self) -> None:
        """
        Subscribe to events from EventBus

        Sets up handlers for various system events
        """
        # Subscribe to inventory events
        self.event_bus.subscribe('inventory.low_stock', self._handle_low_stock)
        self.event_bus.subscribe('inventory.expiring_soon', self._handle_expiring_soon)

        # Subscribe to financial events
        self.event_bus.subscribe('operations.revenue_anomaly', self._handle_revenue_anomaly)
        self.event_bus.subscribe('operations.channel_dip', self._handle_channel_dip)
        self.event_bus.subscribe('operations.kitchen_slow', self._handle_kitchen_bottleneck)
        self.event_bus.subscribe('operations.high_cancellations', self._handle_high_cancellations)
        self.event_bus.subscribe('operations.aov_drop', self._handle_aov_drop)
        self.event_bus.subscribe('operations.table_stale', self._handle_table_stale)
        self.event_bus.subscribe('operations.dead_period', self._handle_dead_period)

        # Legacy subscription kept for any in-flight events during rollout
        self.event_bus.subscribe('revenue.anomaly', self._handle_revenue_anomaly)

        logger.info("Subscribed to system events")

    def _register_schedules(self) -> None:
        """
        Register scheduled jobs using cron triggers

        Schedule:
        - Inventory Agent: Daily at 6:00 AM
        - Financial Agent: Daily at 11:00 PM
        - Demand Forecaster: Weekly on Sunday at midnight
        """
        # Inventory Agent - Daily at 6 AM
        self.scheduler.add_job(
            self._run_inventory_agent,
            CronTrigger(hour=6, minute=0),
            id='inventory_daily',
            name='Inventory Daily Check',
            replace_existing=True
        )

        # Financial Agent - Daily at 11 PM
        self.scheduler.add_job(
            self._run_financial_agent,
            CronTrigger(hour=23, minute=0),
            id='financial_daily',
            name='Financial Daily Analysis',
            replace_existing=True
        )

        # Demand Forecaster - Weekly on Sunday at midnight
        self.scheduler.add_job(
            self._run_demand_forecaster,
            CronTrigger(day_of_week='sun', hour=0, minute=0),
            id='forecast_weekly',
            name='Weekly Demand Forecast',
            replace_existing=True
        )

        # Operations Pulse - Every hour at minute 5 (data has settled by then)
        self.scheduler.add_job(
            self._run_operations_pulse,
            CronTrigger(minute=5),
            id='operations_pulse_hourly',
            name='Hourly Operations Pulse Check',
            replace_existing=True
        )

        # Expiry Monitor - Daily at 7 AM
        self.scheduler.add_job(
            self._run_expiry_monitor,
            CronTrigger(hour=7, minute=0),
            id='expiry_monitor_daily',
            name="Daily Expiry Monitor + Today's Special",
            replace_existing=True
        )

        # HyperPure price capture - Daily at 2 AM
        self.scheduler.add_job(
            self._capture_hyperpure_prices,
            CronTrigger(hour=2, minute=0),
            id='hyperpure_price_capture_daily',
            name='Daily HyperPure Price Capture',
            replace_existing=True
        )

        # Customer Experience Agent - Daily at 7:30 AM
        self.scheduler.add_job(
            self._run_customer_experience_agent,
            CronTrigger(hour=7, minute=30),
            id='cx_agent_daily',
            name='Daily Customer Experience Agent',
            replace_existing=True
        )

        logger.info("Scheduled jobs registered")

    # ===== Agent Execution Methods =====

    async def _run_inventory_agent(
        self,
        *,
        trigger: str = "scheduled",
        forecast_use_cache: bool = True,
    ) -> None:
        """Execute inventory agent (scheduled or triggered)."""
        logger.info(
            "Running Inventory Agent (%s, forecast_use_cache=%s)",
            trigger,
            forecast_use_cache,
        )

        try:
            # Get inventory agent
            agent = self.agents['inventory']

            # Execute agent
            decision = await agent.execute({
                'trigger': trigger,
                'timestamp': now_ist(),
                'forecast_use_cache': forecast_use_cache,
            })

            # Log decision to MongoDB
            decision_id = await self._log_decision('inventory_agent', decision)

            # Process decision - create shopping list
            await self._process_inventory_decision(decision, decision_id)

            logger.info(
                f"Inventory Agent completed: {len(decision.actions)} actions, "
                f"confidence: {decision.confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"Inventory agent failed: {e}", exc_info=True)

    async def _run_financial_agent(self, trigger: str = "scheduled") -> None:
        """Execute financial agent (scheduled)"""
        logger.info(f"Running Financial Agent ({trigger})")

        try:
            # Get financial agent
            agent = self.agents['financial']

            # Execute agent
            decision = await agent.execute({
                'trigger': trigger,
                'timestamp': now_ist()
            })

            # Log decision to MongoDB
            decision_id = await self._log_decision('financial_agent', decision)

            # Process decision - create financial alerts
            await self._process_financial_decision(decision, decision_id)

            logger.info(
                f"Financial Agent completed: {len(decision.actions)} actions, "
                f"confidence: {decision.confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"Financial agent failed: {e}", exc_info=True)

    async def _run_demand_forecaster(self) -> None:
        """Execute demand forecaster (weekly)"""
        logger.info("Running Demand Forecaster (scheduled)")

        try:
            from app.services.demand_forecaster import get_demand_forecaster

            forecaster = get_demand_forecaster()

            # Generate forecasts for all ingredients (7-day horizon)
            # Use AI enhancement for the weekly run
            forecasts = await forecaster.forecast_all_ingredients(
                horizon_days=7,
                use_cache=False,  # Force regeneration on scheduled run
                enhance_with_ai=True  # Apply weather + events context
            )

            # Log summary
            logger.info(
                f"Demand Forecaster completed: {len(forecasts)} ingredients forecasted"
            )

            # Store summary in agent_decisions
            await self.db.agent_decisions.insert_one({
                'agent_name': 'demand_forecaster',
                'timestamp': now_ist(),
                'decision': {
                    'actions': [],  # Forecasting is informational, no actions
                    'reasoning': f'Generated weekly forecasts for {len(forecasts)} ingredients',
                    'confidence': sum(f.get('confidence_score', 0) for f in forecasts) / len(forecasts) if forecasts else 0
                },
                'status': 'executed',
                'trigger': 'scheduled_weekly'
            })

        except Exception as e:
            logger.error(f"Demand forecaster failed: {e}", exc_info=True)

    async def _run_operations_pulse(self, restaurant_id: str = "antera_jubilee_hills") -> None:
        """Run all operations health checks (runs every hour at :05)."""
        logger.debug("Running Operations Pulse")
        try:
            from app.services.operations_pulse_service import get_operations_pulse
            await get_operations_pulse().run_all_checks(restaurant_id)
        except Exception as e:
            logger.error(f"Operations pulse failed: {e}", exc_info=True)

    async def _run_expiry_monitor(self) -> None:
        """Find expiring items, generate Today's Special via LLM, write pending record."""
        logger.info("Running Expiry Monitor")
        try:
            from app.services.expiry_monitor_service import get_expiry_monitor
            special = await get_expiry_monitor().run()
            if special:
                logger.info(f"Expiry monitor: created special {special.get('special_id')}")
        except Exception as e:
            logger.error(f"Expiry monitor failed: {e}", exc_info=True)

    async def _capture_hyperpure_prices(self) -> None:
        """Write today's HyperPure catalogue prices into cost_history (source='hyperpure')."""
        logger.info("Running HyperPure price capture")
        try:
            from app.services.hyperpure_client import get_hyperpure_client
            client = get_hyperpure_client()
            pricing_svc = get_pricing_service()
            now = now_ist()
            recorded = 0
            for material_id, info in client._MOCK_PRICES_BY_ID.items():
                price = info.get("price_paise_per_base")
                if price is None:
                    continue
                await pricing_svc.record_price(
                    material_id=material_id,
                    price_paise_per_base=int(price),
                    source="hyperpure",
                    effective_date=now,
                )
                recorded += 1
            logger.info(f"HyperPure price capture: recorded {recorded} entries")
        except Exception as e:
            logger.error(f"HyperPure price capture failed: {e}", exc_info=True)

    async def _run_customer_experience_agent(self, trigger: str = "scheduled") -> None:
        """Execute customer experience agent (daily at 7:30 AM) to generate promotion suggestions."""
        logger.info(f"Running Customer Experience Agent ({trigger})")

        try:
            agent = self.agents['customer_experience']

            decision = await agent.execute({
                'trigger': trigger,
                'timestamp': now_ist(),
            })

            decision_id = await self._log_decision('customer_experience_agent', decision)

            # Surface notification when suggestions were saved
            saved_count = 0
            for action in decision.actions:
                if action.action_type == "promotion_suggestions_created":
                    saved_count = action.data.get("count", 0)
                    break

            if saved_count > 0:
                await self._create_notification(
                    type="promotion_suggestions",
                    title=f"{saved_count} promotion suggestion{'s' if saved_count > 1 else ''} ready",
                    message=(
                        f"Customer Experience Agent generated {saved_count} promotion "
                        f"suggestion{'s' if saved_count > 1 else ''} for today — review in Dashboard."
                    ),
                    severity="info",
                    target_roles=["admin"],
                    metadata={"decision_id": decision_id, "count": saved_count},
                )

            logger.info(
                f"Customer Experience Agent completed: {saved_count} suggestions, "
                f"confidence: {decision.confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"Customer experience agent failed: {e}", exc_info=True)

    async def _process_inventory_decision(
        self,
        decision: Any,
        decision_id: str
    ) -> None:
        """Process inventory agent decision using per-item LLM approval buckets."""
        from app.services.shopping_list_service import get_shopping_list_service

        shopping_list_action = None
        for action in decision.actions:
            if action.action_type == "shopping_list":
                shopping_list_action = action
                break

        if not shopping_list_action:
            logger.info("No shopping list generated by inventory agent")
            return

        items = shopping_list_action.data.get("items", [])
        if not items:
            logger.info("Shopping list is empty - no items to reorder")
            return

        # Read per-item approval decisions from agent metadata
        approval_decisions = decision.metadata.get("approval_decisions", {})
        auto_ids = set(approval_decisions.get("auto_approve", []))
        defer_ids = set(approval_decisions.get("defer", []))
        item_reasons = approval_decisions.get("item_reasons", {})

        # Tag each item with its agent_decision so the service can set item_status
        for item in items:
            mid = item["material_id"]
            if mid in auto_ids:
                item["agent_decision"] = "auto_approve"
            elif mid in defer_ids:
                item["agent_decision"] = "defer"
            else:
                item["agent_decision"] = "escalate"
            item["agent_reason"] = item_reasons.get(mid, "")

        service = get_shopping_list_service()
        list_id = await service.upsert_shopping_list(
            items=items,
            agent_decision_id=decision_id,
            reasoning=decision.reasoning,
            confidence=decision.confidence,
        )

        logger.info(
            f"Upserted shopping list: {list_id} with {len(items)} items "
            f"({len(auto_ids)} auto, "
            f"{len(items) - len(auto_ids) - len(defer_ids)} escalate, "
            f"{len(defer_ids)} defer)"
        )

        # Execute Hyperpure order for auto-approved items (execute_approved_order
        # filters internally for item_status="auto_approved")
        if auto_ids:
            await self._execute_hyperpure_order(list_id, items)

        # If nothing needs manual review, flip list status to approved so the
        # Approvals UI / dashboard don't show a misleading "pending" entry.
        escalate_ids = {
            i["material_id"] for i in items
            if i["material_id"] not in auto_ids and i["material_id"] not in defer_ids
        }
        if not escalate_ids:
            await service.approve_list(
                list_id=list_id,
                user_id="orchestrator_auto",
                notes="All items processed by agent (auto-approved or deferred)",
            )

        # Notify owner with all three buckets
        await self._notify_owner_shopping_update(items, approval_decisions, list_id)

        # Link shopping list to agent decision
        await self.db.agent_decisions.update_one(
            {"_id": ObjectId(decision_id)},
            {"$set": {"shopping_list_id": ObjectId(list_id)}},
        )

    async def _notify_owner_shopping_update(
        self,
        items: List[Dict[str, Any]],
        approval_decisions: Dict[str, Any],
        list_id: str,
    ) -> None:
        """Send owner notification with concise auto/escalate/defer headline."""
        auto_ids = set(approval_decisions.get("auto_approve", []))
        defer_ids = set(approval_decisions.get("defer", []))

        n_auto = sum(1 for i in items if i["material_id"] in auto_ids)
        n_escalate = sum(
            1 for i in items
            if i["material_id"] not in auto_ids and i["material_id"] not in defer_ids
        )
        n_defer = sum(1 for i in items if i["material_id"] in defer_ids)
        n_total = len(items)

        now_str = now_ist().strftime("%I:%M %p")

        if n_escalate > 0 and n_auto > 0:
            title = f"Shopping list — {n_escalate} items need your approval"
            message = (
                f"Shopping list created at {now_str} with {n_total} items. "
                f"{n_auto} auto-ordered, {n_escalate} need review — check Dashboard."
            )
        elif n_escalate > 0:
            title = f"{n_escalate} items need your approval"
            message = (
                f"Shopping list created at {now_str} with {n_total} items. "
                f"All {n_escalate} need your review — check Dashboard."
            )
        else:
            title = f"Shopping list processed — {n_auto} items auto-ordered"
            message = (
                f"Shopping list created at {now_str} with {n_total} items. "
                f"{n_auto} auto-ordered, {n_defer} deferred to weekly digest."
            )

        severity = "warning" if n_escalate > 0 else "info"

        await self._create_notification(
            type="shopping_update",
            title=title,
            message=message,
            severity=severity,
            target_roles=["admin"],
            metadata={"list_id": list_id, "approval_summary": {
                "auto": n_auto,
                "escalate": n_escalate,
                "defer": n_defer,
            }},
        )

    async def _process_financial_decision(
        self,
        decision: Any,
        decision_id: str
    ) -> None:
        """
        Process financial agent decision

        Creates financial alert records for issues requiring attention

        Args:
            decision: AgentDecision from financial agent
            decision_id: MongoDB ID of logged decision
        """
        # Store financial alerts in database
        for action in decision.actions:
            if action.action_type == "financial_alert":
                alert_data = action.data
                alert_data.update({
                    "agent_decision_id": decision_id,
                    "reasoning": action.reasoning,
                    "confidence": action.confidence,
                    "created_at": now_ist(),
                    "status": "active"
                })

                await self.db.financial_alerts.insert_one(alert_data)

                logger.info(
                    f"Created financial alert: {alert_data.get('alert_type')} "
                    f"(severity: {alert_data.get('severity', 'N/A')})"
                )

    # ===== Event Handlers =====

    async def _create_notification(
        self,
        type: str,
        title: str,
        message: str,
        severity: str,
        target_roles: list,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort notification creation — never raises."""
        try:
            from app.services.notification_service import get_notification_service
            await get_notification_service().create_notification(
                type=type,
                title=title,
                message=message,
                severity=severity,
                target_roles=target_roles,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.warning(f"Notification creation failed: {e}")

    async def _handle_low_stock(self, event_data: Dict[str, Any]) -> None:
        """Handle low stock event — notify admins + store keepers, trigger inventory agent."""
        print(f"[ORCHESTRATOR] Low stock event received: {event_data}", flush=True)
        logger.warning(f"Low stock event: {event_data}")

        name = event_data.get("material_name", "Unknown item")
        stock = event_data.get("current_stock", "?")
        unit = event_data.get("unit", "")
        severity = "high" if (stock or 0) <= 0 else "warning"

        await self._create_notification(
            type="low_stock",
            title=f"Low stock: {name}",
            message=f"{name} is at {stock} {unit}. Reorder triggered.",
            severity=severity,
            target_roles=["admin", "store_keeper"],
            metadata=event_data,
        )

        # Trigger inventory agent immediately
        await self._run_inventory_agent()

    async def _handle_expiring_soon(self, event_data: Dict[str, Any]) -> None:
        """Handle expiring_soon event — delegate to expiry monitor for LLM suggestion."""
        logger.info(f"Expiring soon event received: {event_data}")
        await self._run_expiry_monitor()

    async def _handle_revenue_anomaly(self, event_data: Dict[str, Any]) -> None:
        """Handle revenue anomaly event — notify admin, write alert to DB, run financial agent."""
        logger.warning(f"Revenue anomaly detected: {event_data}")

        hour = event_data.get("hour", "?")
        ratio = event_data.get("ratio", 0)
        pct = round((1 - ratio) * 100)
        severity = event_data.get("severity", "medium")

        await self._create_notification(
            type="revenue_anomaly",
            title=f"Revenue drop at {hour}:00",
            message=f"Revenue is {pct}% below historical average for this hour.",
            severity=severity,
            target_roles=["admin"],
            metadata=event_data,
        )

        # Write alert directly so dashboard Zone 2 shows it immediately.
        # First resolve any stale revenue_anomaly alerts from prior hours today.
        try:
            today_midnight = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
            await self.db.financial_alerts.update_many(
                {"alert_type": "revenue_anomaly", "status": "active", "created_at": {"$lt": today_midnight}},
                {"$set": {"status": "resolved"}},
            )
            await self.db.financial_alerts.insert_one({
                **event_data,
                "status": "active",
                "created_at": now_ist(),
            })
        except Exception as e:
            logger.error(f"Failed to write revenue anomaly alert: {e}")

        # Also run full financial agent for deeper analysis
        await self._run_financial_agent()

    async def _handle_channel_dip(self, event_data: Dict[str, Any]) -> None:
        """Notify floor manager when a sales channel goes quiet."""
        channel = event_data.get("channel", "unknown")
        ratio = event_data.get("ratio", 0)
        pct = round((1 - ratio) * 100)
        count = event_data.get("current_order_count", "?")
        severity = event_data.get("severity", "medium")
        await self._create_notification(
            type="channel_dip",
            title=f"Channel dip: {channel}",
            message=f"{channel.title()} orders are {pct}% below average this hour ({count} orders).",
            severity=severity,
            target_roles=["admin"],
            metadata=event_data,
        )

    async def _handle_kitchen_bottleneck(self, event_data: Dict[str, Any]) -> None:
        """Notify floor manager when kitchen prep time spikes."""
        avg_min = event_data.get("avg_prep_minutes", "?")
        mult = event_data.get("multiplier", "?")
        severity = event_data.get("severity", "medium")
        await self._create_notification(
            type="kitchen_slow",
            title="Kitchen is slow",
            message=f"Average prep time is {avg_min} min ({mult}× baseline). Check kitchen load.",
            severity=severity,
            target_roles=["admin"],
            metadata=event_data,
        )

    async def _handle_high_cancellations(self, event_data: Dict[str, Any]) -> None:
        """Notify when cancellation rate spikes."""
        rate = round(event_data.get("current_cancellation_rate", 0) * 100, 1)
        cancelled = event_data.get("cancelled_orders", "?")
        severity = event_data.get("severity", "medium")
        await self._create_notification(
            type="high_cancellations",
            title=f"High cancellations: {rate}%",
            message=f"{cancelled} orders cancelled this period — investigate cause.",
            severity=severity,
            target_roles=["admin"],
            metadata=event_data,
        )

    async def _handle_aov_drop(self, event_data: Dict[str, Any]) -> None:
        """Notify when average order value drops significantly."""
        aov = event_data.get("current_aov_inr", "?")
        ratio = event_data.get("ratio", 0)
        pct = round((1 - ratio) * 100)
        severity = event_data.get("severity", "medium")
        await self._create_notification(
            type="aov_drop",
            title=f"Low average order value: ₹{aov}",
            message=f"Average order value is {pct}% below normal this hour.",
            severity=severity,
            target_roles=["admin"],
            metadata=event_data,
        )

    async def _handle_table_stale(self, event_data: Dict[str, Any]) -> None:
        """Notify when tables appear occupied with no active order."""
        count = event_data.get("stale_count", 0)
        tables = event_data.get("stale_tables", [])
        numbers = [str(t.get("table_number", "?")) for t in tables]
        await self._create_notification(
            type="table_stale",
            title=f"{count} table(s) may be forgotten",
            message=f"Tables {', '.join(numbers)} are marked occupied with no active order. Check floor.",
            severity="medium",
            target_roles=["admin"],
            metadata=event_data,
        )

    async def _handle_dead_period(self, event_data: Dict[str, Any]) -> None:
        """Notify when no orders have come in during operating hours."""
        minutes = event_data.get("dead_period_minutes", 30)
        hour = event_data.get("hour", "?")
        await self._create_notification(
            type="dead_period",
            title=f"No orders in {minutes} minutes",
            message=f"Zero completed orders since {hour}:00. Is everything OK?",
            severity="high",
            target_roles=["admin"],
            metadata=event_data,
        )

    # ===== Decision Management =====

    async def _log_decision(self, agent_name: str, decision: Any) -> str:
        """
        Log agent decision to MongoDB

        Args:
            agent_name: Name of the agent
            decision: Decision object from agent

        Returns:
            Decision ID (MongoDB ObjectId as string)
        """
        # Convert decision to dict for MongoDB (Pydantic v2 compatibility)
        if hasattr(decision, 'model_dump'):
            try:
                decision_data = decision.model_dump(mode='python')
            except Exception as e:
                logger.warning(f"model_dump failed: {e}, falling back to json parsing")
                import json
                decision_data = json.loads(decision.model_dump_json())
        elif hasattr(decision, 'dict'):
            decision_data = decision.dict()
        else:
            decision_data = decision

        decision_doc = {
            'agent_name': agent_name,
            'timestamp': now_ist(),
            'decision': decision_data,
            'status': 'executed'
        }

        result = await self.db.agent_decisions.insert_one(decision_doc)
        logger.info(f"Logged decision from {agent_name}: {result.inserted_id}")

        return str(result.inserted_id)

    async def _process_decision(self, decision: Any) -> None:
        """
        Process decision - execute or queue for approval

        Args:
            decision: Decision object from agent
        """
        # TODO: Implement when decision structure is defined
        logger.info("Decision processing placeholder")

    async def execute_approved_order(self, list_id: str) -> None:
        """
        Place approved shopping list items on Hyperpure.

        Called after owner or auto-approval. Fetches the shopping list,
        collects approved items, calls Hyperpure, and handles all outcome paths:
          - confirmed  → mark items as ordered, notify owner
          - partial    → mark confirmed items ordered, notify owner of shortfall
          - rejected   → park list, notify owner with reason
          - error      → park list, notify owner that browser automation failed

        Duplicate-order guard: skips items already in 'ordered' or 'delivered' state.
        """
        from app.services.shopping_list_service import get_shopping_list_service
        from app.services.hyperpure_client import get_hyperpure_client
        from app.repositories.purchase_order_repository import get_purchase_order_repository
        import os

        service = get_shopping_list_service()
        shopping_list = await service.get_shopping_list(list_id)
        if not shopping_list:
            logger.error(f"execute_approved_order: list {list_id} not found")
            return

        # Collect items that are approved but not yet ordered/delivered (duplicate guard)
        actionable_statuses = {"auto_approved", "owner_approved", "approved"}
        locked_statuses = {"ordered", "delivered"}
        items_to_order = [
            i for i in shopping_list.get("items", [])
            if (
                i.get("item_status") in actionable_statuses
                or i.get("status") in actionable_statuses
            )
            and i.get("item_status") not in locked_statuses
        ]

        if not items_to_order:
            logger.info(f"execute_approved_order: no actionable items in list {list_id}")
            return

        logger.info(
            f"Placing Hyperpure order for list {list_id}: {len(items_to_order)} items"
        )

        client = get_hyperpure_client()
        result = await client.place_order(items_to_order)

        po_id = result.order_id or f"PARKED-{list_id[:8]}"
        po_repo = get_purchase_order_repository()

        if result.status == "confirmed":
            await service.mark_items_ordered(list_id, result.confirmed_items, po_id)

            confirmed_items_data = [
                i for i in items_to_order if i["material_id"] in result.confirmed_items
            ]
            total_cost = sum(i.get("line_total_inr", 0) for i in confirmed_items_data)
            await po_repo.create({
                "po_number": po_id,
                "source": "hyperpure",
                "supplier_id": "hyperpure",
                "supplier_name": "Hyperpure",
                "shopping_list_id": list_id,
                "status": "pending",
                "items": [
                    {
                        "material_id": i["material_id"],
                        "material_name": i.get("material_name", ""),
                        "quantity": i.get("quantity_to_order", 0),
                        "unit": i.get("unit", ""),
                        "unit_cost_inr": i.get("unit_cost_inr", 0),
                        "line_total_inr": i.get("line_total_inr", 0),
                    }
                    for i in confirmed_items_data
                ],
                "total_cost_inr": total_cost,
                "ordered_at": now_ist(),
            })

            await self._create_notification(
                type="order_placed",
                title=f"Order {result.order_id} placed on Hyperpure",
                message=(
                    f"Placed order for {len(result.confirmed_items)} items "
                    f"(ref: {result.order_id}). Check Hyperpure Orders for status."
                ),
                severity="info",
                target_roles=["admin", "store_keeper"],
                metadata={"order_id": result.order_id, "list_id": list_id},
            )
            logger.info(f"Hyperpure order confirmed: {result.order_id}")
            if os.getenv("HYPERPURE_USE_MOCK", "true").lower() != "false":
                asyncio.create_task(
                    self._mock_deliver_after_delay(
                        list_id, result.confirmed_items, result.order_id, items_to_order, po_id
                    )
                )

        elif result.status == "partial":
            if result.confirmed_items:
                await service.mark_items_ordered(list_id, result.confirmed_items, po_id)
                confirmed_items_data = [
                    i for i in items_to_order if i["material_id"] in result.confirmed_items
                ]
                total_cost = sum(i.get("line_total_inr", 0) for i in confirmed_items_data)
                await po_repo.create({
                    "po_number": po_id,
                    "source": "hyperpure",
                    "supplier_id": "hyperpure",
                    "supplier_name": "Hyperpure",
                    "shopping_list_id": list_id,
                    "status": "pending",
                    "items": [
                        {
                            "material_id": i["material_id"],
                            "material_name": i.get("material_name", ""),
                            "quantity": i.get("quantity_to_order", 0),
                            "unit": i.get("unit", ""),
                            "unit_cost_inr": i.get("unit_cost_inr", 0),
                            "line_total_inr": i.get("line_total_inr", 0),
                        }
                        for i in confirmed_items_data
                    ],
                    "total_cost_inr": total_cost,
                    "ordered_at": now_ist(),
                })
                if os.getenv("HYPERPURE_USE_MOCK", "true").lower() != "false":
                    asyncio.create_task(
                        self._mock_deliver_after_delay(
                            list_id, result.confirmed_items, result.order_id, confirmed_items_data, po_id
                        )
                    )
            await self._create_notification(
                type="order_partial",
                title=f"Order {result.order_id} partially placed",
                message=(
                    f"{len(result.confirmed_items)} items ordered, "
                    f"{len(result.rejected_items)} out of stock — check Hyperpure Orders."
                ),
                severity="warning",
                target_roles=["admin", "store_keeper"],
                metadata={"order_id": result.order_id, "list_id": list_id},
            )
            logger.warning(
                f"Hyperpure partial order {result.order_id}: "
                f"{len(result.rejected_items)} items OOS"
            )

        elif result.status == "rejected":
            await self._create_notification(
                type="order_rejected",
                title="Hyperpure rejected the order",
                message="Order not accepted — check Hyperpure Orders and reorder manually.",
                severity="high",
                target_roles=["admin"],
                metadata={"list_id": list_id},
            )
            logger.error(f"Hyperpure rejected order for list {list_id}: {result.message}")

        else:  # error
            await self._create_notification(
                type="order_error",
                title="Hyperpure unavailable",
                message="Could not place order automatically — please order manually or retry later.",
                severity="high",
                target_roles=["admin"],
                metadata={"list_id": list_id},
            )
            logger.error(f"Hyperpure error for list {list_id}: {result.message}")

    async def _execute_hyperpure_order(self, list_id: str, items: List[Dict[str, Any]]) -> None:
        """Thin wrapper used by auto-approve path."""
        await self.execute_approved_order(list_id)

    async def _mock_deliver_after_delay(
        self,
        list_id: str,
        material_ids: List[str],
        order_id: Optional[str],
        items_data: List[Dict[str, Any]],
        po_number: Optional[str] = None,
    ) -> None:
        """Simulate Hyperpure delivery 60 seconds after order confirmation."""
        await asyncio.sleep(60)
        try:
            from app.services.shopping_list_service import get_shopping_list_service
            from app.services.inventory_service import get_inventory_service
            from app.repositories.purchase_order_repository import get_purchase_order_repository

            service = get_shopping_list_service()
            inv_service = get_inventory_service()

            await service.mark_items_delivered(list_id, material_ids)

            qty_map = {i["material_id"]: i.get("quantity_to_order", 0) for i in items_data}
            for mid in material_ids:
                qty = qty_map.get(mid, 0)
                if qty > 0:
                    await inv_service.add_stock(mid, qty, source="hyperpure_delivery")

            # Update PO status to fully_received
            if po_number:
                po_repo = get_purchase_order_repository()
                po_doc = await po_repo.get_by_po_number(po_number)
                if po_doc:
                    await po_repo.update(str(po_doc["_id"]), {
                        "status": "fully_received",
                        "delivered_at": now_ist(),
                    })

            await self._create_notification(
                type="order_delivered",
                title=f"Order {order_id} delivered",
                message=(
                    f"{len(material_ids)} items from Hyperpure order {order_id} "
                    f"have been delivered and inventory updated."
                ),
                severity="info",
                target_roles=["admin", "store_keeper"],
                metadata={"order_id": order_id, "list_id": list_id},
            )
            logger.info(f"Mock delivery complete for order {order_id}, list {list_id}")
        except Exception as e:
            logger.error(f"Mock delivery failed for list {list_id}: {e}", exc_info=True)

    async def _execute_action(self, action: Dict[str, Any]) -> None:
        """
        Execute approved action

        Args:
            action: Action to execute
        """
        logger.info(f"Executing action: {action.get('action_type')}")

    # ===== Manual Triggers (for testing/API) =====

    async def trigger_agent(self, agent_name: str) -> Dict[str, Any]:
        """
        Manually trigger an agent (for testing or API endpoint)

        Args:
            agent_name: Name of agent to trigger

        Returns:
            Result of agent execution
        """
        logger.info(f"Manually triggering agent: {agent_name}")

        if agent_name == 'inventory':
            # Manual trigger bypasses forecast cache so the full forecasting path
            # (incl. v7 lazy loader) runs and emits logs.
            await self._run_inventory_agent(trigger="manual", forecast_use_cache=False)
        elif agent_name == 'financial':
            await self._run_financial_agent(trigger="manual")
        elif agent_name == 'forecaster':
            await self._run_demand_forecaster()
        elif agent_name == 'expiry':
            await self._run_expiry_monitor()
        elif agent_name in ('revenue', 'pulse'):
            await self._run_operations_pulse()
        elif agent_name == 'customer_experience':
            await self._run_customer_experience_agent(trigger="manual")
        else:
            raise ValueError(f"Unknown agent: {agent_name}")

        return {'status': 'triggered', 'agent': agent_name}

    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        Get scheduler status and job information

        Returns:
            Scheduler status and jobs
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })

        return {
            'running': self.scheduler.running,
            'jobs': jobs
        }


# Global orchestrator instance (singleton)
_orchestrator_instance = None


def get_orchestrator() -> OrchestratorService:
    """
    Get global orchestrator instance (singleton pattern)

    Returns:
        Global OrchestratorService instance
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorService()
    return _orchestrator_instance
