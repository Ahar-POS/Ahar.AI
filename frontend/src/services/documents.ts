/**
 * API service for document upload and OCR operations.
 */
import api from './api';
import type { APIResponse, PaginatedResponse } from '../types/api';
import type {
  Bill,
  BillFilter,
  DocumentHistoryFilter,
  DocumentType,
  DocumentUpload,
  DocumentUploadResponse,
  OCRApprovalRequest,
  OCRApprovalResponse,
  BillStatusUpdateRequest,
  OCRSavePendingRequest,
  BillReviewRequest,
  OCRRejectionRequest,
  OCRResult,
  PurchaseOrder,
  PurchaseOrderFilter
} from '../types/inventory';

/**
 * Upload a document for OCR processing.
 */
export const uploadDocument = async (
  file: File,
  documentType: DocumentType
): Promise<DocumentUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', documentType);

  const response = await api.post<APIResponse<DocumentUploadResponse>>(
    '/documents/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }
  );

  return response.data.data;
};

/**
 * Get OCR results pending review.
 */
export const getPendingReviews = async (limit: number = 50): Promise<OCRResult[]> => {
  const response = await api.get<APIResponse<OCRResult[]>>('/documents/pending', {
    params: { limit }
  });

  return response.data.data;
};

/**
 * Get OCR result details by ID.
 */
export const getOCRResult = async (docId: string): Promise<OCRResult> => {
  const response = await api.get<APIResponse<OCRResult>>(`/documents/${docId}`);
  return response.data.data;
};

/**
 * Approve OCR result with optional edits.
 */
export const approveOCRResult = async (
  docId: string,
  request: OCRApprovalRequest
): Promise<OCRApprovalResponse> => {
  const response = await api.post<APIResponse<OCRApprovalResponse>>(
    `/documents/${docId}/approve`,
    request
  );

  return response.data.data;
};

/**
 * Reject OCR result with reason.
 */
export const rejectOCRResult = async (
  docId: string,
  request: OCRRejectionRequest
): Promise<{ success: boolean; message: string }> => {
  const response = await api.post<APIResponse<{ success: boolean; message: string }>>(
    `/documents/${docId}/reject`,
    request
  );

  return response.data.data;
};

/**
 * Save OCR review as pending (without approve/reject).
 */
export const saveOCRAsPending = async (
  docId: string,
  request: OCRSavePendingRequest
): Promise<{ bill_id?: string }> => {
  const response = await api.post<APIResponse<{ bill_id?: string }>>(
    `/documents/${docId}/save-pending`,
    request
  );
  return response.data.data;
};

/**
 * Discard uploaded document and related OCR data.
 */
export const discardUploadedDocument = async (docId: string): Promise<void> => {
  await api.delete(`/documents/${docId}/discard`);
};

/**
 * Get paginated document upload history.
 */
export const getDocumentHistory = async (
  page: number = 1,
  limit: number = 20,
  filters?: DocumentHistoryFilter
): Promise<{
  data: DocumentUpload[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}> => {
  const params: Record<string, any> = { page, limit };

  if (filters) {
    if (filters.document_type) params.document_type = filters.document_type;
    if (filters.status) params.status = filters.status;
    if (filters.start_date) params.start_date = filters.start_date;
    if (filters.end_date) params.end_date = filters.end_date;
    if (filters.uploaded_by) params.uploaded_by = filters.uploaded_by;
  }

  const response = await api.get<PaginatedResponse<DocumentUpload>>('/documents/history/list', { params });

  return response.data;
};

/**
 * Get paginated list of purchase orders.
 */
export const getPurchaseOrders = async (
  page: number = 1,
  limit: number = 20,
  filters?: PurchaseOrderFilter
): Promise<{
  data: PurchaseOrder[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}> => {
  const params: Record<string, any> = { page, limit };

  if (filters) {
    if (filters.supplier_id) params.supplier_id = filters.supplier_id;
    if (filters.status) params.status = filters.status;
    if (filters.start_date) params.start_date = filters.start_date;
    if (filters.end_date) params.end_date = filters.end_date;
  }

  const response = await api.get<PaginatedResponse<PurchaseOrder>>('/documents/purchase-orders/list', { params });

  return response.data;
};

/**
 * Get paginated list of bills.
 */
export const getBills = async (
  page: number = 1,
  limit: number = 20,
  filters?: BillFilter
): Promise<{
  data: Bill[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}> => {
  const params: Record<string, any> = { page, limit };

  if (filters) {
    if (filters.supplier_id) params.supplier_id = filters.supplier_id;
    if (filters.status) params.status = filters.status;
    if (filters.has_price_discrepancies !== undefined) {
      params.has_price_discrepancies = filters.has_price_discrepancies;
    }
    if (filters.linked_po_id) params.linked_po_id = filters.linked_po_id;
    if (filters.start_date) params.start_date = filters.start_date;
    if (filters.end_date) params.end_date = filters.end_date;
  }

  const response = await api.get<PaginatedResponse<Bill>>('/documents/bills/list', { params });

  return response.data;
};

/**
 * Update bill status.
 */
export const updateBillStatus = async (
  billId: string,
  request: BillStatusUpdateRequest
): Promise<Bill> => {
  const response = await api.patch<APIResponse<Bill>>(
    `/documents/bills/${billId}/status`,
    request
  );
  return response.data.data;
};

/**
 * Approve pending bill from Bills tab.
 */
export const approvePendingBill = async (
  billId: string,
  request: BillReviewRequest
): Promise<{ inventory_updated_count: number }> => {
  const response = await api.post<APIResponse<{ inventory_updated_count: number }>>(
    `/documents/bills/${billId}/approve`,
    request
  );
  return response.data.data;
};

/**
 * Reject pending bill from Bills tab.
 */
export const rejectPendingBill = async (
  billId: string,
  request: BillReviewRequest
): Promise<void> => {
  await api.post(`/documents/bills/${billId}/reject`, request);
};

/**
 * Format currency from paise to rupees with symbol.
 */
export const formatCurrency = (amountInPaise: number): string => {
  const rupees = amountInPaise / 100;
  return `₹${rupees.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;
};

/**
 * Format date from ISO string to display format.
 */
export const formatDate = (dateString: string | undefined): string => {
  if (!dateString) return 'N/A';

  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  } catch {
    return 'Invalid Date';
  }
};

/**
 * Get status badge color based on document status.
 */
export const getStatusColor = (
  status?: string
): 'primary' | 'success' | 'warning' | 'error' | 'default' => {
  switch (status || 'pending_review') {
    case 'approved':
    case 'fully_received':
      return 'success';
    case 'pending':
    case 'pending_review':
    case 'partially_received':
      return 'warning';
    case 'processing':
    case 'uploading':
      return 'primary';
    case 'rejected':
    case 'failed':
    case 'cancelled':
      return 'error';
    default:
      return 'default';
  }
};

/**
 * Get status display label.
 */
export const getStatusLabel = (status: string): string => {
  return (status || 'pending_review')
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};
