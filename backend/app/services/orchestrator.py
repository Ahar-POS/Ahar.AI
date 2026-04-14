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
from typing import Dict, Any, List, Optional, Tuple
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.core.database import get_database
from app.services.event_bus import get_event_bus

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

        logger.info("MongoDB collections and indexes created")

    async def _register_agents(self) -> None:
        """
        Register all agents

        Agents will be imported and initialized here
        """
        # Import agents
        from app.services.agents.inventory_agent import get_inventory_agent
        from app.services.agents.financial_agent import get_financial_agent

        # Initialize agents
        self.agents = {
            'inventory': get_inventory_agent(),
            'financial': get_financial_agent(),
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
        self.event_bus.subscribe('revenue.anomaly', self._handle_revenue_anomaly)

        # Subscribe to kitchen events
        self.event_bus.subscribe('kitchen.bottleneck', self._handle_kitchen_bottleneck)

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

        # Revenue Monitor - Every hour at minute 5 (data has settled by then)
        self.scheduler.add_job(
            self._run_revenue_monitor,
            CronTrigger(minute=5),
            id='revenue_monitor_hourly',
            name='Hourly Revenue Anomaly Check',
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
                'timestamp': datetime.utcnow(),
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

    async def _run_financial_agent(self) -> None:
        """Execute financial agent (scheduled)"""
        logger.info("Running Financial Agent (scheduled)")

        try:
            # Get financial agent
            agent = self.agents['financial']

            # Execute agent
            decision = await agent.execute({
                'trigger': 'scheduled',
                'timestamp': datetime.utcnow()
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
                'timestamp': datetime.utcnow(),
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

    async def _run_revenue_monitor(self) -> None:
        """Check hourly revenue for anomalies (runs every hour at :05)."""
        logger.debug("Running Revenue Monitor")
        try:
            from app.services.revenue_monitor_service import get_revenue_monitor
            anomaly = await get_revenue_monitor().check_hourly_revenue()
            if anomaly:
                logger.info(f"Revenue monitor flagged anomaly: {anomaly}")
        except Exception as e:
            logger.error(f"Revenue monitor failed: {e}", exc_info=True)

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

    async def _process_inventory_decision(
        self,
        decision: Any,
        decision_id: str
    ) -> None:
        """
        Process inventory agent decision

        Creates shopping list from decision if items need reordering

        Args:
            decision: AgentDecision from inventory agent
            decision_id: MongoDB ID of logged decision
        """
        from app.services.shopping_list_service import get_shopping_list_service

        # Find shopping_list action
        shopping_list_action = None
        for action in decision.actions:
            if action.action_type == "shopping_list":
                shopping_list_action = action
                break

        if not shopping_list_action:
            logger.info("No shopping list generated by inventory agent")
            return

        # Extract items from action data
        items = shopping_list_action.data.get("items", [])

        if not items:
            logger.info("Shopping list is empty - no items to reorder")
            return

        # Phase 5: evaluate auto-approve criteria before creating the list
        requires_approval, approval_reason = await self._requires_approval(items)

        # Create shopping list (always starts as "pending")
        service = get_shopping_list_service()
        list_id = await service.create_shopping_list(
            items=items,
            agent_decision_id=decision_id,
            reasoning=decision.reasoning,
            confidence=decision.confidence
        )

        logger.info(
            f"Created shopping list: {list_id} with {len(items)} items "
            f"(total: ₹{shopping_list_action.estimated_cost/100:.2f})"
        )

        # Auto-approve or leave pending for manual review
        if not requires_approval:
            await service.approve_list(
                list_id=list_id,
                user_id="orchestrator_auto",
                notes=f"Auto-approved: {approval_reason}"
            )
            logger.info(f"Auto-approved shopping list {list_id}: {approval_reason}")
        else:
            logger.info(f"Shopping list {list_id} flagged for manual approval: {approval_reason}")

        # Link shopping list to agent decision
        await self.db.agent_decisions.update_one(
            {"_id": ObjectId(decision_id)},
            {"$set": {"shopping_list_id": ObjectId(list_id)}}
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
                    "created_at": datetime.utcnow(),
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

        # Write alert directly so dashboard Zone 2 shows it immediately
        try:
            await self.db.financial_alerts.insert_one({
                **event_data,
                "status": "active",
                "created_at": datetime.utcnow(),
            })
        except Exception as e:
            logger.error(f"Failed to write revenue anomaly alert: {e}")

        # Also run full financial agent for deeper analysis
        await self._run_financial_agent()

    async def _handle_kitchen_bottleneck(self, event_data: Dict[str, Any]) -> None:
        """Handle kitchen bottleneck event"""
        logger.warning(f"Kitchen bottleneck detected: {event_data}")

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
            'timestamp': datetime.utcnow(),
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

    async def _requires_approval(self, items: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Determine if a shopping list requires manual approval.

        Auto-approves only when ALL criteria pass:
        - Total order cost < AUTO_APPROVE_LIMIT_INR
        - All suppliers are known (supplier_name populated by inventory agent)
        - No item has quantity_to_order > 2 × reorder_qty (fetched from DB)
        - No item has the expiry_discount flag set (forward-compatible: absent → False)

        Returns:
            (requires_approval, reason) — reason explains the decision either way.
        """
        try:
            from app.core.config import get_settings
            settings = get_settings()

            # 1. Total cost check (line_total_inr is in paise; divide by 100 for rupees)
            total_cost_rupees = sum(item.get("line_total_inr", 0) for item in items) / 100
            print(f"[AUTO-APPROVE] Cost gate: ₹{total_cost_rupees:.0f} vs limit ₹{settings.AUTO_APPROVE_LIMIT_INR}", flush=True)
            if total_cost_rupees >= settings.AUTO_APPROVE_LIMIT_INR:
                return True, (
                    f"Total cost ₹{total_cost_rupees:.0f} meets or exceeds "
                    f"auto-approve limit ₹{settings.AUTO_APPROVE_LIMIT_INR}"
                )

            # 2. Supplier check (inventory agent sets "Unknown Supplier" when lookup fails)
            if not settings.AUTO_APPROVE_NEW_SUPPLIER:
                for item in items:
                    supplier_name = (item.get("supplier_name") or "").strip()
                    if not supplier_name or supplier_name == "Unknown Supplier":
                        return True, (
                            f"Unknown supplier for "
                            f"{item.get('material_name', item.get('material_id', '?'))}"
                        )

            # 3. Quantity vs reorder_qty — batch DB lookup to avoid N+1 queries
            material_ids = [item["material_id"] for item in items if item.get("material_id")]
            reorder_qtys: Dict[str, int] = {}
            if material_ids:
                cursor = self.db.raw_material_inventory.find(
                    {"material_id": {"$in": material_ids}},
                    {"material_id": 1, "reorder_qty": 1}
                )
                async for doc in cursor:
                    reorder_qtys[doc["material_id"]] = int(doc.get("reorder_qty", 0))

            for item in items:
                material_id = item.get("material_id")
                qty_ordered = float(item.get("quantity_to_order", 0))
                reorder_qty = reorder_qtys.get(material_id, 0)
                print(f"[AUTO-APPROVE] Qty gate: {item.get('material_name')} ordered={qty_ordered} reorder_qty={reorder_qty} 2x={2*reorder_qty}", flush=True)
                if reorder_qty > 0 and qty_ordered > 2 * reorder_qty:
                    return True, (
                        f"{item.get('material_name', material_id)}: order qty {qty_ordered:.0f} "
                        f"exceeds 2× reorder qty ({reorder_qty})"
                    )

            # 4. Expiry-discount flag (field absent → False; activates automatically once Phase 3 adds it)
            for item in items:
                if item.get("expiry_discount", False):
                    return True, (
                        f"{item.get('material_name', item.get('material_id', '?'))}: "
                        f"expiry discount flag set"
                    )

            print(f"[AUTO-APPROVE] All gates passed — auto-approving", flush=True)
            return False, "All auto-approve criteria met"

        except Exception as e:
            print(f"[AUTO-APPROVE] Exception in gates: {e}", flush=True)
            logger.error(f"_requires_approval check failed: {e}", exc_info=True)
            return True, "DB lookup failed — defaulting to manual review"

    async def _execute_action(self, action: Dict[str, Any]) -> None:
        """
        Execute approved action

        Args:
            action: Action to execute
        """
        # TODO: Implement action execution
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
            await self._run_financial_agent()
        elif agent_name == 'forecaster':
            await self._run_demand_forecaster()
        elif agent_name == 'expiry':
            await self._run_expiry_monitor()
        elif agent_name == 'revenue':
            await self._run_revenue_monitor()
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
