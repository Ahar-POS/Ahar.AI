"""
Data models for OCR document processing, purchase orders, and bills.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.common import PyObjectId


class DocumentType(str, Enum):
    """Type of document being processed."""
    PURCHASE_ORDER = "PO"
    BILL = "BILL"


class DocumentStatus(str, Enum):
    """Status of document processing."""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class MatchStatus(str, Enum):
    """Status of item matching to inventory."""
    EXACT = "exact"
    UNMATCHED = "unmatched"


class POStatus(str, Enum):
    """Status of purchase order."""
    PENDING = "pending"
    PARTIALLY_RECEIVED = "partially_received"
    FULLY_RECEIVED = "fully_received"
    CANCELLED = "cancelled"


class BillStatus(str, Enum):
    """Status of bill."""
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


# ============================================================================
# Extracted Item Models
# ============================================================================

class ExtractedItem(BaseModel):
    """Item extracted from OCR processing."""
    material_name: str = Field(..., description="Name of the material/item")
    quantity: float = Field(..., gt=0, description="Quantity ordered/delivered")
    unit: str = Field(..., description="Unit of measurement (kg, liters, units, etc.)")
    unit_cost_inr: int = Field(..., description="Unit cost in paise (smallest currency unit)")
    line_total_inr: Optional[int] = Field(None, description="Line total in paise")
    confidence_score: float = Field(..., ge=0, le=1, description="OCR confidence (0-1)")
    matched_inventory_id: Optional[str] = Field(None, description="ID of matched inventory item")
    match_status: MatchStatus = Field(default=MatchStatus.UNMATCHED, description="Matching status")
    row_number: Optional[int] = Field(None, description="Row number in original document")
    notes: Optional[str] = Field(None, description="Additional notes or corrections")

    class Config:
        use_enum_values = True


class PurchaseOrderItem(BaseModel):
    """Item in a purchase order."""
    inventory_id: str = Field(..., description="ID of inventory item")
    material_name: str = Field(..., description="Name of the material")
    quantity_ordered: float = Field(..., gt=0, description="Quantity ordered")
    quantity_received: float = Field(default=0, ge=0, description="Quantity received so far")
    unit: str = Field(..., description="Unit of measurement")
    unit_cost_inr: int = Field(..., description="Expected unit cost in paise")
    line_total_inr: int = Field(..., description="Line total in paise")


class BillItem(BaseModel):
    """Item in a bill/invoice."""
    inventory_id: str = Field(..., description="ID of inventory item")
    material_name: str = Field(..., description="Name of the material")
    quantity: float = Field(..., gt=0, description="Quantity delivered")
    unit: str = Field(..., description="Unit of measurement")
    unit_cost_inr: int = Field(..., description="Actual unit cost in paise")
    line_total_inr: int = Field(..., description="Line total in paise")
    price_variance_pct: Optional[float] = Field(None, description="Price variance % compared to PO")
    po_unit_cost_inr: Optional[int] = Field(None, description="PO unit cost for comparison")


# ============================================================================
# Document Upload Model
# ============================================================================

class DocumentUpload(BaseModel):
    """Metadata for uploaded document."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Path to stored file")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of file")
    document_type: DocumentType = Field(..., description="Type of document (PO or Bill)")
    status: DocumentStatus = Field(default=DocumentStatus.UPLOADING, description="Processing status")
    uploaded_by: str = Field(..., description="User ID who uploaded")
    ocr_result_id: Optional[str] = Field(None, description="ID of associated OCR result")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            PyObjectId: lambda v: str(v)
        }


class DocumentUploadCreate(BaseModel):
    """Request model for creating document upload."""
    filename: str
    file_path: str
    file_size_bytes: int
    mime_type: str
    document_type: DocumentType
    uploaded_by: str


class DocumentUploadUpdate(BaseModel):
    """Request model for updating document upload."""
    status: Optional[DocumentStatus] = None
    ocr_result_id: Optional[str] = None
    error_message: Optional[str] = None


# ============================================================================
# OCR Result Model
# ============================================================================

class OCRResult(BaseModel):
    """Result of OCR processing."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    document_upload_id: str = Field(..., description="ID of source document")
    document_type: DocumentType = Field(..., description="Type of document")

    # Extracted data
    extracted_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted header fields (invoice_number, dates, totals, etc.)"
    )
    extracted_items: List[ExtractedItem] = Field(
        default_factory=list,
        description="List of extracted items"
    )
    raw_text: Optional[str] = Field(None, description="Raw OCR text")

    # Processing metadata
    processing_time_sec: float = Field(..., ge=0, description="Processing time in seconds")
    ocr_engine: str = Field(default="tesseract", description="OCR engine used")

    # Validation
    warnings: List[str] = Field(default_factory=list, description="Processing warnings")
    errors: List[str] = Field(default_factory=list, description="Processing errors")

    # Review and approval
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING_REVIEW,
        description="Review status"
    )
    reviewed_by: Optional[str] = Field(None, description="User ID who reviewed")
    review_notes: Optional[str] = Field(None, description="Review notes")
    reviewed_at: Optional[datetime] = Field(None, description="Review timestamp")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            PyObjectId: lambda v: str(v)
        }


class OCRResultCreate(BaseModel):
    """Request model for creating OCR result."""
    document_upload_id: str
    document_type: DocumentType
    extracted_fields: Dict[str, Any]
    extracted_items: List[ExtractedItem]
    raw_text: Optional[str] = None
    processing_time_sec: float
    ocr_engine: str = "tesseract"
    warnings: List[str] = []
    errors: List[str] = []


class OCRResultUpdate(BaseModel):
    """Request model for updating OCR result."""
    status: Optional[DocumentStatus] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    extracted_fields: Optional[Dict[str, Any]] = None
    extracted_items: Optional[List[ExtractedItem]] = None


# ============================================================================
# Purchase Order Model
# ============================================================================

class PurchaseOrder(BaseModel):
    """Purchase order document."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    po_number: str = Field(..., description="Purchase order number")
    supplier_id: str = Field(..., description="ID of supplier")
    supplier_name: Optional[str] = Field(None, description="Name of supplier")

    # Items
    items: List[PurchaseOrderItem] = Field(..., description="List of ordered items")

    # Dates
    po_date: Optional[str] = Field(None, description="PO creation date (YYYY-MM-DD)")
    expected_delivery_date: Optional[str] = Field(
        None,
        description="Expected delivery date (YYYY-MM-DD)"
    )

    # Amounts
    subtotal_inr: int = Field(..., description="Subtotal in paise")
    tax_amount_inr: Optional[int] = Field(None, description="Tax amount in paise")
    total_amount_inr: int = Field(..., description="Total amount in paise")

    # Status
    status: POStatus = Field(default=POStatus.PENDING, description="PO status")

    # References
    document_upload_id: str = Field(..., description="ID of source document upload")
    ocr_result_id: str = Field(..., description="ID of source OCR result")

    # Audit
    created_by: str = Field(..., description="User ID who created")
    approved_by: Optional[str] = Field(None, description="User ID who approved")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            PyObjectId: lambda v: str(v)
        }


class PurchaseOrderCreate(BaseModel):
    """Request model for creating purchase order."""
    po_number: str
    supplier_id: str
    supplier_name: Optional[str] = None
    items: List[PurchaseOrderItem]
    po_date: Optional[str] = None
    expected_delivery_date: Optional[str] = None
    subtotal_inr: int
    tax_amount_inr: Optional[int] = None
    total_amount_inr: int
    status: POStatus = POStatus.PENDING
    document_upload_id: str
    ocr_result_id: str
    created_by: str


class PurchaseOrderUpdate(BaseModel):
    """Request model for updating purchase order."""
    status: Optional[POStatus] = None
    items: Optional[List[PurchaseOrderItem]] = None
    approved_by: Optional[str] = None


# ============================================================================
# Bill Model
# ============================================================================

class Bill(BaseModel):
    """Bill/Invoice document."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    invoice_number: str = Field(..., description="Invoice/bill number")
    supplier_id: str = Field(..., description="ID of supplier")
    supplier_name: Optional[str] = Field(None, description="Name of supplier")

    # Items
    items: List[BillItem] = Field(..., description="List of billed items")

    # Dates
    invoice_date: Optional[str] = Field(None, description="Invoice date (YYYY-MM-DD)")
    actual_delivery_date: Optional[str] = Field(
        None,
        description="Actual delivery date (YYYY-MM-DD)"
    )

    # Amounts
    subtotal_inr: int = Field(..., description="Subtotal in paise")
    tax_amount_inr: Optional[int] = Field(None, description="Tax amount in paise")
    total_amount_inr: int = Field(..., description="Total amount in paise")

    # PO Linking
    linked_po_id: Optional[str] = Field(None, description="ID of linked purchase order")
    has_price_discrepancies: bool = Field(
        default=False,
        description="Flag indicating price variances detected"
    )
    price_variance_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary of price variances"
    )

    # Status
    status: BillStatus = Field(default=BillStatus.PENDING_REVIEW, description="Bill status")

    # References
    document_upload_id: str = Field(..., description="ID of source document upload")
    ocr_result_id: str = Field(..., description="ID of source OCR result")

    # Inventory update tracking
    inventory_updated: bool = Field(default=False, description="Flag if inventory was updated")
    inventory_update_timestamp: Optional[datetime] = Field(
        None,
        description="Timestamp of inventory update"
    )

    # Audit
    created_by: str = Field(..., description="User ID who created")
    approved_by: Optional[str] = Field(None, description="User ID who approved")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            PyObjectId: lambda v: str(v)
        }


class BillCreate(BaseModel):
    """Request model for creating bill."""
    invoice_number: str
    supplier_id: str
    supplier_name: Optional[str] = None
    items: List[BillItem]
    invoice_date: Optional[str] = None
    actual_delivery_date: Optional[str] = None
    subtotal_inr: int
    tax_amount_inr: Optional[int] = None
    total_amount_inr: int
    linked_po_id: Optional[str] = None
    has_price_discrepancies: bool = False
    price_variance_summary: Optional[Dict[str, Any]] = None
    status: BillStatus = BillStatus.PENDING_REVIEW
    document_upload_id: str
    ocr_result_id: str
    created_by: str


class BillUpdate(BaseModel):
    """Request model for updating bill."""
    status: Optional[BillStatus] = None
    approved_by: Optional[str] = None
    inventory_updated: Optional[bool] = None
    inventory_update_timestamp: Optional[datetime] = None


class BillStatusUpdateRequest(BaseModel):
    """Request model for updating bill status."""
    status: BillStatus


class OCRSavePendingRequest(BaseModel):
    """Request for saving OCR result as pending review with edits."""
    extracted_fields: Optional[Dict[str, Any]] = None
    extracted_items: Optional[List[ExtractedItem]] = None
    review_notes: Optional[str] = None


class BillReviewRequest(BaseModel):
    """Request for approving/rejecting pending bill with optional item edits."""
    items: Optional[List[BillItem]] = None
    reason: Optional[str] = None


# ============================================================================
# API Request/Response Models
# ============================================================================

class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    upload_id: str
    ocr_result_id: Optional[str] = None
    status: DocumentStatus
    message: str


class OCRApprovalRequest(BaseModel):
    """Request for approving OCR result with optional edits."""
    extracted_fields: Optional[Dict[str, Any]] = None
    extracted_items: Optional[List[ExtractedItem]] = None
    review_notes: Optional[str] = None


class OCRApprovalResponse(BaseModel):
    """Response after OCR approval."""
    success: bool
    message: str
    po_id: Optional[str] = None
    bill_id: Optional[str] = None
    inventory_updated_count: int = 0
    price_variances: List[Dict[str, Any]] = []


class OCRRejectionRequest(BaseModel):
    """Request for rejecting OCR result."""
    reason: str


class DocumentHistoryFilter(BaseModel):
    """Filter parameters for document history."""
    document_type: Optional[DocumentType] = None
    status: Optional[DocumentStatus] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    uploaded_by: Optional[str] = None


class PurchaseOrderFilter(BaseModel):
    """Filter parameters for purchase orders."""
    supplier_id: Optional[str] = None
    status: Optional[POStatus] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class BillFilter(BaseModel):
    """Filter parameters for bills."""
    supplier_id: Optional[str] = None
    status: Optional[BillStatus] = None
    has_price_discrepancies: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    linked_po_id: Optional[str] = None
