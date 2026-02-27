/**
 * Table-related TypeScript types.
 */

/**
 * Table status enumeration.
 */
export enum TableStatus {
  AVAILABLE = 'available',
  OCCUPIED = 'occupied',
  RESERVED = 'reserved',
  CLOSED = 'closed',
}

/**
 * Table status display labels.
 */
export const TABLE_STATUS_LABELS: Record<TableStatus, string> = {
  [TableStatus.AVAILABLE]: 'Available',
  [TableStatus.OCCUPIED]: 'Occupied',
  [TableStatus.RESERVED]: 'Reserved',
  [TableStatus.CLOSED]: 'Closed',
};

/**
 * Table status colors for UI badges.
 */
export const TABLE_STATUS_COLORS: Record<TableStatus, string> = {
  [TableStatus.AVAILABLE]: '#059669', // Muted green
  [TableStatus.OCCUPIED]: '#be123c', // Muted red
  [TableStatus.RESERVED]: '#b45309', // Muted orange
  [TableStatus.CLOSED]: '#4b5563', // Gray
};

/**
 * Table data structure.
 */
export interface Table {
  id: string;
  table_number: number;
  location: string;
  capacity: number;
  status: TableStatus;
  is_active: boolean;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
}

/**
 * Data for creating a new table.
 * 
 * Note: created_by_user_id is automatically set by the backend.
 */
export interface CreateTableData {
  table_number: number;
  location: string;
  capacity: number;
  status: TableStatus;
  // created_by_user_id is set automatically by the backend
}

/**
 * Data for updating an existing table.
 */
export interface UpdateTableData {
  location?: string;
  capacity?: number;
  status?: TableStatus;
  is_active?: boolean;
}

/**
 * Table summary statistics.
 */
export interface TableStats {
  total: number;
  available: number;
  occupied: number;
  reserved: number;
  closed: number;
}
