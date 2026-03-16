"""
OCR Service for extracting text and structured data from documents.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter
from PyPDF2 import PdfReader

from app.models.document import DocumentType, ExtractedItem, MatchStatus

class OCRService:
    """Service for OCR text extraction and parsing."""

    def __init__(self):
        """Initialize OCR service."""
        self.ocr_timeout_sec = 30
        self.supported_languages = ['eng']  # Can add 'hin' for Hindi support

    async def extract_from_pdf(
        self,
        file_path: str,
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """
        Extract text from PDF file.

        Args:
            file_path: Path to PDF file
            document_type: Type of document (PO or Bill)

        Returns:
            Dictionary containing raw_text, extracted_fields, and extracted_items
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        # Try extracting text directly from searchable PDF first
        raw_text = await self._extract_text_from_searchable_pdf(file_path)

        # If no text or very little text, treat as scanned PDF
        if not raw_text or len(raw_text.strip()) < 50:
            raw_text = await self._extract_text_from_scanned_pdf(file_path)

        # Parse the extracted text
        extracted_fields, extracted_items = await self.parse_extracted_text(
            raw_text,
            document_type
        )

        return {
            "raw_text": raw_text,
            "extracted_fields": extracted_fields,
            "extracted_items": extracted_items
        }

    async def extract_from_image(
        self,
        file_path: str,
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """
        Extract text from image file (JPEG/PNG).

        Args:
            file_path: Path to image file
            document_type: Type of document (PO or Bill)

        Returns:
            Dictionary containing raw_text, extracted_fields, and extracted_items
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        # Load and preprocess image
        image = Image.open(file_path)
        processed_image = await self.preprocess_image(image)

        # Extract text using Tesseract
        raw_text = pytesseract.image_to_string(
            processed_image,
            lang='+'.join(self.supported_languages),
            timeout=self.ocr_timeout_sec
        )

        # Parse the extracted text
        extracted_fields, extracted_items = await self.parse_extracted_text(
            raw_text,
            document_type
        )

        return {
            "raw_text": raw_text,
            "extracted_fields": extracted_fields,
            "extracted_items": extracted_items
        }

    async def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image to improve OCR accuracy.

        Args:
            image: PIL Image object

        Returns:
            Processed PIL Image
        """
        # Convert to grayscale
        image = image.convert('L')

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)

        # Apply slight sharpening
        image = image.filter(ImageFilter.SHARPEN)

        # Threshold to binary (black and white)
        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0)

        # Resize if too small (improve OCR accuracy)
        width, height = image.size
        if width < 1000:
            scale_factor = 1000 / width
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return image

    async def parse_extracted_text(
        self,
        raw_text: str,
        document_type: DocumentType
    ) -> Tuple[Dict[str, Any], List[ExtractedItem]]:
        """
        Parse extracted text to structured data.

        Args:
            raw_text: Raw OCR text
            document_type: Type of document

        Returns:
            Tuple of (extracted_fields dict, extracted_items list)
        """
        extracted_fields = {}
        extracted_items = []

        if not raw_text or len(raw_text.strip()) < 10:
            return extracted_fields, extracted_items

        # Extract header fields
        extracted_fields = await self._extract_header_fields(raw_text, document_type)

        # Extract line items from table
        extracted_items = await self._extract_line_items(raw_text)

        return extracted_fields, extracted_items

    async def classify_document_type(self, raw_text: str) -> Optional[DocumentType]:
        """
        Auto-detect document type from text.

        Args:
            raw_text: Raw OCR text

        Returns:
            DocumentType or None if cannot determine
        """
        text_lower = raw_text.lower()

        # Keywords for Purchase Order
        po_keywords = ['purchase order', 'po number', 'p.o.', 'order confirmation']
        # Keywords for Bill/Invoice
        bill_keywords = ['invoice', 'bill', 'tax invoice', 'receipt']

        po_score = sum(1 for kw in po_keywords if kw in text_lower)
        bill_score = sum(1 for kw in bill_keywords if kw in text_lower)

        if po_score > bill_score:
            return DocumentType.PURCHASE_ORDER
        elif bill_score > po_score:
            return DocumentType.BILL
        else:
            return None

    # ========================================================================
    # Private helper methods
    # ========================================================================

    async def _extract_text_from_searchable_pdf(self, file_path: str) -> str:
        """Extract text from searchable PDF using PyPDF2."""
        try:
            reader = PdfReader(file_path)
            text = ""
            # Extract from first 10 pages max
            max_pages = min(10, len(reader.pages))
            for page_num in range(max_pages):
                page = reader.pages[page_num]
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"Error extracting from searchable PDF: {e}")
            return ""

    async def _extract_text_from_scanned_pdf(self, file_path: str) -> str:
        """Extract text from scanned PDF using OCR."""
        try:
            # Convert PDF pages to images
            images = convert_from_path(
                file_path,
                first_page=1,
                last_page=10,  # Process max 10 pages
                dpi=300
            )

            text = ""
            for image in images:
                # Preprocess image
                processed_image = await self.preprocess_image(image)

                # Extract text
                page_text = pytesseract.image_to_string(
                    processed_image,
                    lang='+'.join(self.supported_languages),
                    timeout=self.ocr_timeout_sec
                )
                text += page_text + "\n"

            return text
        except Exception as e:
            print(f"Error extracting from scanned PDF: {e}")
            return ""

    async def _extract_header_fields(
        self,
        text: str,
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """Extract header fields (invoice number, dates, totals, etc.)."""
        fields = {}

        # Invoice/PO number patterns (try multiple variations)
        invoice_patterns = [
            r'(?:Invoice|Bill|Inv\.?)\s*(?:No\.?|Number|#)\s*:?\s*([A-Z0-9\-/]+)',
            r'(?:Tax\s+)?Invoice\s*:?\s*([A-Z0-9\-/]+)',
            r'Bill\s+(?:Number|No\.?)\s*:?\s*([A-Z0-9\-/]+)',
        ]
        po_patterns = [
            r'(?:Purchase\s+Order|PO|P\.O\.)\s*(?:No\.?|Number|#)\s*:?\s*([A-Z0-9\-/]+)',
            r'(?:Order|PO)\s+(?:Number|No\.?)\s*:?\s*([A-Z0-9\-/]+)',
        ]

        patterns = po_patterns if document_type == DocumentType.PURCHASE_ORDER else invoice_patterns

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                field_name = "po_number" if document_type == DocumentType.PURCHASE_ORDER else "invoice_number"
                fields[field_name] = match.group(1)
                fields[f"{field_name}_confidence"] = 1.0
                break

        # Date patterns (try multiple formats)
        date_patterns = [
            r'(?:Date|Dated)\s*:?\s*(\d{2}[-/\.]\d{2}[-/\.]\d{4})',
            r'(?:Invoice|Bill|PO)\s+Date\s*:?\s*(\d{2}[-/\.]\d{2}[-/\.]\d{4})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed_date = self._parse_date(date_str)
                if parsed_date:
                    field_name = "po_date" if document_type == DocumentType.PURCHASE_ORDER else "invoice_date"
                    fields[field_name] = parsed_date
                    fields[f"{field_name}_confidence"] = 0.9
                    break

        # Delivery date (for POs)
        if document_type == DocumentType.PURCHASE_ORDER:
            delivery_patterns = [
                r'(?:Expected|Delivery|Deliver\s+By)\s+Date\s*:?\s*(\d{2}[-/\.]\d{2}[-/\.]\d{4})',
            ]
            for pattern in delivery_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        fields["expected_delivery_date"] = parsed_date
                        fields["expected_delivery_date_confidence"] = 0.8

        # Total amount
        total_patterns = [
            r'(?:Total|Grand\s+Total|Net\s+Amount)\s*:?\s*(?:Rs\.?|₹)?\s*(\d+(?:[,\.]\d+)*)',
        ]

        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '').replace('.', '')
                try:
                    # Assume amount is in rupees, convert to paise
                    amount_inr = int(float(amount_str))
                    fields["total_amount_inr"] = amount_inr * 100  # Convert to paise
                    fields["total_amount_confidence"] = 0.9
                    break
                except ValueError:
                    pass

        return fields

    async def _extract_line_items(self, text: str) -> List[ExtractedItem]:
        """Extract line items from table in text."""
        items = []

        # Find table boundaries by looking for header keywords
        header_keywords = [
            'item', 'description', 'qty', 'quantity', 'rate', 'price',
            'amount', 'total', 'unit', 'uom'
        ]

        lines = text.split('\n')

        # Find header row
        header_row_idx = None
        for i, line in enumerate(lines):
            line_lower = line.lower()
            keyword_count = sum(1 for kw in header_keywords if kw in line_lower)
            if keyword_count >= 3:  # Header should have at least 3 keywords
                header_row_idx = i
                break

        if header_row_idx is None:
            return items  # No table found

        # Detect columns from header
        header_line = lines[header_row_idx]
        column_map = self._detect_columns(header_line)

        # Parse subsequent rows as items
        row_number = 1
        for i in range(header_row_idx + 1, len(lines)):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                continue

            # Try to parse as item row
            item = self._parse_item_row(line, column_map, row_number)
            if item:
                items.append(item)
                row_number += 1

            # Stop after footer keywords or 50 items
            if any(kw in line.lower() for kw in ['subtotal', 'total:', 'grand total']) or len(items) >= 50:
                break

        return items

    def _detect_columns(self, header_line: str) -> Dict[str, int]:
        """Detect column indices from header line."""
        column_map = {}
        header_lower = header_line.lower()

        # Simple column detection based on keywords
        item_keywords = ['item', 'description', 'material', 'product']
        qty_keywords = ['qty', 'quantity', 'quan']
        unit_keywords = ['unit', 'uom']
        rate_keywords = ['rate', 'price', 'cost']
        amount_keywords = ['amount', 'total']

        # For simplicity, use regex-based splitting
        # This is a simplified approach - real-world would need better column detection

        column_map['item_col'] = 0
        column_map['qty_col'] = 1
        column_map['unit_col'] = 2
        column_map['rate_col'] = 3
        column_map['amount_col'] = 4

        return column_map

    def _parse_item_row(
        self,
        line: str,
        column_map: Dict[str, int],
        row_number: int
    ) -> Optional[ExtractedItem]:
        """Parse a single item row."""
        # Split by multiple spaces or tabs (works for structured text extraction)
        parts = re.split(r'\s{2,}|\t', line.strip())

        # Fallback for OCR rows that collapse into single-space text:
        # "Potato 25,982 Gram 0.07 1,819"
        if len(parts) < 3:
            pattern = re.match(
                r"^(?P<material>.+?)\s+(?P<qty>\d[\d,]*(?:\.\d+)?)\s+"
                r"(?P<unit>[A-Za-z]+)\s+(?P<rate>\d[\d,]*(?:\.\d+)?)\s+"
                r"(?P<amount>\d[\d,]*(?:\.\d+)?)$",
                line.strip()
            )
            if pattern:
                parts = [
                    pattern.group("material"),
                    pattern.group("qty"),
                    pattern.group("unit"),
                    pattern.group("rate"),
                    pattern.group("amount"),
                ]
            else:
                return None  # Not enough data

        try:
            # Extract fields
            material_name = parts[0].strip() if len(parts) > 0 else ""
            quantity_str = parts[1].strip() if len(parts) > 1 else "0"
            unit = parts[2].strip() if len(parts) > 2 else "units"
            unit_cost_str = parts[3].strip() if len(parts) > 3 else "0"

            # Clean numeric strings
            quantity_str = re.sub(r'[^\d\.]', '', quantity_str)
            unit_cost_str = re.sub(r'[^\d\.]', '', unit_cost_str)

            # Parse numeric values
            quantity = float(quantity_str) if quantity_str else 0
            unit_cost_inr = int(float(unit_cost_str) * 100) if unit_cost_str else 0  # Convert to paise

            # Validate
            if not material_name or quantity <= 0:
                return None

            # Calculate confidence based on data quality
            confidence = 0.8 if unit_cost_inr > 0 else 0.6

            # Create ExtractedItem
            item = ExtractedItem(
                material_name=material_name,
                quantity=quantity,
                unit=unit,
                unit_cost_inr=unit_cost_inr,
                line_total_inr=int(quantity * unit_cost_inr),
                confidence_score=confidence,
                match_status=MatchStatus.UNMATCHED,
                row_number=row_number
            )

            return item

        except (ValueError, IndexError) as e:
            print(f"Error parsing item row: {e}")
            return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to YYYY-MM-DD format."""
        date_formats = [
            '%d/%m/%Y',      # 16/03/2026
            '%d-%m-%Y',      # 16-03-2026
            '%Y-%m-%d',      # 2026-03-16
            '%d.%m.%Y',      # 16.03.2026
            '%d %b %Y',      # 16 Mar 2026
            '%d %B %Y',      # 16 March 2026
        ]

        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue

        return None
