"""
API endpoints for document upload and OCR processing.
"""
import tempfile
from datetime import datetime
from app.utils.timezone import now_ist
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.dependencies import get_admin_user
from app.models.document import (
    BillStatus,
    BillReviewRequest,
    OCRSavePendingRequest,
    BillStatusUpdateRequest,
    BillFilter,
    DocumentHistoryFilter,
    DocumentStatus,
    DocumentType,
    OCRApprovalRequest,
    OCRApprovalResponse,
    OCRRejectionRequest,
    PurchaseOrderFilter
)
from app.models.user import UserRole, UserResponse
from app.repositories.bill_repository import get_bill_repository
from app.repositories.document_repository import get_document_repository
from app.repositories.ocr_repository import get_ocr_repository
from app.repositories.purchase_order_repository import get_purchase_order_repository
from app.services.document_processor import get_document_processor_service
from app.utils.response import error_response, paginated_response, success_response

router = APIRouter(prefix="/documents", tags=["documents"])

# Configuration
settings = get_settings()
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png"
]


def _get_writable_upload_root() -> Path:
    """Return a writable upload root path, falling back to temp dir when needed."""
    upload_dir = UPLOAD_DIR
    if not upload_dir.is_absolute():
        # Resolve relative path from backend working directory
        upload_dir = (Path.cwd() / upload_dir).resolve()

    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir
    except OSError:
        # Fallback for restricted environments (read-only project mounts, etc.)
        fallback = Path(tempfile.gettempdir()) / "ahar_uploads" / "documents"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Upload a document (PDF/image) for OCR processing.

    - **file**: Document file (PDF, JPEG, or PNG)
    - **document_type**: Type of document ("PO" or "BILL")

    Returns:
      - upload_id: ID of created document upload
      - ocr_result_id: ID of OCR result (if processing succeeded)
      - status: Processing status
      - message: Status message
    """
    try:
        # Validate document type
        try:
            doc_type = DocumentType(document_type)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    "INVALID_DOCUMENT_TYPE",
                    f"Invalid document type. Must be 'PO' or 'BILL'."
                )
            )

        # Validate file type
        if file.content_type not in ALLOWED_MIME_TYPES:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    "INVALID_FILE_TYPE",
                    f"Invalid file type: {file.content_type}. Allowed types: PDF, JPEG, PNG."
                )
            )

        # Read file
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size
        if file_size > MAX_FILE_SIZE:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    "FILE_TOO_LARGE",
                    f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds maximum allowed size (10 MB)."
                )
            )

        # Create upload directory structure (YYYY/MM/)
        now = now_ist()
        upload_root = _get_writable_upload_root()
        upload_subdir = upload_root / str(now.year) / f"{now.month:02d}"
        upload_subdir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        filename_safe = file.filename.replace(" ", "_")
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        file_path = upload_subdir / f"{timestamp}_{filename_safe}"

        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Process upload through OCR pipeline
        processor = get_document_processor_service()
        result = await processor.process_upload(
            file_path=str(file_path),
            filename=file.filename,
            file_size=file_size,
            mime_type=file.content_type,
            document_type=doc_type,
            user_id=current_user.id
        )

        return success_response(
            data={
                "upload_id": result["upload_id"],
                "ocr_result_id": result["ocr_result_id"],
                "status": result["status"].value if isinstance(result["status"], DocumentStatus) else result["status"],
            },
            message=result["message"]
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "UPLOAD_FAILED",
                f"Document upload failed: {str(e)}"
            )
        )


@router.get("/pending")
async def get_pending_reviews(
    limit: int = 50,
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Get OCR results pending review.

    - **limit**: Maximum number of results to return (default: 50)

    Returns list of OCR results awaiting approval.
    """
    try:
        ocr_repo = get_ocr_repository()
        pending_results = await ocr_repo.get_pending_reviews(limit)

        # Convert ObjectId to string
        for result in pending_results:
            result["_id"] = str(result["_id"])
            if "document_upload_id" in result:
                result["document_upload_id"] = str(result["document_upload_id"])

        return success_response(
            data=pending_results,
            message=f"Found {len(pending_results)} pending reviews"
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "FETCH_FAILED",
                f"Failed to fetch pending reviews: {str(e)}"
            )
        )


@router.get("/{doc_id}")
async def get_ocr_result(
    doc_id: str,
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Get OCR result details by ID.

    - **doc_id**: OCR result ID

    Returns full OCR result with extracted data.
    """
    try:
        ocr_repo = get_ocr_repository()
        ocr_result = await ocr_repo.get_by_id(doc_id)

        if not ocr_result:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response(
                    "NOT_FOUND",
                    f"OCR result not found: {doc_id}"
                )
            )

        # Convert ObjectId to string
        ocr_result["_id"] = str(ocr_result["_id"])

        return success_response(
            data=ocr_result,
            message="OCR result retrieved successfully"
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "FETCH_FAILED",
                f"Failed to fetch OCR result: {str(e)}"
            )
        )


@router.post("/{doc_id}/approve")
async def approve_ocr_result(
    doc_id: str,
    request: OCRApprovalRequest,
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Approve OCR result with optional edits and apply to system.

    - **doc_id**: OCR result ID
    - **extracted_fields**: Optional user corrections to header fields
    - **extracted_items**: Optional user corrections to line items
    - **review_notes**: Optional review notes

    Creates PO/Bill and updates inventory as appropriate.
    """
    try:
        processor = get_document_processor_service()

        # Build user edits from request
        user_edits = {}
        if request.extracted_fields is not None:
            user_edits["extracted_fields"] = request.extracted_fields
        if request.extracted_items is not None:
            user_edits["extracted_items"] = [item.dict() for item in request.extracted_items]

        result = await processor.approve_and_apply(
            ocr_result_id=doc_id,
            user_id=current_user.id,
            user_edits=user_edits if user_edits else None,
            review_notes=request.review_notes
        )

        if not result["success"]:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    "APPROVAL_FAILED",
                    result["message"]
                )
            )

        return success_response(
            data={
                "po_id": result["po_id"],
                "bill_id": result["bill_id"],
                "inventory_updated_count": result["inventory_updated_count"],
                "price_variances": result["price_variances"]
            },
            message=result["message"]
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "APPROVAL_FAILED",
                f"Failed to approve OCR result: {str(e)}"
            )
        )


@router.post("/{doc_id}/reject")
async def reject_ocr_result(
    doc_id: str,
    request: OCRRejectionRequest,
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Reject OCR result with reason.

    - **doc_id**: OCR result ID
    - **reason**: Reason for rejection
    """
    try:
        processor = get_document_processor_service()
        result = await processor.reject_ocr_result(
            ocr_result_id=doc_id,
            user_id=current_user.id,
            reason=request.reason
        )

        if not result["success"]:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(
                    "REJECTION_FAILED",
                    result["message"]
                )
            )

        return success_response(
            data={},
            message=result["message"]
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "REJECTION_FAILED",
                f"Failed to reject OCR result: {str(e)}"
            )
        )


@router.post("/{doc_id}/save-pending")
async def save_pending_ocr_result(
    doc_id: str,
    request: OCRSavePendingRequest,
    current_user: UserResponse = Depends(get_admin_user)
):
    """Save OCR review edits as pending review without approving/rejecting."""
    try:
        processor = get_document_processor_service()
        user_edits = {}
        if request.extracted_fields is not None:
            user_edits["extracted_fields"] = request.extracted_fields
        if request.extracted_items is not None:
            user_edits["extracted_items"] = [item.dict() for item in request.extracted_items]

        result = await processor.save_pending_review(
            ocr_result_id=doc_id,
            user_id=current_user.id,
            user_edits=user_edits if user_edits else None,
            review_notes=request.review_notes
        )
        if not result["success"]:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response("SAVE_PENDING_FAILED", result["message"])
            )
        return success_response(
            data={"bill_id": result.get("bill_id")},
            message=result["message"]
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("SAVE_PENDING_FAILED", f"Failed to save pending review: {str(e)}")
        )


@router.delete("/{doc_id}/discard")
async def discard_uploaded_document(
    doc_id: str,
    current_user: UserResponse = Depends(get_admin_user)
):
    """Discard uploaded document + OCR result + derived records."""
    try:
        processor = get_document_processor_service()
        result = await processor.discard_upload(doc_id)
        if not result["success"]:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response("DISCARD_FAILED", result["message"])
            )
        return success_response(data={}, message=result["message"])
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DISCARD_FAILED", f"Failed to discard upload: {str(e)}")
        )


@router.get("/history/list")
async def get_document_history(
    page: int = 1,
    limit: int = 20,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Get paginated document upload history.

    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20)
    - **document_type**: Filter by type ("PO" or "BILL")
    - **status**: Filter by status
    - **start_date**: Filter by start date (YYYY-MM-DD)
    - **end_date**: Filter by end date (YYYY-MM-DD)
    """
    try:
        doc_repo = get_document_repository()

        # Parse filters
        doc_type_filter = DocumentType(document_type) if document_type else None
        status_filter = DocumentStatus(status) if status else None

        # Get paginated results
        skip = (page - 1) * limit
        documents = await doc_repo.get_all(
            skip=skip,
            limit=limit,
            document_type=doc_type_filter,
            status=status_filter,
            start_date=start_date,
            end_date=end_date
        )

        total = await doc_repo.count(
            document_type=doc_type_filter,
            status=status_filter,
            start_date=start_date,
            end_date=end_date
        )

        # Convert ObjectId to string
        for doc in documents:
            doc["_id"] = str(doc["_id"])

        return paginated_response(
            data=documents,
            page=page,
            limit=limit,
            total=total
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "FETCH_FAILED",
                f"Failed to fetch document history: {str(e)}"
            )
        )


@router.get("/purchase-orders/list")
async def get_purchase_orders(
    page: int = 1,
    limit: int = 20,
    supplier_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Get paginated list of purchase orders.

    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20)
    - **supplier_id**: Filter by supplier
    - **status**: Filter by status
    - **start_date**: Filter by start date
    - **end_date**: Filter by end date
    """
    try:
        po_repo = get_purchase_order_repository()

        # Parse status filter
        from app.models.document import POStatus
        status_filter = POStatus(status) if status else None

        # Get paginated results
        skip = (page - 1) * limit
        pos = await po_repo.get_all(
            skip=skip,
            limit=limit,
            supplier_id=supplier_id,
            status=status_filter,
            start_date=start_date,
            end_date=end_date
        )

        total = await po_repo.count(
            supplier_id=supplier_id,
            status=status_filter,
            start_date=start_date,
            end_date=end_date
        )

        # Convert ObjectId to string
        for po in pos:
            po["_id"] = str(po["_id"])

        return paginated_response(
            data=pos,
            page=page,
            limit=limit,
            total=total
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "FETCH_FAILED",
                f"Failed to fetch purchase orders: {str(e)}"
            )
        )


@router.get("/bills/list")
async def get_bills(
    page: int = 1,
    limit: int = 20,
    supplier_id: Optional[str] = None,
    status: Optional[str] = None,
    has_price_discrepancies: Optional[bool] = None,
    linked_po_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Get paginated list of bills.

    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20)
    - **supplier_id**: Filter by supplier
    - **status**: Filter by status
    - **has_price_discrepancies**: Filter bills with price discrepancies
    - **linked_po_id**: Filter by linked PO
    - **start_date**: Filter by start date
    - **end_date**: Filter by end date
    """
    try:
        bill_repo = get_bill_repository()

        # Parse status filter
        status_filter = BillStatus(status) if status else None

        # Get paginated results
        skip = (page - 1) * limit
        bills = await bill_repo.get_all(
            skip=skip,
            limit=limit,
            supplier_id=supplier_id,
            status=status_filter,
            has_price_discrepancies=has_price_discrepancies,
            linked_po_id=linked_po_id,
            start_date=start_date,
            end_date=end_date
        )

        total = await bill_repo.count(
            supplier_id=supplier_id,
            status=status_filter,
            has_price_discrepancies=has_price_discrepancies,
            linked_po_id=linked_po_id,
            start_date=start_date,
            end_date=end_date
        )

        # Convert ObjectId to string
        for bill in bills:
            bill["_id"] = str(bill["_id"])

        return paginated_response(
            data=bills,
            page=page,
            limit=limit,
            total=total
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "FETCH_FAILED",
                f"Failed to fetch bills: {str(e)}"
            )
        )


@router.post("/bills/{bill_id}/approve")
async def approve_pending_bill(
    bill_id: str,
    request: BillReviewRequest,
    current_user: UserResponse = Depends(get_admin_user)
):
    """Approve pending bill with optional item edits."""
    try:
        processor = get_document_processor_service()
        result = await processor.approve_pending_bill(
            bill_id=bill_id,
            user_id=current_user.id,
            items=[item.dict() for item in request.items] if request.items else None
        )
        if not result["success"]:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response("APPROVAL_FAILED", result["message"])
            )
        return success_response(
            data={"inventory_updated_count": result["inventory_updated_count"]},
            message=result["message"]
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("APPROVAL_FAILED", f"Failed to approve bill: {str(e)}")
        )


@router.post("/bills/{bill_id}/reject")
async def reject_pending_bill(
    bill_id: str,
    request: BillReviewRequest,
    current_user: UserResponse = Depends(get_admin_user)
):
    """Reject pending bill with optional item edits."""
    try:
        processor = get_document_processor_service()
        result = await processor.reject_pending_bill(
            bill_id=bill_id,
            user_id=current_user.id,
            items=[item.dict() for item in request.items] if request.items else None,
            reason=request.reason
        )
        if not result["success"]:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response("REJECTION_FAILED", result["message"])
            )
        return success_response(data={}, message=result["message"])
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("REJECTION_FAILED", f"Failed to reject bill: {str(e)}")
        )


@router.patch("/bills/{bill_id}/status")
async def update_bill_status(
    bill_id: str,
    request: BillStatusUpdateRequest,
    current_user: UserResponse = Depends(get_admin_user)
):
    """
    Update status of a bill from Bills tab workflows.

    - **bill_id**: Bill document ID
    - **status**: New bill status (pending_review, approved, rejected)
    """
    try:
        bill_repo = get_bill_repository()
        bill_doc = await bill_repo.get_by_id(bill_id)

        if not bill_doc:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response(
                    "NOT_FOUND",
                    f"Bill not found: {bill_id}"
                )
            )

        update_data = {"status": request.status}
        if request.status == BillStatus.APPROVED:
            update_data["approved_by"] = current_user.id
            update_data["approved_at"] = now_ist()

        updated_bill = await bill_repo.update(bill_id, update_data)
        if not updated_bill:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response(
                    "NOT_FOUND",
                    f"Bill not found: {bill_id}"
                )
            )

        updated_bill["_id"] = str(updated_bill["_id"])
        return success_response(
            data=updated_bill,
            message=f"Bill status updated to {request.status.value}"
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "UPDATE_FAILED",
                f"Failed to update bill status: {str(e)}"
            )
        )
