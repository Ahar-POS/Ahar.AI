"""
Document processor service - orchestrates OCR upload and approval workflows.
"""
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.document import (
    Bill,
    BillCreate,
    BillItem,
    BillStatus,
    DocumentStatus,
    DocumentType,
    DocumentUpload,
    DocumentUploadCreate,
    ExtractedItem,
    OCRResult,
    OCRResultCreate,
    POStatus,
    PurchaseOrder,
    PurchaseOrderCreate,
    PurchaseOrderItem
)
from app.repositories.bill_repository import get_bill_repository
from app.repositories.document_repository import get_document_repository
from app.repositories.inventory_repository import get_inventory_repository
from app.repositories.ocr_repository import get_ocr_repository
from app.repositories.purchase_order_repository import get_purchase_order_repository
from app.services.item_matching_service import ItemMatchingService
from app.services.ocr_service import OCRService

class DocumentProcessorService:
    """Service for processing document uploads and OCR workflows."""

    def __init__(self):
        """Initialize document processor service."""
        self.ocr_service = OCRService()
        self.document_repo = get_document_repository()
        self.ocr_repo = get_ocr_repository()
        self.inventory_repo = get_inventory_repository()
        self.po_repo = get_purchase_order_repository()
        self.bill_repo = get_bill_repository()
        self.item_matching_service = ItemMatchingService(self.inventory_repo)

    async def process_upload(
        self,
        file_path: str,
        filename: str,
        file_size: int,
        mime_type: str,
        document_type: DocumentType,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Process uploaded document through OCR pipeline.

        Args:
            file_path: Path to saved file
            filename: Original filename
            file_size: File size in bytes
            mime_type: MIME type
            document_type: Type of document (PO or Bill)
            user_id: ID of user who uploaded

        Returns:
            Dictionary with upload_id, ocr_result_id, status, message
        """
        start_time = time.time()
        warnings = []
        errors = []

        try:
            # 1. Create document upload record
            upload_data = DocumentUploadCreate(
                filename=filename,
                file_path=file_path,
                file_size_bytes=file_size,
                mime_type=mime_type,
                document_type=document_type,
                uploaded_by=user_id
            )

            document_upload = await self.document_repo.create(upload_data.dict())
            upload_id = str(document_upload["_id"])

            # 2. Update status to processing
            await self.document_repo.update(
                upload_id,
                {"status": DocumentStatus.PROCESSING}
            )

            # 3. Extract text based on file type
            try:
                if mime_type == "application/pdf":
                    extraction_result = await self.ocr_service.extract_from_pdf(
                        file_path,
                        document_type
                    )
                elif mime_type in ["image/jpeg", "image/png"]:
                    extraction_result = await self.ocr_service.extract_from_image(
                        file_path,
                        document_type
                    )
                else:
                    raise ValueError(f"Unsupported file type: {mime_type}")

            except Exception as e:
                # OCR extraction failed
                errors.append(f"OCR extraction failed: {str(e)}")
                await self.document_repo.update(
                    upload_id,
                    {
                        "status": DocumentStatus.FAILED,
                        "error_message": str(e)
                    }
                )
                return {
                    "upload_id": upload_id,
                    "ocr_result_id": None,
                    "status": DocumentStatus.FAILED,
                    "message": f"OCR extraction failed: {str(e)}"
                }

            raw_text = extraction_result["raw_text"]
            extracted_fields = extraction_result["extracted_fields"]
            extracted_items = extraction_result["extracted_items"]

            # 4. Validate extraction
            if not raw_text or len(raw_text.strip()) < 10:
                warnings.append("Very little text extracted - document may be blank or illegible")

            if not extracted_items:
                warnings.append("No line items found in table - may require manual entry")

            # 5. Match items to inventory
            if extracted_items:
                matched_items = await self.item_matching_service.match_extracted_items(
                    extracted_items
                )
            else:
                matched_items = []

            # Count unmatched items
            unmatched_count = sum(
                1 for item in matched_items
                if item.match_status.value == "unmatched"
            )

            if unmatched_count > 0:
                warnings.append(
                    f"{unmatched_count} items could not be matched to inventory - "
                    "will require manual mapping"
                )

            # 6. Create OCR result
            processing_time = time.time() - start_time

            ocr_data = OCRResultCreate(
                document_upload_id=upload_id,
                document_type=document_type,
                extracted_fields=extracted_fields,
                extracted_items=[item.dict() for item in matched_items],
                raw_text=raw_text,
                processing_time_sec=round(processing_time, 2),
                warnings=warnings,
                errors=errors
            )

            ocr_result = await self.ocr_repo.create(ocr_data.dict())
            ocr_result_id = str(ocr_result["_id"])

            # 7. Update document upload with OCR result
            await self.document_repo.update(
                upload_id,
                {
                    "status": DocumentStatus.PENDING_REVIEW,
                    "ocr_result_id": ocr_result_id
                }
            )

            return {
                "upload_id": upload_id,
                "ocr_result_id": ocr_result_id,
                "status": DocumentStatus.PENDING_REVIEW,
                "message": "OCR processing completed successfully"
            }

        except Exception as e:
            # Unexpected error
            errors.append(f"Processing failed: {str(e)}")

            if 'upload_id' in locals():
                await self.document_repo.update(
                    upload_id,
                    {
                        "status": DocumentStatus.FAILED,
                        "error_message": str(e)
                    }
                )

            return {
                "upload_id": locals().get('upload_id'),
                "ocr_result_id": None,
                "status": DocumentStatus.FAILED,
                "message": f"Processing failed: {str(e)}"
            }

    async def approve_and_apply(
        self,
        ocr_result_id: str,
        user_id: str,
        user_edits: Optional[Dict[str, Any]] = None,
        review_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve OCR result and apply to system (create PO/Bill, update inventory).

        Args:
            ocr_result_id: ID of OCR result to approve
            user_id: ID of user approving
            user_edits: Optional user corrections to extracted data
            review_notes: Optional review notes

        Returns:
            Dictionary with success status, po_id/bill_id, inventory updates, variances
        """
        try:
            # 1. Get OCR result
            ocr_result_doc = await self.ocr_repo.get_by_id(ocr_result_id)
            if not ocr_result_doc:
                raise ValueError(f"OCR result not found: {ocr_result_id}")

            # 2. Apply user edits if provided
            if user_edits:
                if "extracted_fields" in user_edits:
                    ocr_result_doc["extracted_fields"].update(user_edits["extracted_fields"])

                if "extracted_items" in user_edits:
                    ocr_result_doc["extracted_items"] = user_edits["extracted_items"]

            # 3. Update OCR result status
            await self.ocr_repo.update(
                ocr_result_id,
                {
                    "status": DocumentStatus.APPROVED,
                    "reviewed_by": user_id,
                    "review_notes": review_notes,
                    "reviewed_at": datetime.utcnow()
                }
            )

            # 4. Update document upload status
            await self.document_repo.update(
                ocr_result_doc["document_upload_id"],
                {"status": DocumentStatus.APPROVED}
            )

            # 5. Process based on document type
            document_type = DocumentType(ocr_result_doc["document_type"])

            if document_type == DocumentType.PURCHASE_ORDER:
                result = await self._process_po_approval(
                    ocr_result_doc,
                    user_id
                )
            else:  # BILL
                result = await self._process_bill_approval(
                    ocr_result_doc,
                    user_id
                )

            return result

        except Exception as e:
            return {
                "success": False,
                "message": f"Approval failed: {str(e)}",
                "po_id": None,
                "bill_id": None,
                "inventory_updated_count": 0,
                "price_variances": []
            }

    async def reject_ocr_result(
        self,
        ocr_result_id: str,
        user_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Reject OCR result.

        Args:
            ocr_result_id: ID of OCR result to reject
            user_id: ID of user rejecting
            reason: Reason for rejection

        Returns:
            Dictionary with success status and message
        """
        try:
            # 1. Get OCR result
            ocr_result_doc = await self.ocr_repo.get_by_id(ocr_result_id)
            if not ocr_result_doc:
                raise ValueError(f"OCR result not found: {ocr_result_id}")

            # 2. Update OCR result status
            await self.ocr_repo.update(
                ocr_result_id,
                {
                    "status": DocumentStatus.REJECTED,
                    "reviewed_by": user_id,
                    "review_notes": reason,
                    "reviewed_at": datetime.utcnow()
                }
            )

            # 3. Update document upload status
            await self.document_repo.update(
                ocr_result_doc["document_upload_id"],
                {"status": DocumentStatus.REJECTED}
            )

            # 4. For bills, create/update rejected bill record so it appears in Bills tab
            if DocumentType(ocr_result_doc["document_type"]) == DocumentType.BILL:
                await self._upsert_bill_from_ocr(
                    ocr_result_doc=ocr_result_doc,
                    user_id=user_id,
                    status=BillStatus.REJECTED
                )

            return {
                "success": True,
                "message": "OCR result rejected successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Rejection failed: {str(e)}"
            }

    async def save_pending_review(
        self,
        ocr_result_id: str,
        user_id: str,
        user_edits: Optional[Dict[str, Any]] = None,
        review_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save OCR result as pending review and persist editable bill draft."""
        try:
            ocr_result_doc = await self.ocr_repo.get_by_id(ocr_result_id)
            if not ocr_result_doc:
                raise ValueError(f"OCR result not found: {ocr_result_id}")

            if user_edits:
                if "extracted_fields" in user_edits:
                    ocr_result_doc["extracted_fields"].update(user_edits["extracted_fields"])
                if "extracted_items" in user_edits:
                    ocr_result_doc["extracted_items"] = user_edits["extracted_items"]

            await self.ocr_repo.update(
                ocr_result_id,
                {
                    "status": DocumentStatus.PENDING_REVIEW,
                    "reviewed_by": user_id,
                    "review_notes": review_notes
                }
            )
            await self.document_repo.update(
                ocr_result_doc["document_upload_id"],
                {"status": DocumentStatus.PENDING_REVIEW}
            )

            bill_id = None
            if DocumentType(ocr_result_doc["document_type"]) == DocumentType.BILL:
                bill_doc = await self._upsert_bill_from_ocr(
                    ocr_result_doc=ocr_result_doc,
                    user_id=user_id,
                    status=BillStatus.PENDING_REVIEW
                )
                bill_id = str(bill_doc["_id"]) if bill_doc else None

            return {
                "success": True,
                "message": "Saved as pending review",
                "bill_id": bill_id
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Save pending failed: {str(e)}",
                "bill_id": None
            }

    async def discard_upload(self, ocr_result_id: str) -> Dict[str, Any]:
        """Delete upload + OCR + derived documents + file as if never uploaded."""
        try:
            ocr_result_doc = await self.ocr_repo.get_by_id(ocr_result_id)
            if not ocr_result_doc:
                raise ValueError(f"OCR result not found: {ocr_result_id}")

            document_upload_id = str(ocr_result_doc["document_upload_id"])
            document_upload_doc = await self.document_repo.get_by_id(document_upload_id)

            existing_bill = await self.bill_repo.get_by_ocr_result_id(ocr_result_id)
            if existing_bill:
                await self.bill_repo.delete(str(existing_bill["_id"]))

            existing_po = await self.po_repo.get_by_ocr_result_id(ocr_result_id)
            if existing_po:
                await self.po_repo.delete(str(existing_po["_id"]))

            await self.ocr_repo.delete(ocr_result_id)
            await self.document_repo.delete(document_upload_id)

            if document_upload_doc and document_upload_doc.get("file_path"):
                file_path = Path(str(document_upload_doc["file_path"]))
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass

            return {"success": True, "message": "Upload discarded successfully"}
        except Exception as e:
            return {"success": False, "message": f"Discard failed: {str(e)}"}

    async def approve_pending_bill(
        self,
        bill_id: str,
        user_id: str,
        items: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Approve pending bill with optional item edits and update inventory."""
        try:
            bill_doc = await self.bill_repo.get_by_id(bill_id)
            if not bill_doc:
                raise ValueError(f"Bill not found: {bill_id}")
            if bill_doc.get("status") != BillStatus.PENDING_REVIEW.value:
                raise ValueError("Only pending review bills can be approved")

            bill_items = items if items is not None else bill_doc.get("items", [])
            inventory_updated_count = 0
            for item in bill_items:
                inventory_item = await self.inventory_repo.get_by_id(item["inventory_id"])
                if not inventory_item:
                    continue
                await self.inventory_repo.update(
                    item["inventory_id"],
                    {
                        "current_stock": float(inventory_item["current_stock"]) + float(item["quantity"]),
                        "unit_cost_inr": item["unit_cost_inr"],
                        "last_restock_date": bill_doc.get("actual_delivery_date") or datetime.utcnow().strftime("%Y-%m-%d")
                    }
                )
                inventory_updated_count += 1

            subtotal = sum(int(item.get("line_total_inr", int(float(item["quantity"]) * int(item["unit_cost_inr"])))) for item in bill_items)
            await self.bill_repo.update(
                bill_id,
                {
                    "items": bill_items,
                    "subtotal_inr": subtotal,
                    "total_amount_inr": bill_doc.get("total_amount_inr", subtotal),
                    "status": BillStatus.APPROVED,
                    "approved_by": user_id,
                    "approved_at": datetime.utcnow(),
                    "inventory_updated": True,
                    "inventory_update_timestamp": datetime.utcnow()
                }
            )
            return {"success": True, "message": "Bill approved", "inventory_updated_count": inventory_updated_count}
        except Exception as e:
            return {"success": False, "message": f"Approve pending bill failed: {str(e)}", "inventory_updated_count": 0}

    async def reject_pending_bill(
        self,
        bill_id: str,
        user_id: str,
        items: Optional[List[Dict[str, Any]]] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reject pending bill with optional item edits."""
        try:
            bill_doc = await self.bill_repo.get_by_id(bill_id)
            if not bill_doc:
                raise ValueError(f"Bill not found: {bill_id}")
            if bill_doc.get("status") != BillStatus.PENDING_REVIEW.value:
                raise ValueError("Only pending review bills can be rejected")

            update_data = {
                "status": BillStatus.REJECTED,
                "approved_by": user_id,
                "approved_at": datetime.utcnow()
            }
            if items is not None:
                subtotal = sum(int(item.get("line_total_inr", int(float(item["quantity"]) * int(item["unit_cost_inr"])))) for item in items)
                update_data["items"] = items
                update_data["subtotal_inr"] = subtotal
                update_data["total_amount_inr"] = bill_doc.get("total_amount_inr", subtotal)
            if reason:
                update_data["rejection_reason"] = reason

            await self.bill_repo.update(bill_id, update_data)
            return {"success": True, "message": "Bill rejected"}
        except Exception as e:
            return {"success": False, "message": f"Reject pending bill failed: {str(e)}"}

    async def get_pending_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get OCR results pending review."""
        return await self.ocr_repo.get_pending_reviews(limit)

    # ========================================================================
    # Private helper methods
    # ========================================================================

    async def _process_po_approval(
        self,
        ocr_result_doc: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Process approval of purchase order."""
        extracted_fields = ocr_result_doc["extracted_fields"]
        extracted_items = ocr_result_doc["extracted_items"]

        # Build PO items from extracted items
        po_items = []
        for item_data in extracted_items:
            if item_data.get("matched_inventory_id"):
                po_item = PurchaseOrderItem(
                    inventory_id=item_data["matched_inventory_id"],
                    material_name=item_data["material_name"],
                    quantity_ordered=item_data["quantity"],
                    quantity_received=0,
                    unit=item_data["unit"],
                    unit_cost_inr=item_data["unit_cost_inr"],
                    line_total_inr=item_data.get(
                        "line_total_inr",
                        int(item_data["quantity"] * item_data["unit_cost_inr"])
                    )
                )
                po_items.append(po_item)

        if not po_items:
            raise ValueError("No matched items to create PO")

        # Calculate totals
        subtotal = sum(item.line_total_inr for item in po_items)

        # Create PO
        po_data = PurchaseOrderCreate(
            po_number=extracted_fields.get("po_number", "UNKNOWN"),
            supplier_id=extracted_fields.get("supplier_id", ""),
            supplier_name=extracted_fields.get("supplier_name"),
            items=[item.dict() for item in po_items],
            po_date=extracted_fields.get("po_date"),
            expected_delivery_date=extracted_fields.get("expected_delivery_date"),
            subtotal_inr=subtotal,
            tax_amount_inr=extracted_fields.get("tax_amount_inr"),
            total_amount_inr=extracted_fields.get("total_amount_inr", subtotal),
            document_upload_id=ocr_result_doc["document_upload_id"],
            ocr_result_id=str(ocr_result_doc["_id"]),
            created_by=user_id
        )

        po = await self.po_repo.create(po_data.dict())

        return {
            "success": True,
            "message": "Purchase order created successfully",
            "po_id": str(po["_id"]),
            "bill_id": None,
            "inventory_updated_count": 0,
            "price_variances": []
        }

    async def _process_bill_approval(
        self,
        ocr_result_doc: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Process approval of bill and update inventory."""
        extracted_fields = ocr_result_doc["extracted_fields"]
        extracted_items = ocr_result_doc["extracted_items"]

        # Build bill items from extracted items
        bill_items, inventory_updates = self._build_bill_items_and_inventory_updates(extracted_items)

        if not bill_items:
            raise ValueError("No matched items to create bill")

        # Calculate totals
        subtotal = sum(item.line_total_inr for item in bill_items)

        # Try to match bill to PO
        supplier_id = extracted_fields.get("supplier_id", "")
        actual_delivery_date = extracted_fields.get("actual_delivery_date") or extracted_fields.get("invoice_date")

        linked_po_id, price_variance_summary = await self.item_matching_service.match_bill_to_po(
            bill=Bill(
                invoice_number="",  # Placeholder
                supplier_id=supplier_id,
                items=bill_items,
                subtotal_inr=subtotal,
                total_amount_inr=extracted_fields.get("total_amount_inr", subtotal),
                document_upload_id="",
                ocr_result_id="",
                created_by=user_id
            ),
            supplier_id=supplier_id,
            actual_delivery_date=actual_delivery_date,
            po_repo=self.po_repo
        )

        existing_bill = await self.bill_repo.get_by_ocr_result_id(str(ocr_result_doc["_id"]))
        if existing_bill:
            await self.bill_repo.update(
                str(existing_bill["_id"]),
                {
                    "invoice_number": extracted_fields.get("invoice_number", "UNKNOWN"),
                    "supplier_id": supplier_id,
                    "supplier_name": extracted_fields.get("supplier_name"),
                    "items": [item.dict() for item in bill_items],
                    "invoice_date": extracted_fields.get("invoice_date"),
                    "actual_delivery_date": actual_delivery_date,
                    "subtotal_inr": subtotal,
                    "tax_amount_inr": extracted_fields.get("tax_amount_inr"),
                    "total_amount_inr": extracted_fields.get("total_amount_inr", subtotal),
                    "linked_po_id": linked_po_id,
                    "has_price_discrepancies": price_variance_summary.get("has_significant_variances", False),
                    "price_variance_summary": price_variance_summary if price_variance_summary else None,
                    "status": BillStatus.APPROVED
                }
            )
            bill_id = str(existing_bill["_id"])
        else:
            bill_data = BillCreate(
                invoice_number=extracted_fields.get("invoice_number", "UNKNOWN"),
                supplier_id=supplier_id,
                supplier_name=extracted_fields.get("supplier_name"),
                items=[item.dict() for item in bill_items],
                invoice_date=extracted_fields.get("invoice_date"),
                actual_delivery_date=actual_delivery_date,
                subtotal_inr=subtotal,
                tax_amount_inr=extracted_fields.get("tax_amount_inr"),
                total_amount_inr=extracted_fields.get("total_amount_inr", subtotal),
                linked_po_id=linked_po_id,
                has_price_discrepancies=price_variance_summary.get("has_significant_variances", False),
                price_variance_summary=price_variance_summary if price_variance_summary else None,
                status=BillStatus.APPROVED,
                document_upload_id=ocr_result_doc["document_upload_id"],
                ocr_result_id=str(ocr_result_doc["_id"]),
                created_by=user_id
            )
            bill = await self.bill_repo.create(bill_data.dict())
            bill_id = str(bill["_id"])

        # Update inventory
        inventory_updated_count = 0
        for update in inventory_updates:
            try:
                # Increment current_stock
                inventory_item = await self.inventory_repo.get_by_id(update["inventory_id"])
                if inventory_item:
                    await self.inventory_repo.update(
                        update["inventory_id"],
                        {
                            "current_stock": float(inventory_item["current_stock"]) + float(update["quantity"]),
                            "unit_cost_inr": update["unit_cost_inr"],
                            "last_restock_date": actual_delivery_date or datetime.utcnow().strftime("%Y-%m-%d")
                        }
                    )
                    inventory_updated_count += 1
            except Exception as e:
                print(f"Failed to update inventory {update['inventory_id']}: {e}")

        # Update bill inventory tracking
        await self.bill_repo.update(
            bill_id,
            {
                "inventory_updated": True,
                "inventory_update_timestamp": datetime.utcnow()
            }
        )

        # Update PO if linked
        if linked_po_id:
            po = await self.po_repo.get_by_id(linked_po_id)
            if po:
                await self.item_matching_service.update_po_received_quantities(
                    po=PurchaseOrder(**po),
                    bill_items=bill_items,
                    po_repo=self.po_repo
                )

        return {
            "success": True,
            "message": "Bill created and inventory updated successfully",
            "po_id": None,
            "bill_id": bill_id,
            "inventory_updated_count": inventory_updated_count,
            "price_variances": price_variance_summary.get("item_variances", []) if price_variance_summary else []
        }

    def _build_bill_items_and_inventory_updates(
        self,
        extracted_items: List[Dict[str, Any]]
    ) -> tuple[List[BillItem], List[Dict[str, Any]]]:
        """Build normalized BillItem list and inventory updates from extracted items."""
        bill_items: List[BillItem] = []
        inventory_updates: List[Dict[str, Any]] = []

        for item_data in extracted_items:
            matched_inventory_id = item_data.get("matched_inventory_id")
            if not matched_inventory_id:
                continue

            quantity = float(item_data["quantity"])
            unit_cost_inr = int(item_data["unit_cost_inr"])
            bill_item = BillItem(
                inventory_id=matched_inventory_id,
                material_name=item_data["material_name"],
                quantity=quantity,
                unit=item_data["unit"],
                unit_cost_inr=unit_cost_inr,
                line_total_inr=item_data.get(
                    "line_total_inr",
                    int(quantity * unit_cost_inr)
                )
            )
            bill_items.append(bill_item)
            inventory_updates.append(
                {
                    "inventory_id": matched_inventory_id,
                    "quantity": quantity,
                    "unit_cost_inr": unit_cost_inr
                }
            )

        return bill_items, inventory_updates

    async def _upsert_bill_from_ocr(
        self,
        ocr_result_doc: Dict[str, Any],
        user_id: str,
        status: BillStatus
    ) -> Optional[Dict[str, Any]]:
        """Create or update bill draft from OCR result for pending/rejected workflows."""
        extracted_fields = ocr_result_doc.get("extracted_fields", {})
        extracted_items = ocr_result_doc.get("extracted_items", [])
        bill_items, _ = self._build_bill_items_and_inventory_updates(extracted_items)
        if not bill_items:
            return None

        subtotal = sum(item.line_total_inr for item in bill_items)
        supplier_id = extracted_fields.get("supplier_id", "")
        actual_delivery_date = extracted_fields.get("actual_delivery_date") or extracted_fields.get("invoice_date")

        existing_bill = await self.bill_repo.get_by_ocr_result_id(str(ocr_result_doc["_id"]))
        update_payload = {
            "invoice_number": extracted_fields.get("invoice_number", "UNKNOWN"),
            "supplier_id": supplier_id,
            "supplier_name": extracted_fields.get("supplier_name"),
            "items": [item.dict() for item in bill_items],
            "invoice_date": extracted_fields.get("invoice_date"),
            "actual_delivery_date": actual_delivery_date,
            "subtotal_inr": subtotal,
            "tax_amount_inr": extracted_fields.get("tax_amount_inr"),
            "total_amount_inr": extracted_fields.get("total_amount_inr", subtotal),
            "status": status
        }
        if status == BillStatus.APPROVED:
            update_payload["approved_by"] = user_id
            update_payload["approved_at"] = datetime.utcnow()

        if existing_bill:
            return await self.bill_repo.update(str(existing_bill["_id"]), update_payload)

        bill_data = BillCreate(
            invoice_number=extracted_fields.get("invoice_number", "UNKNOWN"),
            supplier_id=supplier_id,
            supplier_name=extracted_fields.get("supplier_name"),
            items=[item.dict() for item in bill_items],
            invoice_date=extracted_fields.get("invoice_date"),
            actual_delivery_date=actual_delivery_date,
            subtotal_inr=subtotal,
            tax_amount_inr=extracted_fields.get("tax_amount_inr"),
            total_amount_inr=extracted_fields.get("total_amount_inr", subtotal),
            linked_po_id=None,
            has_price_discrepancies=False,
            price_variance_summary=None,
            status=status,
            document_upload_id=ocr_result_doc["document_upload_id"],
            ocr_result_id=str(ocr_result_doc["_id"]),
            created_by=user_id
        )
        return await self.bill_repo.create(bill_data.dict())


# Singleton instance
document_processor_service = DocumentProcessorService()


def get_document_processor_service() -> DocumentProcessorService:
    """Get singleton document processor service instance."""
    return document_processor_service
