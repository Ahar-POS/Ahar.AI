/**
 * MenuItemCard component.
 * 
 * Displays a single menu item with details and actions.
 */

import React, { useState } from 'react';
import { MenuItem, PREP_TYPE_LABELS, PREP_TYPE_COLORS, IngredientTag } from '../types/menu';
import { formatPrice } from '../utils/currency';
import ConfirmModal from './ConfirmModal';
import './MenuItemCard.css';

interface MenuItemCardProps {
  item: MenuItem;
  onEdit: (item: MenuItem) => void;
  onDelete: (itemId: string) => void;
  canEdit?: boolean;
}

/**
 * Menu item card component showing item details and action menu.
 */
export default function MenuItemCard({ item, onEdit, onDelete, canEdit = true }: MenuItemCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);

  /**
   * Get display text for ingredient tags.
   * Shows first 3 tags, then "+X more" if there are more.
   */
  const getTagDisplay = (tags: IngredientTag[]): string => {
    if (tags.length === 0) return '';
    if (tags.length <= 3) {
      return tags.join(', ');
    }
    const firstThree = tags.slice(0, 3).join(', ');
    const remaining = tags.length - 3;
    return `${firstThree}, +${remaining} more`;
  };

  const handleMenuToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(!showMenu);
  };

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(false);
    onEdit(item);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(false);
    setShowConfirmDelete(true);
  };

  const handleConfirmDelete = () => {
    setShowConfirmDelete(false);
    onDelete(item.id);
  };

  const handleCancelDelete = () => {
    setShowConfirmDelete(false);
  };

  return (
    <div className="menu-item-card">
      {/* Header with name and action menu */}
      <div className="menu-item-card-header">
        <h3 className="menu-item-card-name">{item.name}</h3>
        {canEdit && (
          <div className="menu-item-card-menu">
            <button
              type="button"
              className="menu-item-card-menu-button"
              onClick={handleMenuToggle}
              aria-label="Menu options"
              aria-expanded={showMenu}
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
                <circle cx="10" cy="4" r="1.5" />
                <circle cx="10" cy="10" r="1.5" />
                <circle cx="10" cy="16" r="1.5" />
              </svg>
            </button>
            {showMenu && (
              <div className="menu-item-card-menu-dropdown">
                <button
                  type="button"
                  className="menu-item-card-menu-item"
                  onClick={handleEdit}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="menu-item-card-menu-item menu-item-card-menu-item-danger"
                  onClick={handleDelete}
                >
                  Delete
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Description */}
      <p className="menu-item-card-description">{item.description}</p>

      {/* Price */}
      <div className="menu-item-card-price">{formatPrice(item.price)}</div>

      {/* Tags */}
      {item.tags.length > 0 && (
        <div className="menu-item-card-tags">
          <span className="menu-item-card-tags-label">Ingredients:</span>
          <span className="menu-item-card-tags-value">{getTagDisplay(item.tags)}</span>
        </div>
      )}

      {/* Prep type badge */}
      <div className="menu-item-card-footer">
        <span
          className="menu-item-card-prep-badge"
          style={{ backgroundColor: PREP_TYPE_COLORS[item.prep_type] }}
        >
          {PREP_TYPE_LABELS[item.prep_type]}
        </span>
        {!item.is_available && (
          <span className="menu-item-card-unavailable">Unavailable</span>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showConfirmDelete && (
        <ConfirmModal
          title="Delete Menu Item"
          message={`Are you sure you want to delete "${item.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          onConfirm={handleConfirmDelete}
          onCancel={handleCancelDelete}
          variant="danger"
        />
      )}
    </div>
  );
}
