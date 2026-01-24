/**
 * Currency formatting utilities.
 * 
 * Handles conversion and display of prices in Rupees (₹).
 * Backend stores prices in paise (smallest currency unit).
 */

/**
 * Format price from paise to Rupees with symbol.
 * 
 * @param paise - Price in paise (e.g., 12500)
 * @returns Formatted price string (e.g., "₹125.00")
 */
export function formatPrice(paise: number): string {
  const rupees = paise / 100;
  return `₹${rupees.toFixed(2)}`;
}

/**
 * Convert Rupees to paise.
 * 
 * @param rupees - Price in Rupees (e.g., 125.50)
 * @returns Price in paise (e.g., 12550)
 */
export function rupeesToPaise(rupees: number): number {
  return Math.round(rupees * 100);
}

/**
 * Convert paise to Rupees.
 * 
 * @param paise - Price in paise (e.g., 12550)
 * @returns Price in Rupees (e.g., 125.50)
 */
export function paiseToRupees(paise: number): number {
  return paise / 100;
}
