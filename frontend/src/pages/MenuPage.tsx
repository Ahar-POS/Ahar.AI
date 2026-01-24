/**
 * MenuPage component.
 * 
 * Main page for managing restaurant menu items.
 */

import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { MenuItem, CreateMenuItemData, UpdateMenuItemData } from '../types/menu';
import {
  getMenuItems,
  getCategories,
  createMenuItem,
  updateMenuItem,
  deleteMenuItem,
} from '../services/menu';
import { useAuth } from '../contexts/AuthContext';
import MenuItemCard from '../components/MenuItemCard';
import MenuItemForm from '../components/MenuItemForm';
import './MenuPage.css';

/**
 * Menu management page component.
 */
export default function MenuPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<MenuItem[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);
  const [includeInactive, setIncludeInactive] = useState(false);

  // Check if user can edit (admin role)
  const canEdit = user?.role === 'admin';

  /**
   * Load menu items and categories from API.
   */
  const loadMenuData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [itemsData, categoriesData] = await Promise.all([
        getMenuItems(includeInactive),
        getCategories(),
      ]);
      
      setItems(itemsData);
      setCategories(categoriesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load menu items');
    } finally {
      setLoading(false);
    }
  }, [includeInactive]);

  /**
   * Load data on component mount and when includeInactive changes.
   */
  useEffect(() => {
    loadMenuData();
  }, [loadMenuData]);

  /**
   * Group items by category.
   */
  const itemsByCategory = useMemo(() => {
    const grouped: Record<string, MenuItem[]> = {};
    
    items.forEach((item) => {
      if (!grouped[item.category]) {
        grouped[item.category] = [];
      }
      grouped[item.category].push(item);
    });
    
    // Sort categories alphabetically
    const sortedCategories = Object.keys(grouped).sort();
    const result: Record<string, MenuItem[]> = {};
    sortedCategories.forEach((cat) => {
      result[cat] = grouped[cat];
    });
    
    return result;
  }, [items]);

  /**
   * Calculate menu statistics.
   */
  const stats = useMemo(() => {
    const totalItems = items.length;
    const totalCategories = Object.keys(itemsByCategory).length;
    const availableItems = items.filter((item) => item.is_available).length;
    const unavailableItems = totalItems - availableItems;
    
    return {
      totalItems,
      totalCategories,
      availableItems,
      unavailableItems,
    };
  }, [items, itemsByCategory]);

  /**
   * Handle Add Item button click.
   */
  const handleAddItemClick = () => {
    setEditingItem(null);
    setShowAddModal(true);
  };

  /**
   * Handle Edit Item.
   */
  const handleEditItem = (item: MenuItem) => {
    setEditingItem(item);
    setShowAddModal(true);
  };

  /**
   * Handle Delete Item.
   */
  const handleDeleteItem = async (itemId: string) => {
    try {
      await deleteMenuItem(itemId);
      await loadMenuData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete menu item');
    }
  };

  /**
   * Handle form submission (create or update).
   */
  const handleFormSubmit = async (
    data: CreateMenuItemData | UpdateMenuItemData
  ) => {
    try {
      if (editingItem) {
        await updateMenuItem(editingItem.id, data as UpdateMenuItemData);
      } else {
        await createMenuItem(data as CreateMenuItemData);
      }
      await loadMenuData();
      setShowAddModal(false);
      setEditingItem(null);
    } catch (err) {
      throw err; // Let form handle the error display
    }
  };

  /**
   * Handle modal close.
   */
  const handleModalClose = () => {
    setShowAddModal(false);
    setEditingItem(null);
  };

  return (
    <div className="menu-page">
      {/* Header */}
      <div className="menu-page-header">
        <div>
          <h1 className="menu-page-title">Menu Management</h1>
          <p className="menu-page-subtitle">
            {stats.totalItems} item{stats.totalItems !== 1 ? 's' : ''} across{' '}
            {stats.totalCategories} categor{stats.totalCategories !== 1 ? 'ies' : 'y'}
          </p>
        </div>

        <div className="menu-page-header-actions">
          <label className="menu-page-toggle">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
            />
            <span>Show inactive items</span>
          </label>
          
          {canEdit && (
            <button
              type="button"
              className="btn btn-primary menu-page-add-btn"
              onClick={handleAddItemClick}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <path d="M10 4v12m-6-6h12" strokeLinecap="round" />
              </svg>
              Add Item
            </button>
          )}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="menu-page-error">
          <p>{error}</p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadMenuData}
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="menu-page-loading">
          <div className="spinner" />
          <p>Loading menu items...</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && items.length === 0 && (
        <div className="menu-page-empty">
          <p>No menu items found</p>
          {canEdit && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleAddItemClick}
            >
              Add Your First Item
            </button>
          )}
        </div>
      )}

      {/* Menu items by category */}
      {!loading && !error && items.length > 0 && (
        <div className="menu-page-content">
          {Object.entries(itemsByCategory).map(([category, categoryItems]) => (
            <div key={category} className="menu-page-category">
              <h2 className="menu-page-category-title">
                {category} ({categoryItems.length})
              </h2>
              <div className="menu-page-items-grid">
                {categoryItems.map((item) => (
                  <MenuItemCard
                    key={item.id}
                    item={item}
                    onEdit={handleEditItem}
                    onDelete={handleDeleteItem}
                    canEdit={canEdit}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit Modal */}
      {showAddModal && (
        <MenuItemForm
          item={editingItem}
          categories={categories}
          onClose={handleModalClose}
          onSubmit={handleFormSubmit}
        />
      )}
    </div>
  );
}
