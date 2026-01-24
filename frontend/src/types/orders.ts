/**
 * Order-related TypeScript types.
 */

/**
 * Order type enumeration.
 */
export enum OrderType {
  DINE_IN = 'dine_in',
  TAKEAWAY = 'takeaway',
}

/**
 * Order status enumeration.
 */
export enum OrderStatus {
  DRAFT = 'draft',
  SENT_TO_KITCHEN = 'sent_to_kitchen',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled',
}

/**
 * Order item status enumeration.
 */
export enum OrderItemStatus {
  PENDING = 'pending',
  COOKING = 'cooking',
  READY = 'ready',
}

/**
 * Order status display labels.
 */
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  [OrderStatus.DRAFT]: 'Draft',
  [OrderStatus.SENT_TO_KITCHEN]: 'Waiting',
  [OrderStatus.IN_PROGRESS]: 'In Progress',
  [OrderStatus.COMPLETED]: 'Completed',
  [OrderStatus.CANCELLED]: 'Cancelled',
};

/**
 * Order item data structure.
 */
export interface OrderItem {
  menu_item_id: string;
  name_snapshot: string;
  price_snapshot: number; // Price in cents
  quantity: number;
  notes?: string;
  status: OrderItemStatus;
}

/**
 * Order data structure.
 */
export interface Order {
  id: string;
  restaurant_id: string;
  order_number: number;
  order_type: OrderType;
  table_id?: string;
  table_number?: number;
  table_location?: string;
  status: OrderStatus;
  items: OrderItem[];
  total_amount: number; // Total in cents
  created_by_user_id: string;
  created_at: string;
  sent_to_kitchen_at?: string;
  completed_at?: string;
}

/**
 * Data for creating a new order item (before sending to kitchen).
 */
export interface CreateOrderItem {
  menu_item_id: string;
  quantity: number;
  notes?: string;
}

/**
 * Data for creating a new order.
 * 
 * Note: restaurant_id and created_by_user_id are automatically set by the backend.
 */
export interface CreateOrderData {
  order_type?: OrderType;
  table_id?: string;
  items: CreateOrderItem[];
}

/**
 * Kitchen orders response structure.
 */
export interface KitchenOrders {
  waiting: Order[];
  next_up: Order[];
}
