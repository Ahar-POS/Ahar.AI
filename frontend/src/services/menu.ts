/**
 * Menu API service.
 * 
 * Handles all menu item-related API calls.
 */

import apiClient, { getErrorMessage } from './api';
import {
  MenuItem,
  IngredientTag,
  PrepType,
  CreateMenuItemData,
  UpdateMenuItemData,
} from '../types/menu';

/**
 * API response structure for menu endpoints.
 */
interface MenuAPIResponse {
  success: boolean;
  data: MenuItem | MenuItem[] | string[];
  message: string;
  timestamp: string;
}

/**
 * Normalize a menu item so it always has `id` and `price` (backend may send `_id`/`id`, `price`/`price_amount`).
 * Price is stored in paise; ensure it's a number for display and totals.
 */
function normalizeMenuItem(item: Record<string, unknown>): MenuItem {
  const id = (item.id as string) ?? (item._id as string) ?? '';
  const rawPrice = item.price ?? item.price_amount;
  let price = 0;
  if (typeof rawPrice === 'number' && !Number.isNaN(rawPrice)) {
    price = Math.max(0, Math.round(rawPrice));
  } else if (typeof rawPrice === 'string') {
    const parsed = parseFloat(rawPrice);
    price = Number.isNaN(parsed) ? 0 : Math.max(0, Math.round(parsed));
  }
  return { ...item, id, price } as MenuItem;
}

/**
 * Extract array from API response body (handles both { data: [] } and raw array).
 */
function extractDataArray<T>(body: unknown): T[] {
  if (Array.isArray(body)) return body as T[];
  const data = (body as { data?: unknown })?.data;
  return Array.isArray(data) ? (data as T[]) : [];
}

/**
 * Get all menu items for the authenticated user's restaurant.
 * 
 * @param includeInactive - Whether to include inactive items
 * @param category - Optional category filter
 * @returns Promise resolving to array of menu items
 * @throws Error if request fails
 */
export async function getMenuItems(
  includeInactive = false,
  category?: string
): Promise<MenuItem[]> {
  try {
    const params: Record<string, string | boolean> = {
      include_inactive: includeInactive,
    };
    
    if (category) {
      params.category = category;
    }
    
    const response = await apiClient.get<MenuAPIResponse>('/menu/items', {
      params,
    });
    
    const raw = response.data;
    const list = extractDataArray<Record<string, unknown>>(raw);
    return list.map((item) => normalizeMenuItem(item));
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get all unique menu categories.
 * 
 * @returns Promise resolving to array of category names
 * @throws Error if request fails
 */
export async function getCategories(): Promise<string[]> {
  try {
    const response = await apiClient.get<MenuAPIResponse>('/menu/items/categories');
    return extractDataArray<string>(response.data);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get a specific menu item by ID.
 * 
 * @param itemId - Menu item database ID
 * @returns Promise resolving to menu item data
 * @throws Error if item not found or request fails
 */
export async function getMenuItem(itemId: string): Promise<MenuItem> {
  try {
    const response = await apiClient.get<MenuAPIResponse>(`/menu/items/${itemId}`);
    const raw = (response.data as { data?: Record<string, unknown> })?.data;
    if (!raw || typeof raw !== 'object') {
      throw new Error('Invalid menu item response');
    }
    return normalizeMenuItem(raw);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Create a new menu item.
 * 
 * @param data - Menu item creation data
 * @returns Promise resolving to created menu item
 * @throws Error if creation fails
 */
export async function createMenuItem(data: CreateMenuItemData): Promise<MenuItem> {
  try {
    const response = await apiClient.post<MenuAPIResponse>('/menu/items', data);
    const raw = (response.data as { data?: Record<string, unknown> })?.data;
    if (!raw || typeof raw !== 'object') {
      throw new Error('Invalid menu item response');
    }
    return normalizeMenuItem(raw);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Update menu item details.
 * 
 * @param itemId - Menu item database ID
 * @param data - Fields to update
 * @returns Promise resolving to updated menu item
 * @throws Error if update fails
 */
export async function updateMenuItem(
  itemId: string,
  data: UpdateMenuItemData
): Promise<MenuItem> {
  try {
    const response = await apiClient.put<MenuAPIResponse>(`/menu/items/${itemId}`, data);
    const raw = (response.data as { data?: Record<string, unknown> })?.data;
    if (!raw || typeof raw !== 'object') {
      throw new Error('Invalid menu item response');
    }
    return normalizeMenuItem(raw);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Delete a menu item (soft delete).
 * 
 * @param itemId - Menu item database ID
 * @returns Promise resolving when deletion is complete
 * @throws Error if deletion fails
 */
export async function deleteMenuItem(itemId: string): Promise<void> {
  try {
    await apiClient.delete(`/menu/items/${itemId}`);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}
