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
from typing import Dict, Any, Optional
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

        logger.info("Scheduled jobs registered")

    # ===== Agent Execution Methods =====

    async def _run_inventory_agent(self) -> None:
        """Execute inventory agent (scheduled or triggered)"""
        logger.info("Running Inventory Agent (scheduled)")

        try:
            # Get inventory agent
            agent = self.agents['inventory']

            # Execute agent
            decision = await agent.execute({
                'trigger': 'scheduled',
                'timestamp': datetime.utcnow()
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

        # Create shopping list
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

    async def _handle_low_stock(self, event_data: Dict[str, Any]) -> None:
        """Handle low stock event - trigger inventory agent"""
        logger.warning(f"Low stock event: {event_data}")

        # Trigger inventory agent immediately
        await self._run_inventory_agent()

    async def _handle_expiring_soon(self, event_data: Dict[str, Any]) -> None:
        """Handle expiring soon event"""
        logger.warning(f"Expiring soon event: {event_data}")

        # Log waste alert
        await self.db.agent_decisions.insert_one({
            'agent_name': 'system',
            'timestamp': datetime.utcnow(),
            'decision': {
                'action_type': 'waste_alert',
                'data': event_data
            },
            'status': 'logged'
        })

    async def _handle_revenue_anomaly(self, event_data: Dict[str, Any]) -> None:
        """Handle revenue anomaly event"""
        logger.warning(f"Revenue anomaly detected: {event_data}")

        # Trigger financial agent
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
            'status': 'pending_approval' if self._requires_approval(decision) else 'executed'
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

    def _requires_approval(self, decision: Any) -> bool:
        """
        Determine if decision requires manual approval

        Args:
            decision: Decision object

        Returns:
            True if approval needed
        """
        # TODO: Implement approval logic
        return False

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
            await self._run_inventory_agent()
        elif agent_name == 'financial':
            await self._run_financial_agent()
        elif agent_name == 'forecaster':
            await self._run_demand_forecaster()
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
