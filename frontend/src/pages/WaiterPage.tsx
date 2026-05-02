/**
 * WaiterPage component.
 *
 * Main page for waiters to create orders by selecting tables and menu items.
 */

import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { MenuItem } from '../types/menu';
import { Table } from '../types/tables';
import { CreateOrderItem, OrderType } from '../types/orders';
import { getMenuItems, getCategories } from '../services/menu';
import { getTables } from '../services/tables';
import { createOrder, sendOrderToKitchen } from '../services/orders';
import { formatPrice } from '../utils/currency';
import { getActivePromotions, ActivePromotion } from '../services/promotions';
import OrderItemSelector from '../components/OrderItemSelector';
import './WaiterPage.css';

/**
 * Waiter page component for order creation.
 */
export default function WaiterPage() {
  const [tables, setTables] = useState<Table[]>([]);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [orderItems, setOrderItems] = useState<Map<string, CreateOrderItem>>(new Map());
  const [activePromotions, setActivePromotions] = useState<ActivePromotion[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Load tables and menu data.
   */
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [tablesData, itemsData, categoriesData, promosData] = await Promise.all([
        getTables(false), // Only active tables
        getMenuItems(false), // Only active items
        getCategories(),
        getActivePromotions(),
      ]);

      setTables(tablesData);
      // Filter to only available items (getMenuItems(false) returns active items,
      // but we also need to filter by is_available flag for real-time availability)
      setMenuItems(itemsData.filter(item => item.is_available));
      setCategories(categoriesData);
      setActivePromotions(promosData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Set initial category selection when categories are loaded.
   */
  useEffect(() => {
    if (categories.length > 0 && !selectedCategory) {
      setSelectedCategory(categories[0]);
    }
  }, [categories, selectedCategory]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /**
   * Group menu items by category.
   */
  const itemsByCategory = useMemo(() => {
    const grouped: Record<string, MenuItem[]> = {};

    menuItems.forEach((item) => {
      if (!grouped[item.category]) {
        grouped[item.category] = [];
      }
      grouped[item.category].push(item);
    });

    return grouped;
  }, [menuItems]);

  /**
   * Get items for selected category.
   */
  const categoryItems = useMemo(() => {
    if (!selectedCategory) return [];
    return itemsByCategory[selectedCategory] || [];
  }, [selectedCategory, itemsByCategory]);

  /**
   * Map from menu_item_id to its active promotion (if any).
   */
  const promoMap = useMemo(() =>
    activePromotions.reduce<Record<string, ActivePromotion>>((map, p) => {
      p.menu_item_ids_array.forEach(id => { map[id] = p; });
      return map;
    }, {}),
    [activePromotions]
  );

  /**
   * Whether the order has at least one item (quantity > 0).
   */
  const hasOrderItems = useMemo(() => {
    return Array.from(orderItems.values()).some((item) => item.quantity > 0);
  }, [orderItems]);

  /**
   * Calculate running total (price in paise).
   */
  const totalAmount = useMemo(() => {
    let total = 0;
    orderItems.forEach((item) => {
      if (item.quantity > 0) {
        const menuItem = menuItems.find(m => m.id === item.menu_item_id);
        if (menuItem && typeof menuItem.price === 'number') {
          total += menuItem.price * item.quantity;
        }
      }
    });
    return total;
  }, [orderItems, menuItems]);

  /**
   * Handle quantity change for an item.
   */
  const handleQuantityChange = (item: CreateOrderItem) => {
    setOrderItems(prev => {
      const newMap = new Map(prev);
      if (item.quantity > 0) {
        newMap.set(item.menu_item_id, item);
      } else {
        newMap.delete(item.menu_item_id);
      }
      return newMap;
    });
  };

  /**
   * Handle send to kitchen.
   */
  const handleSendToKitchen = async () => {
    if (!selectedTableId) {
      setError('Please select a table');
      return;
    }

    const items = Array.from(orderItems.values()).filter(item => item.quantity > 0);
    if (items.length === 0) {
      setError('Please add at least one item to the order');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      // Create order
      const order = await createOrder({
        order_type: OrderType.DINE_IN,
        table_id: selectedTableId,
        items,
      });

      // Send to kitchen
      await sendOrderToKitchen(order.id);

      // Reset form
      setSelectedTableId('');
      setOrderItems(new Map());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send order to kitchen');
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * Get table display name.
   */
  const getTableDisplayName = (table: Table): string => {
    return `Table ${table.table_number} — ${table.location}`;
  };

  if (loading) {
    return (
      <div className="waiter-page">
        <div className="waiter-page-loading">
          <div className="spinner" />
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="waiter-page">
      {/* Header */}
      <div className="waiter-page-header">
        <h1 className="waiter-page-title">New Order</h1>
      </div>

      {/* Error message */}
      {error && (
        <div className="waiter-page-error">
          <p>{error}</p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Table selection */}
      <div className="waiter-page-section">
        <label htmlFor="table-select" className="waiter-page-label">
          Select Table
        </label>
        <select
          id="table-select"
          className="waiter-page-select"
          value={selectedTableId}
          onChange={(e) => setSelectedTableId(e.target.value)}
        >
          <option value="">Select table</option>
          {tables.map((table) => (
            <option key={table.id} value={table.id}>
              {getTableDisplayName(table)}
            </option>
          ))}
        </select>
      </div>

      {/* Active promotions banner */}
      {activePromotions.length > 0 && (
        <div className="waiter-promo-banner">
          <span className="waiter-promo-banner-label">Today's Promos</span>
          <div className="waiter-promo-chips">
            {activePromotions.map(p => (
              <span key={p.promo_id} className="waiter-promo-chip">
                {p.discount_pct}% off · {p.menu_item_names.join(', ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Category navigation */}
      {categories.length > 0 && (
        <div className="waiter-page-section">
          <div className="waiter-page-categories">
            {categories.map((category) => (
              <button
                key={category}
                type="button"
                className={`waiter-page-category-btn ${
                  selectedCategory === category ? 'active' : ''
                }`}
                onClick={() => setSelectedCategory(category)}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Menu items */}
      {categoryItems.length > 0 && (
        <div className="waiter-page-section">
          <div className="waiter-page-items">
            {categoryItems.map((item) => (
              <OrderItemSelector
                key={item.id}
                item={item}
                onQuantityChange={handleQuantityChange}
                promo={promoMap[item.id] ?? null}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty state when no available menu items */}
      {!loading && !error && menuItems.length === 0 && (
        <div className="waiter-page-empty">
          <p>No available menu items to order.</p>
          <p className="waiter-page-empty-hint">
            Mark items as available in Menu to show them here.
          </p>
        </div>
      )}

      {/* Order summary and actions: show when there are items so user can send to kitchen */}
      {hasOrderItems && (
        <div className="waiter-page-footer">
          <div className="waiter-page-summary">
            <span className="waiter-page-summary-label">Total:</span>
            <span className="waiter-page-summary-amount">{formatPrice(totalAmount)}</span>
          </div>
          <button
            type="button"
            className="btn btn-primary waiter-page-send-btn"
            onClick={handleSendToKitchen}
            disabled={submitting || !selectedTableId}
          >
            {submitting ? 'Sending...' : 'Send to Kitchen'}
          </button>
        </div>
      )}
    </div>
  );
}
