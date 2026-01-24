/**
 * Orders API service.
 * 
 * Handles all order-related API calls.
 */

import apiClient, { getErrorMessage } from './api';
import {
  Order,
  OrderStatus,
  CreateOrderData,
  KitchenOrders,
} from '../types/orders';

/**
 * API response structure for order endpoints.
 */
interface OrderAPIResponse {
  success: boolean;
  data: Order | KitchenOrders | { waiting: Order[]; next_up: Order[] };
  message: string;
  timestamp: string;
}

/**
 * Create a new order.
 * 
 * Restaurant ID and created_by_user_id are automatically set by the backend.
 * 
 * @param data - Order creation data
 * @returns Promise resolving to created order
 * @throws Error if creation fails
 */
export async function createOrder(data: CreateOrderData): Promise<Order> {
  try {
    const response = await apiClient.post<OrderAPIResponse>('/orders', data);
    return response.data.data as Order;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Send order to kitchen (transition DRAFT → SENT_TO_KITCHEN).
 * 
 * @param orderId - Order database ID
 * @returns Promise resolving to updated order
 * @throws Error if request fails
 */
export async function sendOrderToKitchen(orderId: string): Promise<Order> {
  try {
    const response = await apiClient.post<OrderAPIResponse>(
      `/orders/${orderId}/send-to-kitchen`
    );
    return response.data.data as Order;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Start cooking order (transition SENT_TO_KITCHEN → IN_PROGRESS).
 * 
 * @param orderId - Order database ID
 * @returns Promise resolving to updated order
 * @throws Error if request fails
 */
export async function startCookingOrder(orderId: string): Promise<Order> {
  try {
    const response = await apiClient.post<OrderAPIResponse>(
      `/orders/${orderId}/start-cooking`
    );
    return response.data.data as Order;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Mark order as complete (transition IN_PROGRESS → COMPLETED).
 * 
 * @param orderId - Order database ID
 * @returns Promise resolving to updated order
 * @throws Error if request fails
 */
export async function markOrderComplete(orderId: string): Promise<Order> {
  try {
    const response = await apiClient.post<OrderAPIResponse>(
      `/orders/${orderId}/mark-complete`
    );
    return response.data.data as Order;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Move order back to waiting (transition IN_PROGRESS → SENT_TO_KITCHEN).
 * 
 * @param orderId - Order database ID
 * @returns Promise resolving to updated order
 * @throws Error if request fails
 */
export async function moveOrderToWaiting(orderId: string): Promise<Order> {
  try {
    const response = await apiClient.post<OrderAPIResponse>(
      `/orders/${orderId}/move-to-waiting`
    );
    return response.data.data as Order;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get orders for kitchen view, grouped by status.
 * 
 * Returns orders in SENT_TO_KITCHEN (Waiting) and IN_PROGRESS (Next Up) statuses.
 * 
 * @returns Promise resolving to kitchen orders object
 * @throws Error if request fails
 */
export async function getKitchenOrders(): Promise<KitchenOrders> {
  try {
    const response = await apiClient.get<OrderAPIResponse>('/orders/kitchen');
    const data = response.data.data as { waiting: Order[]; next_up: Order[] };
    return {
      waiting: data.waiting || [],
      next_up: data.next_up || [],
    };
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get a specific order by ID.
 * 
 * @param orderId - Order database ID
 * @returns Promise resolving to order data
 * @throws Error if order not found or request fails
 */
export async function getOrder(orderId: string): Promise<Order> {
  try {
    const response = await apiClient.get<OrderAPIResponse>(`/orders/${orderId}`);
    return response.data.data as Order;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}
