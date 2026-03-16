#!/usr/bin/env python3
"""
Generate OCR-friendly Purchase Order and Bill PDFs from live inventory data.

This script reads the current MongoDB inventory, picks one supplier's items,
and creates a matching PO and Bill pair under output/pdf/.
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont
from pymongo import MongoClient


PAGE_WIDTH = 2480
PAGE_HEIGHT = 3508
PAGE_MARGIN = 170

TITLE_FONT = "/System/Library/Fonts/Supplemental/Verdana Bold.ttf"
BODY_FONT = "/System/Library/Fonts/Supplemental/Verdana.ttf"
BODY_BOLD_FONT = "/System/Library/Fonts/Supplemental/Verdana Bold.ttf"


@dataclass(frozen=True)
class SupplierDetails:
    supplier_id: str
    supplier_name: str
    contact_person: str
    phone: str
    email: str
    address: str
    city: str
    state: str
    pincode: str
    payment_terms: str


@dataclass(frozen=True)
class LineItem:
    material_id: str
    material_name: str
    quantity: float
    unit: str
    unit_cost_paise: int
    line_total_paise: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate OCR test PO and Bill PDFs from current MongoDB inventory."
    )
    parser.add_argument(
        "--mongodb-uri",
        default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"),
        help="MongoDB connection URI.",
    )
    parser.add_argument(
        "--db-name",
        default=os.environ.get("DB_NAME", "ahar_pos"),
        help="MongoDB database name.",
    )
    parser.add_argument(
        "--supplier-id",
        default=None,
        help="Optional supplier_id to force a specific supplier.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=8,
        help="Maximum number of line items to include from the selected supplier.",
    )
    parser.add_argument(
        "--buyer-name",
        default="Ahar.AI Test Kitchen",
        help="Buyer name shown on the documents.",
    )
    parser.add_argument(
        "--buyer-address",
        default="Bangalore, Karnataka 560001",
        help="Single-line buyer address.",
    )
    return parser.parse_args()


def escape_pdf_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{int(round(value)):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def format_rupees_from_paise(value_paise: int, decimals: bool = True) -> str:
    rupees = value_paise / 100.0
    if decimals:
        return f"{rupees:,.2f}"
    return f"{int(round(rupees)):,}"


def load_fonts() -> dict[str, ImageFont.FreeTypeFont]:
    return {
        "title": ImageFont.truetype(TITLE_FONT, 84),
        "subtitle": ImageFont.truetype(BODY_FONT, 34),
        "meta": ImageFont.truetype(BODY_FONT, 30),
        "section": ImageFont.truetype(BODY_BOLD_FONT, 34),
        "body": ImageFont.truetype(BODY_FONT, 28),
        "body_bold": ImageFont.truetype(BODY_BOLD_FONT, 28),
        "small": ImageFont.truetype(BODY_FONT, 24),
        "small_bold": ImageFont.truetype(BODY_BOLD_FONT, 24),
    }


def load_supplier_and_items(
    client: MongoClient,
    db_name: str,
    requested_supplier_id: str | None,
    max_items: int,
) -> tuple[SupplierDetails, list[LineItem]]:
    db = client[db_name]

    supplier_lookup = {
        doc["supplier_id"]: doc
        for doc in db.suppliers.find({"is_active": True})
        if doc.get("supplier_id")
    }

    grouped_items: dict[str, list[dict]] = defaultdict(list)
    query = {"supplier_id": requested_supplier_id} if requested_supplier_id else {}
    for doc in db.raw_material_inventory.find(query).sort("material_id", 1):
        supplier_id = doc.get("supplier_id")
        if supplier_id in supplier_lookup:
            grouped_items[supplier_id].append(doc)

    if requested_supplier_id:
        chosen_supplier_id = requested_supplier_id
    else:
        ranked_suppliers = sorted(
            grouped_items.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
        if not ranked_suppliers:
            raise RuntimeError("No supplier-backed inventory items found in raw_material_inventory.")
        chosen_supplier_id = ranked_suppliers[0][0]

    if chosen_supplier_id not in supplier_lookup:
        raise RuntimeError(f"Supplier {chosen_supplier_id} not found in suppliers collection.")

    selected_docs = grouped_items.get(chosen_supplier_id, [])
    if not selected_docs:
        raise RuntimeError(f"No inventory rows found for supplier {chosen_supplier_id}.")

    supplier_doc = supplier_lookup[chosen_supplier_id]
    supplier = SupplierDetails(
        supplier_id=supplier_doc["supplier_id"],
        supplier_name=supplier_doc.get("supplier_name", chosen_supplier_id),
        contact_person=supplier_doc.get("contact_person", ""),
        phone=supplier_doc.get("phone", ""),
        email=supplier_doc.get("email", ""),
        address=supplier_doc.get("address", ""),
        city=supplier_doc.get("city", ""),
        state=supplier_doc.get("state", ""),
        pincode=str(supplier_doc.get("pincode", "")),
        payment_terms=supplier_doc.get("payment_terms", ""),
    )

    items: list[LineItem] = []
    for doc in selected_docs[:max_items]:
        quantity = float(doc.get("reorder_qty", 0))
        unit_cost_paise = int(round(float(doc.get("unit_cost_inr", 0))))
        line_total_paise = int(round(quantity * unit_cost_paise))
        items.append(
            LineItem(
                material_id=doc.get("material_id", ""),
                material_name=doc.get("material_name", "Unknown Item"),
                quantity=quantity,
                unit=doc.get("unit", "Unit"),
                unit_cost_paise=unit_cost_paise,
                line_total_paise=line_total_paise,
            )
        )

    return supplier, items


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    x: float,
    start_y: float,
    lines: Iterable[str],
    *,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] = (36, 36, 36),
    line_gap: float = 14,
) -> None:
    current_y = start_y
    for line in lines:
        draw.text((x, current_y), line, font=font, fill=fill)
        current_y += line_gap


def draw_right_aligned_text(
    draw: ImageDraw.ImageDraw,
    right_x: float,
    y: float,
    text: str,
    *,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] = (36, 36, 36),
) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    width = right - left
    draw.text((right_x - width, y), text, font=font, fill=fill)


def build_document_pdf(
    *,
    title: str,
    document_number_label: str,
    document_number: str,
    date_label: str,
    document_date: date,
    extra_label: str,
    extra_value: str,
    supplier: SupplierDetails,
    buyer_name: str,
    buyer_address: str,
    items: list[LineItem],
    total_paise: int,
    footer_note: str,
    output_path: Path,
) -> None:
    fonts = load_fonts()
    image = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    ink = (32, 34, 40)
    muted = (86, 92, 102)
    border = (214, 219, 227)
    panel = (247, 249, 252)
    header_fill = (231, 237, 245)

    left_margin = PAGE_MARGIN
    right_margin = PAGE_WIDTH - PAGE_MARGIN

    draw.text((left_margin, 170), title, font=fonts["title"], fill=ink)
    draw.text((left_margin, 295), "OCR Upload Test Document", font=fonts["subtitle"], fill=muted)
    draw.line((left_margin, 360, right_margin, 360), fill=(185, 192, 201), width=4)

    meta_x = 1620
    draw_text_block(
        draw,
        meta_x,
        210,
        [
            f"{document_number_label}: {document_number}",
            f"{date_label}: {document_date.strftime('%d/%m/%Y')}",
            f"{extra_label}: {extra_value}",
            f"Supplier ID: {supplier.supplier_id}",
        ],
        font=fonts["meta"],
        fill=ink,
        line_gap=52,
    )

    seller_box = (left_margin, 470, 1140, 1010)
    buyer_box = (1290, 470, right_margin, 1010)
    draw.rounded_rectangle(seller_box, radius=24, fill=panel, outline=border, width=4)
    draw.rounded_rectangle(buyer_box, radius=24, fill=panel, outline=border, width=4)

    draw.text((left_margin + 36, 520), "Supplier", font=fonts["section"], fill=ink)
    draw_text_block(
        draw,
        left_margin + 36,
        590,
        [
            supplier.supplier_name,
            supplier.contact_person,
            supplier.address,
            f"{supplier.city}, {supplier.state} {supplier.pincode}",
            supplier.phone,
            supplier.email,
            f"Payment Terms: {supplier.payment_terms}",
        ],
        font=fonts["body"],
        fill=ink,
        line_gap=48,
    )

    draw.text((1326, 520), "Bill To", font=fonts["section"], fill=ink)
    draw_text_block(
        draw,
        1326,
        590,
        [
            buyer_name,
            buyer_address,
            "Ops Contact: inventory-testing@ahar.ai",
            "Purpose: OCR QA upload sample",
        ],
        font=fonts["body"],
        fill=ink,
        line_gap=52,
    )

    table_left = left_margin
    table_right = right_margin
    table_top = 1120
    header_bottom = table_top + 92
    draw.rounded_rectangle(
        (table_left, table_top, table_right, header_bottom),
        radius=18,
        fill=header_fill,
        outline=border,
        width=3,
    )
    column_x = {
        "item": table_left + 34,
        "qty": 1360,
        "unit": 1650,
        "rate": 1900,
        "amount": table_right - 40,
    }
    draw.text((column_x["item"], table_top + 25), "Item Description", font=fonts["body_bold"], fill=ink)
    draw_right_aligned_text(draw, column_x["qty"] + 120, table_top + 25, "Qty", font=fonts["body_bold"], fill=ink)
    draw.text((column_x["unit"], table_top + 25), "Unit", font=fonts["body_bold"], fill=ink)
    draw_right_aligned_text(draw, column_x["rate"] + 120, table_top + 25, "Rate", font=fonts["body_bold"], fill=ink)
    draw_right_aligned_text(draw, column_x["amount"], table_top + 25, "Amount", font=fonts["body_bold"], fill=ink)

    row_y = header_bottom + 18
    row_height = 116
    for item in items:
        draw.rounded_rectangle(
            (table_left, row_y, table_right, row_y + row_height),
            radius=14,
            fill=(255, 255, 255),
            outline=border,
            width=3,
        )
        baseline = row_y + 32
        draw.text((column_x["item"], baseline), item.material_name, font=fonts["body"], fill=ink)
        draw_right_aligned_text(
            draw,
            column_x["qty"] + 120,
            baseline,
            format_number(item.quantity),
            font=fonts["body"],
            fill=ink,
        )
        draw.text((column_x["unit"], baseline), item.unit, font=fonts["body"], fill=ink)
        draw_right_aligned_text(
            draw,
            column_x["rate"] + 120,
            baseline,
            format_rupees_from_paise(item.unit_cost_paise),
            font=fonts["body"],
            fill=ink,
        )
        draw_right_aligned_text(
            draw,
            column_x["amount"],
            baseline,
            format_rupees_from_paise(item.line_total_paise, decimals=False),
            font=fonts["body"],
            fill=ink,
        )
        row_y += row_height + 16

    totals_top = row_y + 24
    totals_box = (1450, totals_top, right_margin, totals_top + 250)
    draw.rounded_rectangle(totals_box, radius=24, fill=panel, outline=border, width=4)
    draw_text_block(
        draw,
        1490,
        totals_top + 38,
        [
            f"Subtotal: Rs. {format_rupees_from_paise(total_paise, decimals=False)}",
            "Tax: Rs. 0",
            f"Grand Total: Rs. {format_rupees_from_paise(total_paise, decimals=False)}",
        ],
        font=fonts["body_bold"],
        fill=ink,
        line_gap=72,
    )

    notes_top = totals_top
    draw.text((left_margin, notes_top), "Notes", font=fonts["section"], fill=ink)
    draw_text_block(
        draw,
        left_margin,
        notes_top + 72,
        [
            footer_note,
            "Source: raw_material_inventory in the live MongoDB.",
            "Layout tuned for the current OCR upload parser.",
        ],
        font=fonts["body"],
        fill=ink,
        line_gap=56,
    )

    footer_y = PAGE_HEIGHT - 140
    draw.line((left_margin, footer_y, right_margin, footer_y), fill=(185, 192, 201), width=3)
    draw.text((left_margin, footer_y + 28), "Generated locally for OCR upload testing.", font=fonts["small"], fill=muted)
    draw_right_aligned_text(
        draw,
        right_margin,
        footer_y + 28,
        "Prepared by Codex script",
        font=fonts["small"],
        fill=muted,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "PDF", resolution=300.0)


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = repo_root / "output" / "pdf"
    output_dir.mkdir(parents=True, exist_ok=True)

    client = MongoClient(args.mongodb_uri, serverSelectionTimeoutMS=5000)
    supplier, items = load_supplier_and_items(
        client=client,
        db_name=args.db_name,
        requested_supplier_id=args.supplier_id,
        max_items=args.max_items,
    )

    po_date = date.today()
    bill_date = po_date + timedelta(days=2)
    po_number = f"PO-{po_date.strftime('%Y%m%d')}-{supplier.supplier_id}"
    invoice_number = f"INV-{bill_date.strftime('%Y%m%d')}-{supplier.supplier_id}"
    total_paise = sum(item.line_total_paise for item in items)

    po_path = output_dir / f"test_purchase_order_{supplier.supplier_id.lower()}.pdf"
    bill_path = output_dir / f"test_bill_{supplier.supplier_id.lower()}.pdf"

    build_document_pdf(
        title="PURCHASE ORDER",
        document_number_label="PO Number",
        document_number=po_number,
        date_label="PO Date",
        document_date=po_date,
        extra_label="Expected Delivery Date",
        extra_value=bill_date.strftime("%d/%m/%Y"),
        supplier=supplier,
        buyer_name=args.buyer_name,
        buyer_address=args.buyer_address,
        items=items,
        total_paise=total_paise,
        footer_note="Test PO built from live supplier inventory and reorder quantities.",
        output_path=po_path,
    )

    build_document_pdf(
        title="TAX INVOICE",
        document_number_label="Invoice No",
        document_number=invoice_number,
        date_label="Invoice Date",
        document_date=bill_date,
        extra_label="Reference PO No",
        extra_value=po_number,
        supplier=supplier,
        buyer_name=args.buyer_name,
        buyer_address=args.buyer_address,
        items=items,
        total_paise=total_paise,
        footer_note="Test Bill mirrors the PO item set for end-to-end OCR upload checks.",
        output_path=bill_path,
    )

    print(f"Selected supplier: {supplier.supplier_id} - {supplier.supplier_name}")
    print(f"Line items: {len(items)}")
    for item in items:
        print(
            f"  {item.material_id} | {item.material_name} | "
            f"qty={format_number(item.quantity)} {item.unit} | "
            f"rate=Rs. {format_rupees_from_paise(item.unit_cost_paise)}"
        )
    print(f"Purchase Order PDF: {po_path}")
    print(f"Bill PDF: {bill_path}")


if __name__ == "__main__":
    main()
