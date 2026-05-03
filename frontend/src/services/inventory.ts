import axios from './api';
import type {
  InventoryItem,
  InventoryItemCreate,
  InventoryItemUpdate,
  InventoryFilters
} from '../types/inventory';

interface PaginatedResponse {
  success: boolean;
  data: InventoryItem[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}

interface ItemResponse {
  success: boolean;
  data: InventoryItem;
  message: string;
}

interface ItemsResponse {
  success: boolean;
  data: InventoryItem[];
  message: string;
}

export const inventoryService = {
  async getAllItems(
    page: number = 1,
    limit: number = 20,
    filters?: InventoryFilters
  ): Promise<PaginatedResponse> {
    const params: any = { page, limit };
    if (filters?.category) params.category = filters.category;
    if (filters?.is_perishable) params.is_perishable = filters.is_perishable;

    const response = await axios.get('/inventory', { params });
    return response.data;
  },

  async getItem(itemId: string): Promise<ItemResponse> {
    const response = await axios.get(`/inventory/${itemId}`);
    return response.data;
  },

  async createItem(item: InventoryItemCreate): Promise<ItemResponse> {
    const response = await axios.post('/inventory', item);
    return response.data;
  },

  async updateItem(
    itemId: string,
    updates: InventoryItemUpdate
  ): Promise<ItemResponse> {
    const response = await axios.put(`/inventory/${itemId}`, updates);
    return response.data;
  },

  async deleteItem(itemId: string): Promise<{ success: boolean }> {
    const response = await axios.delete(`/inventory/${itemId}`);
    return response.data;
  },

  async getLowStockItems(): Promise<ItemsResponse> {
    const response = await axios.get('/inventory/low-stock');
    return response.data;
  },

  async simulateOrders(): Promise<{ success: boolean; message: string }> {
    const response = await axios.post('/inventory/simulate-orders');
    return response.data;
  }
};
