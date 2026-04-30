# ADR-002: OCR-Driven Purchase Order and Bill Review Workflow

**Date**: 2026-04-10
**Status**: Accepted
**Decider**: Pandiarajan
**Context**: Inventory management — automating data entry from supplier bills and purchase orders via document upload and OCR extraction

---

## Problem

Restaurant staff receive supplier bills and purchase orders as physical documents or PDFs/images. Manually re-entering line items into the system is error-prone and slow. The goal is to extract structured data (items, quantities, prices, totals) from uploaded documents and link them to inventory records, while keeping a human in the loop before any inventory state is changed.

---

## Decisions Made

### Decision: Tesseract OCR over Claude Vision API for text extraction
- **Chosen**: `pytesseract` (open-source Tesseract) with PIL image preprocessing
- **Rejected**: Claude vision API for OCR
- **Reason**: Tesseract runs locally at zero marginal cost per document. Claude vision API would incur per-call cost and add latency for every document upload. For structured documents (invoices, POs) with relatively uniform layouts, Tesseract with preprocessing is sufficient. Claude's vision strength is in understanding context and ambiguity — not needed when the document structure is predictable.

### Decision: Dual-path PDF handling (text extraction → OCR fallback)
- **Chosen**: Attempt `PyPDF2` direct text extraction first; fall back to `pdf2image` → Tesseract if extracted text is under 50 characters
- **Reason**: Many supplier PDFs are searchable (digitally created), making direct text extraction faster and more accurate than OCR. Scanned PDFs require rasterisation. The 50-character threshold distinguishes "no embedded text" from "genuinely short document."

### Decision: Fuzzy token-overlap matching for inventory item linking
- **Chosen**: Jaccard similarity on normalised token sets, threshold ≥ 0.65 for a match
- **Rejected**: Exact string match only; semantic embedding similarity
- **Reason**: OCR introduces noise (extra spaces, punctuation errors, casing differences). Jaccard on tokens tolerates this without requiring an embedding model. The 0.65 threshold was chosen empirically to avoid false matches while catching common OCR distortions. Embedding similarity would improve accuracy but adds a model dependency and latency that isn't justified until match failure rates are measured at scale.

### Decision: Human-in-the-loop review step before inventory commit
- **Chosen**: OCR results saved as a `pending_review` document state; staff review and correct in `OCRReviewStep` UI before the document is accepted
- **Rejected**: Auto-committing extracted data directly to inventory
- **Reason**: OCR accuracy on scanned restaurant invoices is not 100%. Auto-committing wrong quantities or prices would corrupt inventory records silently. The review step makes errors visible and correctable. The cost of one manual review per document is acceptable given the alternative (fully manual entry).

### Decision: Separate document status lifecycle (pending → accepted / discarded)
- **Chosen**: Documents progress through `pending_review` → `accepted` or `discarded` states stored in a `documents` collection
- **Reason**: Provides an audit trail of all uploaded documents regardless of outcome. "Discarded" documents are preserved for debugging OCR failures rather than deleted. Inventory updates are only triggered on `accepted` transition.

### Decision: 5% price variance threshold for PO-to-bill matching alerts
- **Chosen**: Flag items where billed price differs from PO price by more than 5%
- **Reason**: Gives staff visibility into supplier price deviations without alerting on rounding noise. The threshold is configurable in `ItemMatchingService`.

---

## Decisions Rejected / Deferred

### Deferred: Hindi/regional language support in OCR
- **Reason**: `pytesseract` supports `hin` language pack; placeholder exists in code (`supported_languages = ['eng']`). Not enabled because no restaurant has submitted Hindi-script invoices yet. Enable when a restaurant requires it.

### Deferred: Claude vision for ambiguous/handwritten documents
- **Reason**: Tesseract performs poorly on handwritten text. A fallback to Claude vision for documents where Tesseract confidence is low would improve coverage. Deferred until the handwritten-document failure rate is measured in production.

### Rejected: Fully automated inventory update without review
- **Reason**: Tested conceptually — rejected because OCR error rates on real-world scanned invoices are non-trivial. Staff correction during review also trains intuition for spotting supplier errors.

---

## Known Limitations

| Issue | Impact | Path forward |
|---|---|---|
| Tesseract accuracy on low-quality scans | Missed or garbled line items requiring manual correction | Image preprocessing (contrast enhancement, deskew) partially mitigates; Claude vision fallback deferred |
| Fuzzy match false negatives | New or renamed inventory items won't auto-match | Staff can manually link during review; unmatched items flagged clearly |
| English OCR only | Non-English invoices unsupported | Hindi language pack available in Tesseract; enable on demand |
| No confidence scores surfaced to UI | Staff can't prioritise which fields need review | Add Tesseract word-level confidence to review UI |

---

## Output / Affected Files

| File or service | What changed or was created |
|---|---|
| `backend/app/services/ocr_service.py` | Tesseract extraction, dual-path PDF/image handling, field parsing |
| `backend/app/services/item_matching_service.py` | Fuzzy inventory matching, PO-to-bill linking, price variance alerts |
| `backend/app/services/document_processor.py` | Orchestrates OCR → matching → pending save pipeline |
| `backend/app/api/v1/documents.py` | Upload, review, accept, discard endpoints |
| `backend/app/models/document.py` | Document, PurchaseOrder, Bill models and status enums |
| `backend/app/repositories/document_repository.py` | Documents collection CRUD |
| `backend/app/repositories/ocr_repository.py` | OCR result persistence |
| `backend/app/repositories/purchase_order_repository.py` | PO collection CRUD |
| `backend/app/repositories/bill_repository.py` | Bill collection CRUD |
| `frontend/src/components/inventory/OCRReviewStep.tsx` | Review UI — line-item correction before accept |
| `frontend/src/components/inventory/DocumentUploadModal.tsx` | Upload flow |
| `frontend/src/components/inventory/PurchaseOrdersTab.tsx` | PO management screen |
| `frontend/src/components/inventory/BillsTab.tsx` | Bills management screen |
| `frontend/src/services/documents.ts` | Frontend API client for document endpoints |

---

## Next Decisions Pending

1. **Tesseract confidence threshold for Claude vision fallback** — at what OCR confidence score should the system escalate to Claude vision instead?
2. **PO auto-generation from demand forecast** — should the forecast model output feed directly into PO creation, reducing manual upload need?
3. **Audit trail retention policy** — how long to keep `discarded` documents; storage cost vs debugging value
