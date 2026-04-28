/**
 * Utility functions for displaying inventory quantities in human-readable units.
 *
 * Internally, all stock is stored in base units (grams for solids, mL for liquids)
 * to keep recipe BOM deduction math precise and lossless. These helpers convert
 * only at display time — nothing in storage or deduction logic is affected.
 */

export interface DisplayQuantity {
  /** Formatted numeric string, e.g. "7.3" or "250" */
  value: string;
  /** Human-readable unit label, e.g. "kg", "g", "L", "mL", "pc" */
  unit: string;
  /** Cost per display unit, e.g. "₹450.00/kg" */
  costPerUnit: string;
}

/**
 * Convert a raw stock value and unit cost to human-readable display values.
 *
 * Rules:
 *  - "Gram" >= 1000  → kg (cost × 1000)
 *  - "Gram" < 1000   → g
 *  - "ML"   >= 1000  → L  (cost × 1000)
 *  - "ML"   < 1000   → mL
 *  - "Piece"         → pc (as-is)
 *  - unknown         → pass through
 *
 * @param stock         - Raw quantity in base units as stored in DB
 * @param storedUnit    - The `unit` field from DB: "Gram", "ML", "Piece", etc.
 * @param unitCostPaise - Cost in paise per base unit (e.g. 45 = ₹0.45/g)
 */
export function formatInventoryQuantity(
  stock: number,
  storedUnit: string,
  unitCostPaise: number
): DisplayQuantity {
  const safeStock = isFinite(stock) ? stock : 0;
  const safeCost = isFinite(unitCostPaise) ? unitCostPaise : 0;
  const norm = (storedUnit ?? '').trim().toLowerCase();

  let value: string;
  let unit: string;
  let costFactor: number; // multiply paise/base-unit to get paise/display-unit

  if (norm === 'gram') {
    if (safeStock >= 1000) {
      value = (safeStock / 1000).toFixed(1);
      unit = 'kg';
      costFactor = 1000;
    } else {
      value = safeStock.toFixed(0);
      unit = 'g';
      costFactor = 1;
    }
  } else if (norm === 'ml') {
    if (safeStock >= 1000) {
      value = (safeStock / 1000).toFixed(1);
      unit = 'L';
      costFactor = 1000;
    } else {
      value = safeStock.toFixed(0);
      unit = 'mL';
      costFactor = 1;
    }
  } else if (norm === 'piece') {
    value = safeStock.toFixed(0);
    unit = 'pc';
    costFactor = 1;
  } else {
    value = safeStock.toFixed(0);
    unit = storedUnit ?? '';
    costFactor = 1;
  }

  const costInRupees = (safeCost * costFactor) / 100;
  const costPerUnit = `₹${costInRupees.toFixed(2)}/${unit}`;

  return { value, unit, costPerUnit };
}

/**
 * Convenience wrapper — returns a single "value unit" string for displaying
 * stock quantities without cost context (e.g. reorder level, max stock).
 *
 * Examples: "7.3 kg", "250 g", "6.8 L", "500 pc"
 */
export function formatStockDisplay(stock: number, storedUnit: string): string {
  const { value, unit } = formatInventoryQuantity(stock, storedUnit, 0);
  return `${value} ${unit}`;
}
