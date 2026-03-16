"""
Service for matching extracted items to inventory and POs to bills.
"""
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.models.document import (
    Bill,
    BillItem,
    ExtractedItem,
    MatchStatus,
    POStatus,
    PurchaseOrder,
    PurchaseOrderItem
)
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.purchase_order_repository import PurchaseOrderRepository

class ItemMatchingService:
    """Service for matching items and linking documents."""

    def __init__(self, inventory_repo: InventoryRepository):
        """
        Initialize item matching service.

        Args:
            inventory_repo: Repository for inventory operations
        """
        self.inventory_repo = inventory_repo
        self.price_variance_threshold = 0.05  # 5% threshold

    async def match_extracted_items(
        self,
        extracted_items: List[ExtractedItem]
    ) -> List[ExtractedItem]:
        """
        Match extracted items to inventory.

        Args:
            extracted_items: List of extracted items from OCR

        Returns:
            List of extracted items with match_status and matched_inventory_id updated
        """
        matched_items = []
        inventory_items = await self._get_all_inventory_items()
        normalized_inventory = [
            (inv, self._normalize_name(inv.get("material_name", "")))
            for inv in inventory_items
        ]

        for item in extracted_items:
            # Normalize material name for matching
            normalized_name = self._normalize_name(item.material_name)
            if not normalized_name:
                item.match_status = MatchStatus.UNMATCHED
                matched_items.append(item)
                continue

            # Try exact match (case-insensitive)
            inventory_item = await self.inventory_repo.find_by_name(normalized_name)

            if inventory_item:
                # Exact match found
                item.matched_inventory_id = str(inventory_item["_id"])
                item.match_status = MatchStatus.EXACT
            else:
                # Fallback to fuzzy token-overlap matching for OCR noise tolerance
                best_match = None
                best_score = 0.0
                for inv_item, inv_normalized_name in normalized_inventory:
                    if not inv_normalized_name:
                        continue

                    similarity = self._name_similarity(normalized_name, inv_normalized_name)
                    if similarity > best_score:
                        best_score = similarity
                        best_match = inv_item

                if best_match and best_score >= 0.65:
                    item.matched_inventory_id = str(best_match["_id"])
                    item.match_status = MatchStatus.EXACT
                else:
                    # No reliable match found
                    item.match_status = MatchStatus.UNMATCHED

            matched_items.append(item)

        return matched_items

    async def _get_all_inventory_items(self) -> List[Dict[str, Any]]:
        """Load all inventory items in repository-sized pages."""
        page_size = 100
        skip = 0
        all_items: List[Dict[str, Any]] = []

        while True:
            batch = await self.inventory_repo.get_all(skip=skip, limit=page_size)
            if not batch:
                break

            all_items.extend(batch)
            if len(batch) < page_size:
                break
            skip += page_size

        return all_items

    def _normalize_name(self, value: str) -> str:
        """Normalize item names for matching."""
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", value.lower())).strip()

    def _name_similarity(self, a: str, b: str) -> float:
        """Jaccard token similarity in [0, 1]."""
        a_tokens = set(a.split())
        b_tokens = set(b.split())
        if not a_tokens or not b_tokens:
            return 0.0

        intersection = len(a_tokens & b_tokens)
        union = len(a_tokens | b_tokens)
        return intersection / union if union else 0.0

    async def match_bill_to_po(
        self,
        bill: Bill,
        supplier_id: str,
        actual_delivery_date: Optional[str],
        po_repo: PurchaseOrderRepository
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Match a bill to an existing purchase order.

        Args:
            bill: The bill to match
            supplier_id: Supplier ID from bill
            actual_delivery_date: Actual delivery date from bill
            po_repo: Purchase order repository

        Returns:
            Tuple of (matched_po_id, price_variance_summary)
        """
        # Find open POs for the supplier
        candidate_pos = await po_repo.find_by_supplier_and_status(
            supplier_id=supplier_id,
            statuses=[POStatus.PENDING, POStatus.PARTIALLY_RECEIVED]
        )

        if not candidate_pos:
            return None, {}

        # Filter by date range if delivery date is available
        if actual_delivery_date:
            delivery_date = datetime.fromisoformat(actual_delivery_date)
            date_filtered_pos = []

            for po in candidate_pos:
                if po.expected_delivery_date:
                    expected_date = datetime.fromisoformat(po.expected_delivery_date)
                    # Check if within ±7 days
                    date_diff = abs((delivery_date - expected_date).days)
                    if date_diff <= 7:
                        date_filtered_pos.append(po)
                else:
                    # Include POs without expected date
                    date_filtered_pos.append(po)

            candidate_pos = date_filtered_pos if date_filtered_pos else candidate_pos

        # Calculate match score for each PO
        best_match = None
        best_score = 0.0

        for po in candidate_pos:
            score = self._calculate_po_match_score(bill, po)
            if score > best_score:
                best_score = score
                best_match = po

        # If match score > 0.7, consider it a match
        if best_match and best_score > 0.7:
            # Calculate price variances
            price_variance_summary = self.calculate_price_variances(
                bill.items,
                best_match.items
            )
            return str(best_match.id), price_variance_summary
        else:
            return None, {}

    def calculate_price_variances(
        self,
        bill_items: List[BillItem],
        po_items: List[PurchaseOrderItem]
    ) -> Dict[str, Any]:
        """
        Calculate price variances between bill and PO items.

        Args:
            bill_items: Items from bill
            po_items: Items from PO

        Returns:
            Dictionary with variance summary
        """
        variances = []
        total_variance_amount = 0
        has_significant_variances = False

        # Create mapping of PO items by inventory_id
        po_items_map = {item.inventory_id: item for item in po_items}

        for bill_item in bill_items:
            inventory_id = bill_item.inventory_id
            if inventory_id in po_items_map:
                po_item = po_items_map[inventory_id]

                # Calculate variance percentage
                po_cost = po_item.unit_cost_inr
                bill_cost = bill_item.unit_cost_inr

                if po_cost > 0:
                    variance_pct = ((bill_cost - po_cost) / po_cost) * 100
                    variance_amount = (bill_cost - po_cost) * bill_item.quantity

                    # Update bill item with variance info
                    bill_item.price_variance_pct = round(variance_pct, 2)
                    bill_item.po_unit_cost_inr = po_cost

                    # Check if variance exceeds threshold
                    if abs(variance_pct) > (self.price_variance_threshold * 100):
                        has_significant_variances = True
                        variances.append({
                            "material_name": bill_item.material_name,
                            "po_unit_cost_inr": po_cost,
                            "bill_unit_cost_inr": bill_cost,
                            "variance_pct": round(variance_pct, 2),
                            "variance_amount_inr": int(variance_amount),
                            "quantity": bill_item.quantity
                        })

                    total_variance_amount += int(variance_amount)

        return {
            "has_significant_variances": has_significant_variances,
            "total_variance_amount_inr": total_variance_amount,
            "item_variances": variances,
            "threshold_pct": self.price_variance_threshold * 100
        }

    def _calculate_po_match_score(
        self,
        bill: Bill,
        po: PurchaseOrder
    ) -> float:
        """
        Calculate match score between bill and PO.

        Args:
            bill: Bill to match
            po: Purchase order to compare

        Returns:
            Match score (0-1)
        """
        score = 0.0
        factors = 0

        # 1. Item overlap (most important factor)
        bill_item_ids = {item.inventory_id for item in bill.items}
        po_item_ids = {item.inventory_id for item in po.items}

        if bill_item_ids and po_item_ids:
            intersection = bill_item_ids & po_item_ids
            union = bill_item_ids | po_item_ids
            overlap_score = len(intersection) / len(union) if union else 0
            score += overlap_score * 0.5  # 50% weight
            factors += 0.5

        # 2. Total amount similarity
        if bill.total_amount_inr and po.total_amount_inr:
            amount_diff_pct = abs(
                bill.total_amount_inr - po.total_amount_inr
            ) / po.total_amount_inr

            if amount_diff_pct < 0.1:  # Within 10%
                amount_score = 1.0 - amount_diff_pct
                score += amount_score * 0.3  # 30% weight
                factors += 0.3

        # 3. Quantity match for common items
        quantity_matches = 0
        common_items = 0

        po_items_map = {item.inventory_id: item for item in po.items}

        for bill_item in bill.items:
            if bill_item.inventory_id in po_items_map:
                common_items += 1
                po_item = po_items_map[bill_item.inventory_id]

                # Check if quantity is similar (within 20%)
                qty_diff_pct = abs(
                    bill_item.quantity - po_item.quantity_ordered
                ) / po_item.quantity_ordered if po_item.quantity_ordered > 0 else 1

                if qty_diff_pct < 0.2:
                    quantity_matches += 1

        if common_items > 0:
            quantity_score = quantity_matches / common_items
            score += quantity_score * 0.2  # 20% weight
            factors += 0.2

        # Normalize score
        if factors > 0:
            return score / factors
        else:
            return 0.0

    async def update_po_received_quantities(
        self,
        po: PurchaseOrder,
        bill_items: List[BillItem],
        po_repo: PurchaseOrderRepository
    ) -> POStatus:
        """
        Update received quantities in PO based on bill.

        Args:
            po: Purchase order to update
            bill_items: Items from approved bill
            po_repo: Purchase order repository

        Returns:
            Updated PO status
        """
        # Create mapping of bill items by inventory_id
        bill_items_map = {item.inventory_id: item for item in bill_items}

        total_items = len(po.items)
        fully_received_items = 0

        # Update received quantities
        for po_item in po.items:
            if po_item.inventory_id in bill_items_map:
                bill_item = bill_items_map[po_item.inventory_id]
                po_item.quantity_received += bill_item.quantity

            # Check if fully received
            if po_item.quantity_received >= po_item.quantity_ordered:
                fully_received_items += 1

        # Determine new status
        if fully_received_items == total_items:
            new_status = POStatus.FULLY_RECEIVED
        elif fully_received_items > 0:
            new_status = POStatus.PARTIALLY_RECEIVED
        else:
            new_status = POStatus.PENDING

        # Update PO in database
        await po_repo.update(
            po_id=str(po.id),
            update_data={"items": po.items, "status": new_status}
        )

        return new_status
