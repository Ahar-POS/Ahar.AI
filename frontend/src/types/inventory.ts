export interface InventoryItem {
  _id: string;
  material_id: string;
  material_name: string;
  category: string;
  unit: string;
  unit_cost_inr: number;
  reorder_level: number;
  reorder_qty: number;
  current_stock: number;
  max_stock: number;
  lead_time_days: number;
  supplier_id: string;
  last_restock_date: string | null;
  shelf_life_days: number;
  storage_temp_c: string;
  is_perishable: string;
  created_at?: string;
  updated_at?: string;
}

export interface InventoryItemCreate {
  material_id: string;
  material_name: string;
  category: string;
  unit: string;
  unit_cost_inr: number;
  reorder_level: number;
  reorder_qty: number;
  current_stock: number;
  max_stock: number;
  lead_time_days: number;
  supplier_id: string;
  last_restock_date?: string | null;
  shelf_life_days: number;
  storage_temp_c: string;
  is_perishable: string;
}

export interface InventoryItemUpdate {
  material_name?: string;
  category?: string;
  unit?: string;
  unit_cost_inr?: number;
  reorder_level?: number;
  reorder_qty?: number;
  current_stock?: number;
  max_stock?: number;
  lead_time_days?: number;
  supplier_id?: string;
  last_restock_date?: string | null;
  shelf_life_days?: number;
  storage_temp_c?: string;
  is_perishable?: string;
}

export interface InventoryFilters {
  category?: string;
  is_perishable?: string;
}
