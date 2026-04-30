# Autonomous Agent Implementation Example
**Concrete Code: Wrapper → Autonomous Transformation**

**Date:** 2026-03-18

---

## Side-by-Side Comparison: Purchasing Workflow

### ❌ CURRENT APPROACH (Wrapper)

```python
# backend/app/services/agents/inventory_agent.py (current)

class InventoryAgent:
    """Current implementation: Generates suggestions for human approval"""

    async def generate_shopping_list(self):
        """
        WRAPPER PATTERN:
        1. Forecast demand
        2. Calculate what to order
        3. Create shopping list
        4. STOP → Wait for human to approve
        """
        low_stock_items = []

        for material in await self.get_all_materials():
            # Step 1: Forecast demand
            forecast = await self.demand_forecaster.forecast(material.id)

            # Step 2: Calculate order quantity
            current_stock = material.current_stock
            predicted_consumption = forecast.total_quantity
            safety_buffer = predicted_consumption * 0.15  # Fixed 15%

            if current_stock < (predicted_consumption + safety_buffer):
                order_qty = predicted_consumption + safety_buffer - current_stock

                low_stock_items.append({
                    "material_id": material.id,
                    "material_name": material.name,
                    "quantity_to_order": order_qty,
                    "current_stock": current_stock,
                    "reasoning": "Stock below forecast + 15% buffer"
                })

        # Step 3: Save shopping list
        shopping_list = await self.shopping_list_service.create_list(
            items=low_stock_items,
            status="pending_approval"  # ← STOPS HERE
        )

        # Step 4: Notify human
        await self.notification_service.send_notification(
            user_type="admin",
            message=f"New shopping list with {len(low_stock_items)} items ready for approval"
        )

        return shopping_list

# Frontend: ApprovalsPage.tsx (current)
# Human must:
# 1. Open /approvals page
# 2. Review every item
# 3. Click "Approve" button
# 4. Manually email/call supplier
```

**Problems:**
1. ❌ Human is the bottleneck—must review 100% of orders
2. ❌ No actual ordering happens—AI just creates a list
3. ❌ Fixed logic (15% buffer)—no learning or adaptation
4. ❌ No supplier integration—human must manually place order
5. ❌ No follow-up—AI doesn't track if order was placed

---

### ✅ NEW APPROACH (Autonomous)

```python
# backend/app/services/agents/autonomous_purchasing_agent.py (new)

from enum import Enum
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

class DecisionConfidence(Enum):
    HIGH = "high"        # >90% confidence → Auto-execute
    MEDIUM = "medium"    # 70-90% → Auto-execute low-risk only
    LOW = "low"          # <70% → Human review required

class ExecutionMode(Enum):
    AUTONOMOUS = "autonomous"        # AI executes without approval
    HUMAN_REVIEW = "human_review"    # Requires approval
    SIMULATION = "simulation"        # Test mode (don't execute)

@dataclass
class PurchaseDecision:
    material_id: str
    material_name: str
    quantity_to_order: float
    unit: str
    supplier_id: str
    supplier_name: str
    unit_price: float
    total_cost: float
    delivery_date: datetime
    confidence: float
    reasoning: str
    risk_factors: List[str]
    execution_mode: ExecutionMode


class AutonomousPurchasingAgent:
    """
    AUTONOMOUS PATTERN:
    1. Continuously monitors inventory
    2. Detects low stock situations
    3. Makes intelligent purchasing decisions
    4. Executes orders autonomously (if confidence high)
    5. Tracks delivery and outcomes
    6. Learns from results
    """

    def __init__(self):
        self.demand_forecaster = DemandForecaster()
        self.supplier_service = SupplierIntegrationService()
        self.budget_service = BudgetService()
        self.decision_logger = DecisionLogger()
        self.execution_tracker = ExecutionTracker()
        self.learning_engine = LearningEngine()

    # ============================================================================
    # STEP 1: CONTINUOUS MONITORING (Event-Driven, Not Scheduled)
    # ============================================================================

    async def on_inventory_change(self, event: InventoryChangeEvent):
        """
        Triggered by real-time inventory updates (not scheduled job)
        Example events: sale made, delivery received, waste logged
        """
        material_id = event.material_id
        new_stock_level = event.new_stock_level

        # Check if action needed
        should_order = await self._should_trigger_order(material_id, new_stock_level)

        if should_order:
            await self._initiate_purchase_decision(material_id)

    async def _should_trigger_order(self, material_id: str, current_stock: float) -> bool:
        """
        Intelligent trigger logic (not just reorder level)
        """
        material = await self.inventory_repository.get_by_material_id(material_id)

        # Factor 1: Below reorder level?
        if current_stock > material.reorder_level:
            return False

        # Factor 2: Is order already in progress?
        pending_order = await self.execution_tracker.get_pending_order(material_id)
        if pending_order:
            logger.info(f"Order already pending for {material_id}, skipping")
            return False

        # Factor 3: Forecast demand in lead time window
        supplier_lead_time = await self.supplier_service.get_lead_time(material_id)
        forecast = await self.demand_forecaster.forecast(
            material_id,
            horizon_days=supplier_lead_time + 2  # Lead time + buffer
        )

        # Factor 4: Will we run out before delivery?
        predicted_runout_date = current_stock / forecast.daily_avg_consumption
        if predicted_runout_date < supplier_lead_time:
            logger.warning(f"URGENT: {material_id} will run out in {predicted_runout_date:.1f} days")
            return True

        return False

    # ============================================================================
    # STEP 2: INTELLIGENT DECISION-MAKING (Multi-Factor Analysis)
    # ============================================================================

    async def _initiate_purchase_decision(self, material_id: str):
        """
        Main decision pipeline: Analyze → Decide → Execute (or escalate)
        """
        # Gather all relevant data
        context = await self._gather_decision_context(material_id)

        # Generate decision options
        options = await self._generate_purchase_options(context)

        # Evaluate each option
        evaluated = await self._evaluate_options(options, context)

        # Select best option
        best_decision = self._select_best_option(evaluated)

        # Determine execution mode based on confidence and risk
        execution_mode = self._determine_execution_mode(best_decision, context)
        best_decision.execution_mode = execution_mode

        # Execute or escalate
        if execution_mode == ExecutionMode.AUTONOMOUS:
            await self._execute_purchase(best_decision)
        else:
            await self._escalate_to_human(best_decision)

        # Log decision
        await self.decision_logger.log(best_decision)

    async def _gather_decision_context(self, material_id: str) -> Dict:
        """
        Gather comprehensive context for decision-making
        """
        material = await self.inventory_repository.get_by_material_id(material_id)

        # Parallel data fetching for speed
        forecast, supplier_info, budget, price_history, quality_history = await asyncio.gather(
            self.demand_forecaster.forecast_with_reasoning(material_id, horizon_days=14),
            self.supplier_service.get_supplier_info(material_id),
            self.budget_service.get_available_budget(),
            self.supplier_service.get_price_history(material_id, days=90),
            self.supplier_service.get_quality_history(material_id, days=180)
        )

        return {
            "material": material,
            "current_stock": material.current_stock,
            "reorder_level": material.reorder_level,
            "forecast": forecast,
            "supplier_info": supplier_info,
            "budget_available": budget,
            "price_history": price_history,
            "quality_history": quality_history,
            "seasonality": self._detect_seasonality(forecast),
            "lead_time": supplier_info.lead_time_days,
            "is_critical_item": material.is_critical,
            "is_perishable": material.is_perishable
        }

    async def _generate_purchase_options(self, context: Dict) -> List[PurchaseOption]:
        """
        Generate multiple purchase options (different suppliers, quantities, timing)
        """
        options = []

        # Option 1: Preferred supplier, standard quantity
        primary_supplier = context["supplier_info"].primary_supplier
        standard_qty = await self._calculate_optimal_quantity(
            forecast=context["forecast"],
            current_stock=context["current_stock"],
            lead_time=primary_supplier.lead_time_days,
            is_perishable=context["is_perishable"]
        )
        options.append(PurchaseOption(
            supplier=primary_supplier,
            quantity=standard_qty,
            timing="immediate",
            priority="standard"
        ))

        # Option 2: Alternative supplier (if primary has issues)
        if context["quality_history"].recent_defect_rate > 0.05:  # >5% defects
            alt_supplier = context["supplier_info"].alternative_supplier
            if alt_supplier:
                options.append(PurchaseOption(
                    supplier=alt_supplier,
                    quantity=standard_qty,
                    timing="immediate",
                    priority="quality_fallback"
                ))

        # Option 3: Bulk order (if price discount available)
        bulk_discount = await self.supplier_service.check_bulk_discount(
            material_id=context["material"].material_id,
            quantity=standard_qty * 2
        )
        if bulk_discount and bulk_discount.discount_pct > 10:
            options.append(PurchaseOption(
                supplier=primary_supplier,
                quantity=standard_qty * 2,
                timing="immediate",
                priority="cost_optimization"
            ))

        # Option 4: Delayed order (if not urgent and price expected to drop)
        if context["forecast"].urgency != "urgent":
            price_trend = self._analyze_price_trend(context["price_history"])
            if price_trend == "declining":
                options.append(PurchaseOption(
                    supplier=primary_supplier,
                    quantity=standard_qty,
                    timing="delayed_3_days",
                    priority="price_timing"
                ))

        return options

    async def _calculate_optimal_quantity(
        self,
        forecast: Dict,
        current_stock: float,
        lead_time: int,
        is_perishable: bool
    ) -> float:
        """
        Calculate optimal order quantity (not fixed buffer)

        Uses dynamic safety stock based on:
        - Forecast confidence
        - Demand variability
        - Lead time uncertainty
        - Perishability
        """
        # Predicted consumption during lead time + delivery buffer
        consumption_during_lead = forecast.predicted_consumption * (lead_time + 2) / 7

        # Dynamic safety stock (not fixed 15%)
        forecast_error = 1 - forecast.confidence_score  # Higher error = more buffer
        demand_variability = forecast.demand_std_dev / forecast.predicted_consumption
        safety_stock_pct = min(0.30, 0.10 + forecast_error + demand_variability)

        # Reduce buffer for perishables (prefer stockout over waste)
        if is_perishable:
            safety_stock_pct *= 0.7

        safety_stock = consumption_during_lead * safety_stock_pct

        # Order quantity = (Consumption + Safety) - Current Stock
        order_qty = max(0, consumption_during_lead + safety_stock - current_stock)

        return order_qty

    async def _evaluate_options(
        self,
        options: List[PurchaseOption],
        context: Dict
    ) -> List[PurchaseDecision]:
        """
        Score each option on multiple criteria
        """
        decisions = []

        for option in options:
            # Get pricing
            price_quote = await self.supplier_service.get_price_quote(
                material_id=context["material"].material_id,
                supplier_id=option.supplier.supplier_id,
                quantity=option.quantity
            )

            # Calculate costs
            total_cost = option.quantity * price_quote.unit_price
            delivery_cost = price_quote.delivery_fee
            total_with_delivery = total_cost + delivery_cost

            # Calculate scores
            cost_score = self._calculate_cost_score(
                total_cost=total_with_delivery,
                budget_available=context["budget_available"],
                historical_avg_price=context["price_history"].avg_price_30d
            )

            quality_score = self._calculate_quality_score(
                supplier=option.supplier,
                quality_history=context["quality_history"]
            )

            urgency_score = self._calculate_urgency_score(
                current_stock=context["current_stock"],
                forecast=context["forecast"],
                lead_time=option.supplier.lead_time_days
            )

            risk_score = self._calculate_risk_score(
                option=option,
                context=context
            )

            # Weighted overall score
            overall_score = (
                cost_score * 0.30 +
                quality_score * 0.25 +
                urgency_score * 0.30 +
                risk_score * 0.15
            )

            # Confidence level
            confidence = self._calculate_confidence(
                overall_score=overall_score,
                data_quality=context["forecast"].confidence_score,
                supplier_reliability=option.supplier.reliability_score
            )

            # Generate reasoning
            reasoning = self._generate_reasoning(
                option=option,
                scores={
                    "cost": cost_score,
                    "quality": quality_score,
                    "urgency": urgency_score,
                    "risk": risk_score
                },
                context=context
            )

            decisions.append(PurchaseDecision(
                material_id=context["material"].material_id,
                material_name=context["material"].material_name,
                quantity_to_order=option.quantity,
                unit=context["material"].unit,
                supplier_id=option.supplier.supplier_id,
                supplier_name=option.supplier.supplier_name,
                unit_price=price_quote.unit_price,
                total_cost=total_with_delivery,
                delivery_date=datetime.utcnow() + timedelta(days=option.supplier.lead_time_days),
                confidence=confidence,
                reasoning=reasoning,
                risk_factors=self._identify_risk_factors(option, context),
                execution_mode=ExecutionMode.AUTONOMOUS  # Will be updated later
            ))

        return decisions

    def _select_best_option(self, decisions: List[PurchaseDecision]) -> PurchaseDecision:
        """
        Select the best decision from evaluated options
        """
        # Sort by confidence * cost_efficiency
        scored = sorted(
            decisions,
            key=lambda d: d.confidence * (1 / d.total_cost),  # Higher confidence, lower cost
            reverse=True
        )
        return scored[0]

    def _determine_execution_mode(
        self,
        decision: PurchaseDecision,
        context: Dict
    ) -> ExecutionMode:
        """
        Decide if AI should execute autonomously or request human review
        """
        # High-risk scenarios → Human review required
        if any([
            decision.total_cost > context["budget_available"] * 0.20,  # >20% of budget
            decision.confidence < 0.70,  # Low confidence
            len(decision.risk_factors) > 3,  # Many risks
            context["material"].is_critical and decision.confidence < 0.85,  # Critical item
            "price_spike" in decision.risk_factors  # Unusual price
        ]):
            return ExecutionMode.HUMAN_REVIEW

        # Medium-risk scenarios → Autonomous if confidence high
        if decision.confidence > 0.90 and decision.total_cost < context["budget_available"] * 0.10:
            return ExecutionMode.AUTONOMOUS

        # Default: Human review
        return ExecutionMode.HUMAN_REVIEW

    # ============================================================================
    # STEP 3: AUTONOMOUS EXECUTION (Closed Loop)
    # ============================================================================

    async def _execute_purchase(self, decision: PurchaseDecision):
        """
        Actually place the order with supplier (not just create a list)
        """
        logger.info(
            f"🤖 AUTONOMOUS EXECUTION: Ordering {decision.quantity_to_order} "
            f"{decision.unit} of {decision.material_name} from {decision.supplier_name}"
        )

        try:
            # Step 1: Place order via supplier API/email
            order_result = await self.supplier_service.place_order(
                supplier_id=decision.supplier_id,
                material_id=decision.material_id,
                quantity=decision.quantity_to_order,
                unit_price=decision.unit_price,
                delivery_date=decision.delivery_date,
                purchase_order_id=self._generate_po_number()
            )

            # Step 2: Create purchase order record
            purchase_order = await self.purchase_order_repository.create({
                "po_number": order_result.po_number,
                "supplier_id": decision.supplier_id,
                "material_id": decision.material_id,
                "quantity": decision.quantity_to_order,
                "unit_price": decision.unit_price,
                "total_cost": decision.total_cost,
                "expected_delivery": decision.delivery_date,
                "status": "pending_delivery",
                "decision_id": decision.decision_id,
                "autonomous": True,  # Flag for tracking
                "created_by": "ai_agent",
                "created_at": datetime.utcnow()
            })

            # Step 3: Start tracking delivery
            await self.execution_tracker.track_order(
                po_number=order_result.po_number,
                expected_delivery=decision.delivery_date
            )

            # Step 4: Notify human (FYI only, not approval)
            await self.notification_service.send_notification(
                user_type="admin",
                message=f"✅ AI placed order: {decision.quantity_to_order} {decision.unit} "
                        f"of {decision.material_name} from {decision.supplier_name}. "
                        f"Expected delivery: {decision.delivery_date.strftime('%Y-%m-%d')}",
                priority="info"
            )

            logger.info(f"✅ Order placed successfully: PO #{order_result.po_number}")

        except Exception as e:
            logger.error(f"❌ Failed to execute purchase: {e}")

            # Fallback: Escalate to human
            await self._escalate_to_human(
                decision=decision,
                reason=f"Execution failed: {str(e)}"
            )

    async def _escalate_to_human(self, decision: PurchaseDecision, reason: Optional[str] = None):
        """
        Create exception for human review (only when needed)
        """
        exception_reason = reason or self._generate_exception_reason(decision)

        exception = await self.exception_repository.create({
            "type": "purchase_decision_review",
            "material_id": decision.material_id,
            "decision": decision,
            "reason": exception_reason,
            "status": "pending_review",
            "created_at": datetime.utcnow()
        })

        # Notify human (urgent if critical item)
        priority = "urgent" if decision.risk_factors else "normal"
        await self.notification_service.send_notification(
            user_type="admin",
            message=f"⚠️ Purchase decision requires review: {decision.material_name}. "
                    f"Reason: {exception_reason}",
            priority=priority
        )

    # ============================================================================
    # STEP 4: MONITORING & TRACKING (Closed Loop Continues)
    # ============================================================================

    async def on_delivery_received(self, event: DeliveryReceivedEvent):
        """
        Triggered when delivery arrives (QR scan, manual entry, etc.)
        """
        po_number = event.po_number
        actual_quantity = event.actual_quantity
        actual_quality = event.quality_rating

        # Get original decision
        purchase_order = await self.purchase_order_repository.get_by_po_number(po_number)
        original_decision = await self.decision_logger.get_decision(purchase_order.decision_id)

        # Measure outcome vs. prediction
        outcome = {
            "ordered_quantity": original_decision.quantity_to_order,
            "received_quantity": actual_quantity,
            "quantity_accuracy": actual_quantity / original_decision.quantity_to_order,
            "quality_rating": actual_quality,
            "delivery_on_time": event.delivered_at <= purchase_order.expected_delivery,
            "actual_cost": event.actual_cost,
            "cost_accuracy": event.actual_cost / original_decision.total_cost
        }

        # Step 5: Learn from outcome
        await self.learning_engine.update_from_outcome(
            decision=original_decision,
            outcome=outcome
        )

        # Alert if major deviation
        if outcome["quantity_accuracy"] < 0.90 or outcome["quality_rating"] < 3.0:
            await self.notification_service.send_notification(
                user_type="admin",
                message=f"⚠️ Delivery issue: {original_decision.material_name} "
                        f"from {original_decision.supplier_name}. "
                        f"Quality: {outcome['quality_rating']}/5, "
                        f"Quantity: {outcome['quantity_accuracy']:.0%} of expected",
                priority="urgent"
            )

    # ============================================================================
    # STEP 5: CONTINUOUS LEARNING (Gets Smarter Over Time)
    # ============================================================================

    async def _update_decision_model(self, outcomes: List[Dict]):
        """
        Called weekly to retrain decision model based on recent outcomes
        """
        # Analyze past 30 days of decisions
        recent_decisions = await self.decision_logger.get_decisions(days=30)

        # Calculate accuracy
        accuracy_metrics = {
            "autonomous_success_rate": self._calc_autonomous_success_rate(recent_decisions),
            "cost_prediction_mape": self._calc_cost_prediction_error(recent_decisions),
            "quality_prediction_mape": self._calc_quality_prediction_error(recent_decisions),
            "delivery_on_time_rate": self._calc_delivery_accuracy(recent_decisions)
        }

        # Adjust confidence thresholds
        if accuracy_metrics["autonomous_success_rate"] > 0.95:
            # Performing well → be more aggressive
            self.confidence_threshold_autonomous -= 0.05
            logger.info("📈 Increasing autonomy: threshold lowered to {:.2f}".format(
                self.confidence_threshold_autonomous
            ))
        elif accuracy_metrics["autonomous_success_rate"] < 0.85:
            # Performing poorly → be more conservative
            self.confidence_threshold_autonomous += 0.05
            logger.info("📉 Reducing autonomy: threshold raised to {:.2f}".format(
                self.confidence_threshold_autonomous
            ))

        # Update supplier reliability scores
        await self._update_supplier_scores(recent_decisions)

        # Log learning progress
        await self.learning_engine.log_learning_cycle(accuracy_metrics)

    async def _update_supplier_scores(self, recent_decisions: List[Dict]):
        """
        Adjust supplier reliability based on recent performance
        """
        for supplier_id in set(d.supplier_id for d in recent_decisions):
            supplier_decisions = [d for d in recent_decisions if d.supplier_id == supplier_id]

            avg_quality = np.mean([d.outcome.quality_rating for d in supplier_decisions if d.outcome])
            on_time_rate = np.mean([d.outcome.delivery_on_time for d in supplier_decisions if d.outcome])
            cost_accuracy = 1 - np.mean([
                abs(d.outcome.actual_cost - d.total_cost) / d.total_cost
                for d in supplier_decisions if d.outcome
            ])

            new_score = (avg_quality / 5.0) * 0.4 + on_time_rate * 0.4 + cost_accuracy * 0.2

            await self.supplier_service.update_reliability_score(supplier_id, new_score)
```

---

## Comparison Summary

| Aspect | Wrapper (Current) | Autonomous (New) |
|--------|-------------------|------------------|
| **Trigger** | Scheduled job (6 AM daily) | Real-time event (inventory change) |
| **Decision** | AI suggests | AI decides + executes |
| **Human role** | Reviews every order | Reviews 10-20% exceptions |
| **Execution** | Human places order | AI places order automatically |
| **Follow-up** | None | AI tracks delivery, learns from outcome |
| **Learning** | None | Improves accuracy over time |
| **Supplier integration** | None | API/email automation |
| **Risk handling** | Human reviews all | AI escalates only high-risk |
| **Time saved** | ~1 hour (reporting) | ~4 hours (operations) |

---

## Frontend Changes: Exception Dashboard vs. Approval Dashboard

### OLD: Approval Dashboard (shows everything)
```tsx
// ApprovalsPage.tsx (current)
// Human reviews 100% of orders

<div className="approvals">
  <h2>Shopping List - {date}</h2>
  <p>{items.length} items require your approval</p>

  {items.map(item => (
    <ItemCard item={item}>
      <Checkbox onChange={() => toggleApproval(item)} />
      <Button onClick={() => approveItem(item)}>Approve</Button>
      <Button onClick={() => rejectItem(item)}>Reject</Button>
    </ItemCard>
  ))}

  <Button onClick={approveAll}>Approve All</Button>
</div>
```

### NEW: Exception Dashboard (shows only issues)
```tsx
// ExceptionDashboard.tsx (new)
// Human reviews only 10-20% exceptions

<div className="exception-dashboard">
  <MetricsRow>
    <Metric label="Orders Today" value={stats.total_orders} color="blue" />
    <Metric label="Autonomous" value={stats.autonomous} color="green" />
    <Metric label="Needs Review" value={stats.exceptions} color="orange" />
    <Metric label="AI Confidence" value={`${stats.avg_confidence}%`} color="green" />
  </MetricsRow>

  <ActivityFeed>
    <h3>Recent AI Actions</h3>
    {recentActions.map(action => (
      <ActivityItem>
        <StatusIcon status={action.status} />
        <span>{action.timestamp}</span>
        <span>AI ordered {action.quantity} {action.material_name}</span>
        <span>from {action.supplier_name}</span>
        <Badge>Confidence: {action.confidence}%</Badge>
      </ActivityItem>
    ))}
  </ActivityFeed>

  <ExceptionsSection>
    <h3>⚠️ Exceptions Requiring Review ({exceptions.length})</h3>
    {exceptions.map(exc => (
      <ExceptionCard>
        <PriorityBadge priority={exc.priority} />
        <h4>{exc.material_name}</h4>
        <ReasonTag>{exc.reason}</ReasonTag>

        <AIRecommendation>
          <p><strong>AI Recommends:</strong></p>
          <p>Order {exc.decision.quantity} {exc.decision.unit} from {exc.decision.supplier_name}</p>
          <p>Cost: ₹{exc.decision.total_cost.toFixed(2)}</p>
          <p>Confidence: {exc.decision.confidence.toFixed(0)}%</p>
        </AIRecommendation>

        <RiskFactors risks={exc.decision.risk_factors} />

        <ActionButtons>
          <Button variant="success" onClick={() => approveException(exc)}>
            ✓ Approve AI Recommendation
          </Button>
          <Button variant="secondary" onClick={() => modifyAndApprove(exc)}>
            ✎ Modify & Approve
          </Button>
          <Button variant="danger" onClick={() => rejectException(exc)}>
            ✗ Reject
          </Button>
        </ActionButtons>
      </ExceptionCard>
    ))}
  </ExceptionsSection>

  <PerformanceInsights>
    <h3>AI Performance (Last 30 Days)</h3>
    <Chart data={performanceData} />
    <Metrics>
      <Metric label="Autonomous Success Rate" value="94%" />
      <Metric label="Cost Accuracy" value="MAPE 8%" />
      <Metric label="On-Time Delivery" value="92%" />
    </Metrics>
  </PerformanceInsights>
</div>
```

---

## Key Architectural Patterns for Autonomous Agents

### 1. Event-Driven, Not Scheduled
```python
# OLD (Wrapper): Run at fixed time
@scheduler.scheduled_job('cron', hour=6, minute=0)
async def generate_shopping_list():
    # Runs whether needed or not
    pass

# NEW (Autonomous): React to events
@event_bus.subscribe("inventory.stock_changed")
async def on_inventory_change(event):
    # Runs only when needed
    if await should_trigger_order(event.material_id):
        await initiate_purchase()
```

### 2. Confidence-Based Execution
```python
decision = await make_decision(context)

if decision.confidence > 0.90 and decision.risk_score < 0.20:
    await execute_autonomously(decision)
else:
    await escalate_to_human(decision)
```

### 3. Closed-Loop Learning
```python
# Decision → Execution → Outcome → Learning
decision = await decide()
result = await execute(decision)
outcome = await measure_outcome(result)
await learn_from_outcome(decision, outcome)
```

### 4. Multi-Agent Coordination
```python
# Purchasing agent talks to pricing agent
async def autonomous_purchase(material_id):
    # Check if pricing agent suggests discount
    pricing_recommendation = await pricing_agent.should_discount(material_id)

    if pricing_recommendation.action == "discount_to_clear_stock":
        # Reduce order quantity (will sell more at discount)
        order_qty *= 0.70
```

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Create `AutonomousPurchasingAgent` class
- [ ] Implement event-driven architecture (EventBus)
- [ ] Build decision framework (confidence, risk scoring)
- [ ] Create exception handling system

### Phase 2: Supplier Integration
- [ ] API integrations with top 3 suppliers
- [ ] Email/SMS automation fallback
- [ ] Order tracking system
- [ ] Delivery confirmation workflow

### Phase 3: Learning Engine
- [ ] Outcome measurement logic
- [ ] Model retraining pipeline
- [ ] Confidence calibration system
- [ ] Performance monitoring dashboard

### Phase 4: Frontend
- [ ] Replace ApprovalsPage with ExceptionDashboard
- [ ] Activity feed showing AI actions
- [ ] Performance insights charts
- [ ] Exception review workflow

---

## Measuring Success

### Business Metrics
- **Time saved:** 4-6 hours/day (vs. 1-2 hours with wrapper)
- **Cost reduction:** 10-15% better pricing (negotiation, timing)
- **Stockout reduction:** 30-40% fewer incidents
- **Waste reduction:** 20-25% less spoilage

### AI Performance Metrics
- **Autonomy rate:** 80-90% of orders placed without human
- **Decision accuracy:** 90%+ correct decisions
- **Confidence calibration:** High confidence → high accuracy
- **Learning rate:** 5-10% improvement per month

### User Experience Metrics
- **Human workload:** 90% reduction in purchasing tasks
- **Exception review time:** <30 min/day (vs. 2 hours for approval)
- **User satisfaction:** "AI does the work, I handle exceptions"

---

This is the transformation from "wrapper" to "reimagined workflow"—AI that works autonomously, learns continuously, and involves humans only when truly needed.
