"""
Order service for business logic and validation.

Handles order creation, validation, and status transitions.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.models.menu_item import MenuItemInDB
from app.models.order import (
    OrderCreate,
    OrderInDB,
    OrderItem,
    OrderResponse,
    OrderStatus,
    OrderSummary,
)
from app.models.table import TableInDB
from app.repositories.menu_repository import MenuRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.table_repository import TableRepository
from app.services.inventory_service import inventory_service

logger = logging.getLogger(__name__)


class OrderServiceError(Exception):
    """Custom exception for order service errors."""
    
    def __init__(self, message: str, code: str = "ORDER_SERVICE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class OrderService:
    """Service for order business logic."""

    def __init__(
        self,
        order_repo: OrderRepository,
        menu_repo: MenuRepository,
        table_repo: TableRepository,
    ):
        """
        Initialize order service.
        
        Args:
            order_repo: Order repository instance.
            menu_repo: Menu repository instance.
            table_repo: Table repository instance.
        """
        self.order_repo = order_repo
        self.menu_repo = menu_repo
        self.table_repo = table_repo

    def _generate_order_number(self) -> int:
        """
        Generate timestamp-based order number.
        
        Uses Unix timestamp in seconds as order number.
        This ensures uniqueness and provides chronological ordering.
        
        Returns:
            int: Order number (Unix timestamp).
        """
        return int(datetime.now(timezone.utc).timestamp())

    async def _validate_order_items(
        self,
        items: List[OrderItem],
        restaurant_id: str
    ) -> List[MenuItemInDB]:
        """
        Validate order items and fetch menu item details.
        
        Works with OrderItem objects that may have empty snapshots (from API input).
        """
        """
        Validate order items and fetch menu item details.
        
        Args:
            items: List of order items to validate.
            restaurant_id: Restaurant identifier for validation.
            
        Returns:
            List of MenuItemInDB objects corresponding to the order items.
            
        Raises:
            OrderServiceError: If validation fails.
        """
        if not items:
            raise OrderServiceError("Order must contain at least one item", "EMPTY_ORDER")
        
        menu_items = []
        menu_item_ids = set()
        
        for item in items:
            # Check for duplicate menu items
            if item.menu_item_id in menu_item_ids:
                raise OrderServiceError(
                    f"Duplicate menu item: {item.menu_item_id}",
                    "DUPLICATE_ITEM"
                )
            menu_item_ids.add(item.menu_item_id)
            
            # Validate quantity
            if item.quantity < 1:
                raise OrderServiceError(
                    f"Invalid quantity for item {item.menu_item_id}: {item.quantity}",
                    "INVALID_QUANTITY"
                )
            
            # Fetch menu item
            menu_item = await self.menu_repo.get_by_id(item.menu_item_id)
            
            if not menu_item:
                raise OrderServiceError(
                    f"Menu item not found: {item.menu_item_id}",
                    "ITEM_NOT_FOUND"
                )
            
            # Check if item is available
            if not menu_item.is_available:
                raise OrderServiceError(
                    f"Menu item is not available: {menu_item.name}",
                    "ITEM_UNAVAILABLE"
                )
            
            # Check if item is active
            if not menu_item.is_active:
                raise OrderServiceError(
                    f"Menu item is inactive: {menu_item.name}",
                    "ITEM_INACTIVE"
                )
            
            menu_items.append(menu_item)
        
        return menu_items

    async def _prepare_order_items(
        self,
        items: List[OrderItem],
        menu_items: List[MenuItemInDB]
    ) -> List[OrderItem]:
        """
        Prepare order items with snapshots from menu items.
        
        Args:
            items: Order items with menu_item_id and quantity.
            menu_items: Corresponding menu item data.
            
        Returns:
            List of OrderItem with snapshots populated.
        """
        menu_item_map = {item.id: item for item in menu_items}
        prepared_items = []
        
        for item in items:
            menu_item = menu_item_map[item.menu_item_id]
            
            # Create item with snapshots
            prepared_item = OrderItem(
                menu_item_id=item.menu_item_id,
                name_snapshot=menu_item.name,
                price_snapshot=menu_item.price,
                quantity=item.quantity,
                notes=item.notes,
                status=item.status,
            )
            prepared_items.append(prepared_item)
        
        return prepared_items

    def _calculate_total(self, items: List[OrderItem]) -> int:
        """
        Calculate total order amount in cents.
        
        Args:
            items: List of order items with price snapshots.
            
        Returns:
            Total amount in cents.
        """
        return sum(item.price_snapshot * item.quantity for item in items)

    async def create_order(
        self,
        order_data: OrderCreate,
        restaurant_id: str
    ) -> OrderInDB:
        """
        Create a new order with validation.
        
        Args:
            order_data: Order creation data.
            restaurant_id: Restaurant identifier (from authenticated user).
            
        Returns:
            OrderInDB: Created order.
            
        Raises:
            OrderServiceError: If validation fails.
        """
        # Validate and fetch menu items
        menu_items = await self._validate_order_items(order_data.items, restaurant_id)
        
        # Prepare order items with snapshots
        prepared_items = await self._prepare_order_items(order_data.items, menu_items)
        
        # Calculate total
        total_amount = self._calculate_total(prepared_items)
        
        # Validate table if provided
        if order_data.table_id:
            table = await self.table_repo.get_by_id(order_data.table_id)
            if not table:
                raise OrderServiceError(
                    f"Table not found: {order_data.table_id}",
                    "TABLE_NOT_FOUND"
                )
        
        # Generate order number
        order_number = self._generate_order_number()
        
        # Create order with prepared data
        order_create = OrderCreate(
            restaurant_id=restaurant_id,
            order_type=order_data.order_type,
            table_id=order_data.table_id,
            status=order_data.status,
            items=prepared_items,
            total_amount=total_amount,
            created_by_user_id=order_data.created_by_user_id,
        )
        
        # Create order in database
        order = await self.order_repo.create(order_create, order_number)
        
        # Update table status to OCCUPIED if table_id is provided
        if order_data.table_id:
            from app.models.table import TableStatus
            await self.table_repo.update_status(
                order_data.table_id,
                TableStatus.OCCUPIED
            )
        
        return order

    async def send_to_kitchen(
        self,
        order_id: str,
        restaurant_id: str
    ) -> OrderInDB:
        """
        Send order to kitchen (transition DRAFT → SENT_TO_KITCHEN).
        
        Args:
            order_id: Order ID.
            restaurant_id: Restaurant identifier for authorization.
            
        Returns:
            OrderInDB: Updated order.
            
        Raises:
            OrderServiceError: If order not found or invalid transition.
        """
        order = await self.order_repo.get_by_id(order_id)
        
        if not order:
            raise OrderServiceError("Order not found", "NOT_FOUND")
        
        if order.restaurant_id != restaurant_id:
            raise OrderServiceError("Unauthorized access", "UNAUTHORIZED")
        
        if order.status != OrderStatus.DRAFT:
            raise OrderServiceError(
                f"Cannot send order to kitchen. Current status: {order.status.value}",
                "INVALID_STATUS"
            )
        
        updated_order = await self.order_repo.update_status(
            order_id,
            OrderStatus.SENT_TO_KITCHEN,
            restaurant_id
        )
        
        if not updated_order:
            raise OrderServiceError("Failed to update order status", "UPDATE_FAILED")
        
        return updated_order

    async def start_cooking(
        self,
        order_id: str,
        restaurant_id: str
    ) -> OrderInDB:
        """
        Start cooking order (transition SENT_TO_KITCHEN → IN_PROGRESS).
        
        Args:
            order_id: Order ID.
            restaurant_id: Restaurant identifier for authorization.
            
        Returns:
            OrderInDB: Updated order.
            
        Raises:
            OrderServiceError: If order not found or invalid transition.
        """
        order = await self.order_repo.get_by_id(order_id)
        
        if not order:
            raise OrderServiceError("Order not found", "NOT_FOUND")
        
        if order.restaurant_id != restaurant_id:
            raise OrderServiceError("Unauthorized access", "UNAUTHORIZED")
        
        if order.status != OrderStatus.SENT_TO_KITCHEN:
            raise OrderServiceError(
                f"Cannot start cooking. Current status: {order.status.value}",
                "INVALID_STATUS"
            )
        
        updated_order = await self.order_repo.update_status(
            order_id,
            OrderStatus.IN_PROGRESS,
            restaurant_id
        )
        
        if not updated_order:
            raise OrderServiceError("Failed to update order status", "UPDATE_FAILED")
        
        return updated_order

    async def mark_complete(
        self,
        order_id: str,
        restaurant_id: str
    ) -> OrderInDB:
        """
        Mark order as complete (transition IN_PROGRESS → COMPLETED).

        Also deducts inventory for all menu items in the order.

        Args:
            order_id: Order ID.
            restaurant_id: Restaurant identifier for authorization.

        Returns:
            OrderInDB: Updated order.

        Raises:
            OrderServiceError: If order not found or invalid transition.
        """
        order = await self.order_repo.get_by_id(order_id)

        if not order:
            raise OrderServiceError("Order not found", "NOT_FOUND")

        if order.restaurant_id != restaurant_id:
            raise OrderServiceError("Unauthorized access", "UNAUTHORIZED")

        if order.status != OrderStatus.IN_PROGRESS:
            raise OrderServiceError(
                f"Cannot mark complete. Current status: {order.status.value}",
                "INVALID_STATUS"
            )

        # Update order status first
        updated_order = await self.order_repo.update_status(
            order_id,
            OrderStatus.COMPLETED,
            restaurant_id
        )

        if not updated_order:
            raise OrderServiceError("Failed to update order status", "UPDATE_FAILED")

        # Consume inventory for this order
        try:
            order_items = [
                {"menu_item_id": item.menu_item_id, "quantity": item.quantity}
                for item in order.items
            ]

            consumption_result = await inventory_service.consume_for_order(
                order_items,
                order_id=order.id,
                order_number=order.order_number,
                restaurant_id=restaurant_id,
                check_stock=False  # Don't block on insufficient stock
            )

            # Log warnings if any
            if consumption_result["warnings"]:
                for warning in consumption_result["warnings"]:
                    logger.warning(f"Order {order.order_number} inventory: {warning}")

            # Log errors if any
            if consumption_result["errors"]:
                for error in consumption_result["errors"]:
                    logger.error(f"Order {order.order_number} inventory: {error}")

            # Log success
            if consumption_result["success"]:
                consumed_count = len(consumption_result["consumed"])
                logger.info(
                    f"Order {order.order_number} completed: "
                    f"Consumed {consumed_count} inventory items"
                )

        except Exception as e:
            # Log inventory error but don't fail the order completion
            logger.error(
                f"Failed to consume inventory for order {order.order_number}: {e}",
                exc_info=True
            )

        return updated_order

    async def move_to_waiting(
        self,
        order_id: str,
        restaurant_id: str
    ) -> OrderInDB:
        """
        Move order back to waiting (transition IN_PROGRESS → SENT_TO_KITCHEN).
        
        Args:
            order_id: Order ID.
            restaurant_id: Restaurant identifier for authorization.
            
        Returns:
            OrderInDB: Updated order.
            
        Raises:
            OrderServiceError: If order not found or invalid transition.
        """
        order = await self.order_repo.get_by_id(order_id)
        
        if not order:
            raise OrderServiceError("Order not found", "NOT_FOUND")
        
        if order.restaurant_id != restaurant_id:
            raise OrderServiceError("Unauthorized access", "UNAUTHORIZED")
        
        if order.status != OrderStatus.IN_PROGRESS:
            raise OrderServiceError(
                f"Cannot move to waiting. Current status: {order.status.value}",
                "INVALID_STATUS"
            )
        
        updated_order = await self.order_repo.update_status(
            order_id,
            OrderStatus.SENT_TO_KITCHEN,
            restaurant_id
        )
        
        if not updated_order:
            raise OrderServiceError("Failed to update order status", "UPDATE_FAILED")
        
        return updated_order

    def _calculate_wait_time_minutes(
        self,
        sent_to_kitchen_at: Optional[datetime]
    ) -> Optional[int]:
        """
        Calculate wait time in minutes since order was sent to kitchen.
        
        Args:
            sent_to_kitchen_at: Timestamp when order was sent to kitchen.
            
        Returns:
            Wait time in minutes, or None if not sent to kitchen yet.
        """
        if not sent_to_kitchen_at:
            return None
        
        now = datetime.now(timezone.utc)
        if sent_to_kitchen_at.tzinfo is None:
            # Handle naive datetime (shouldn't happen, but defensive)
            sent_to_kitchen_at = sent_to_kitchen_at.replace(tzinfo=timezone.utc)
        
        delta = now - sent_to_kitchen_at
        return int(delta.total_seconds() / 60)

    async def get_kitchen_orders(
        self,
        restaurant_id: str
    ) -> tuple[List[OrderInDB], List[OrderInDB]]:
        """
        Get orders for kitchen view, grouped by status.
        
        Args:
            restaurant_id: Restaurant identifier.
            
        Returns:
            Tuple of (waiting_orders, next_up_orders).
        """
        waiting = await self.order_repo.get_by_status(
            restaurant_id,
            OrderStatus.SENT_TO_KITCHEN
        )
        
        next_up = await self.order_repo.get_by_status(
            restaurant_id,
            OrderStatus.IN_PROGRESS
        )
        
        return (waiting, next_up)

    async def to_order_response(self, order: OrderInDB) -> OrderResponse:
        """
        Convert OrderInDB to OrderResponse with calculated wait time and table information.
        
        Args:
            order: Order from database.
            
        Returns:
            OrderResponse: Order response with table information populated if table_id exists.
        """
        table_number = None
        table_location = None
        
        # Fetch table information if table_id exists
        if order.table_id:
            table = await self.table_repo.get_by_id(order.table_id)
            if table:
                table_number = table.table_number
                table_location = table.location
        
        return OrderResponse(
            id=order.id,
            restaurant_id=order.restaurant_id,
            order_number=order.order_number,
            order_type=order.order_type,
            table_id=order.table_id,
            table_number=table_number,
            table_location=table_location,
            status=order.status,
            items=order.items,
            total_amount=order.total_amount,
            created_by_user_id=order.created_by_user_id,
            created_at=order.created_at,
            sent_to_kitchen_at=order.sent_to_kitchen_at,
            completed_at=order.completed_at,
        )

    def to_order_summary(
        self,
        order: OrderInDB
    ) -> OrderSummary:
        """
        Convert OrderInDB to OrderSummary with calculated wait time.
        
        Args:
            order: Order from database.
            
        Returns:
            OrderSummary: Lightweight order summary.
        """
        wait_time = self._calculate_wait_time_minutes(order.sent_to_kitchen_at)
        
        return OrderSummary(
            id=order.id,
            order_number=order.order_number,
            table_id=order.table_id,
            status=order.status,
            item_count=len(order.items),
            total_amount=order.total_amount,
            created_at=order.created_at,
            wait_time_minutes=wait_time,
        )
