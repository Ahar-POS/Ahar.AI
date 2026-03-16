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

// ============================================================================
// OCR Document Types
// ============================================================================

export enum DocumentType {
  PO = 'PO',
  BILL = 'BILL'
}

export enum DocumentStatus {
  UPLOADING = 'uploading',
  PROCESSING = 'processing',
  PENDING_REVIEW = 'pending_review',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  FAILED = 'failed'
}

export enum MatchStatus {
  EXACT = 'exact',
  UNMATCHED = 'unmatched'
}

export enum POStatus {
  PENDING = 'pending',
  PARTIALLY_RECEIVED = 'partially_received',
  FULLY_RECEIVED = 'fully_received',
  CANCELLED = 'cancelled'
}

export enum BillStatus {
  PENDING_REVIEW = 'pending_review',
  APPROVED = 'approved',
  REJECTED = 'rejected'
}

// Extracted Item from OCR
export interface ExtractedItem {
  material_name: string;
  quantity: number;
  unit: string;
  unit_cost_inr: number;
  line_total_inr?: number;
  confidence_score: number;
  matched_inventory_id: string | null;
  match_status: MatchStatus;
  row_number?: number;
  notes?: string;
}

// Document Upload
export interface DocumentUpload {
  _id: string;
  filename: string;
  file_path: string;
  file_size_bytes: number;
  mime_type: string;
  document_type: DocumentType;
  status: DocumentStatus;
  uploaded_by: string;
  uploaded_by_name?: string;
  ocr_result_id?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

// OCR Result
export interface OCRResult {
  _id: string;
  document_upload_id: string;
  document_type: DocumentType;
  extracted_fields: Record<string, any>;
  extracted_items: ExtractedItem[];
  raw_text?: string;
  processing_time_sec: number;
  ocr_engine: string;
  warnings: string[];
  errors: string[];
  status: DocumentStatus;
  reviewed_by?: string;
  review_notes?: string;
  reviewed_at?: string;
  created_at: string;
  updated_at: string;
}

// Purchase Order Item
export interface PurchaseOrderItem {
  inventory_id: string;
  material_name: string;
  quantity_ordered: number;
  quantity_received: number;
  unit: string;
  unit_cost_inr: number;
  line_total_inr: number;
}

// Purchase Order
export interface PurchaseOrder {
  _id: string;
  po_number: string;
  supplier_id: string;
  supplier_name?: string;
  items: PurchaseOrderItem[];
  po_date?: string;
  expected_delivery_date?: string;
  subtotal_inr: number;
  tax_amount_inr?: number;
  total_amount_inr: number;
  status: POStatus;
  document_upload_id: string;
  ocr_result_id: string;
  created_by: string;
  approved_by?: string;
  approved_at?: string;
  created_at: string;
  updated_at: string;
}

// Bill Item
export interface BillItem {
  inventory_id: string;
  material_name: string;
  quantity: number;
  unit: string;
  unit_cost_inr: number;
  line_total_inr: number;
  price_variance_pct?: number;
  po_unit_cost_inr?: number;
}

// Bill
export interface Bill {
  _id: string;
  invoice_number: string;
  supplier_id: string;
  supplier_name?: string;
  items: BillItem[];
  invoice_date?: string;
  actual_delivery_date?: string;
  subtotal_inr: number;
  tax_amount_inr?: number;
  total_amount_inr: number;
  linked_po_id?: string;
  has_price_discrepancies: boolean;
  price_variance_summary?: {
    has_significant_variances: boolean;
    total_variance_amount_inr: number;
    item_variances: Array<{
      material_name: string;
      po_unit_cost_inr: number;
      bill_unit_cost_inr: number;
      variance_pct: number;
      variance_amount_inr: number;
      quantity: number;
    }>;
    threshold_pct: number;
  };
  status: BillStatus;
  document_upload_id: string;
  ocr_result_id: string;
  inventory_updated: boolean;
  inventory_update_timestamp?: string;
  created_by: string;
  approved_by?: string;
  approved_at?: string;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// API Request/Response Types
// ============================================================================

export interface DocumentUploadResponse {
  upload_id: string;
  ocr_result_id: string | null;
  status: DocumentStatus;
  message: string;
}

export interface OCRApprovalRequest {
  extracted_fields?: Record<string, any>;
  extracted_items?: ExtractedItem[];
  review_notes?: string;
}

export interface OCRApprovalResponse {
  success: boolean;
  message: string;
  po_id: string | null;
  bill_id: string | null;
  inventory_updated_count: number;
  price_variances: Array<{
    material_name: string;
    po_unit_cost_inr: number;
    bill_unit_cost_inr: number;
    variance_pct: number;
    variance_amount_inr: number;
    quantity: number;
  }>;
}

export interface OCRRejectionRequest {
  reason: string;
}

export interface BillStatusUpdateRequest {
  status: BillStatus;
}

export interface OCRSavePendingRequest {
  extracted_fields?: Record<string, any>;
  extracted_items?: ExtractedItem[];
  review_notes?: string;
}

export interface BillReviewRequest {
  items?: BillItem[];
  reason?: string;
}

export interface DocumentHistoryFilter {
  document_type?: DocumentType;
  status?: DocumentStatus;
  start_date?: string;
  end_date?: string;
  uploaded_by?: string;
}

export interface PurchaseOrderFilter {
  supplier_id?: string;
  status?: POStatus;
  start_date?: string;
  end_date?: string;
}

export interface BillFilter {
  supplier_id?: string;
  status?: BillStatus;
  has_price_discrepancies?: boolean;
  linked_po_id?: string;
  start_date?: string;
  end_date?: string;
}
