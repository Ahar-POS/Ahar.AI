/**
 * OrderItemSelector component.
 * 
 * Displays a menu item with quantity selector and notes field for order creation.
 */

import React, { useState } from 'react';
import { MenuItem } from '../types/menu';
import { CreateOrderItem } from '../types/orders';
import { formatPrice } from '../utils/currency';
import './OrderItemSelector.css';

interface OrderItemSelectorProps {
  item: MenuItem;
  onQuantityChange: (item: CreateOrderItem) => void;
}

/**
 * Order item selector component for waiter view.
 */
export default function OrderItemSelector({
  item,
  onQuantityChange,
}: OrderItemSelectorProps) {
  const [quantity, setQuantity] = useState(0);
  const [notes, setNotes] = useState('');

  const handleIncrement = () => {
    const newQuantity = quantity + 1;
    setQuantity(newQuantity);
    onQuantityChange({
      menu_item_id: item.id,
      quantity: newQuantity,
      notes: notes.trim() || undefined,
    });
  };

  const handleDecrement = () => {
    if (quantity > 0) {
      const newQuantity = quantity - 1;
      setQuantity(newQuantity);
      onQuantityChange({
        menu_item_id: item.id,
        quantity: newQuantity,
        notes: newQuantity > 0 ? (notes.trim() || undefined) : undefined,
      });
    }
  };

  const handleNotesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newNotes = e.target.value;
    setNotes(newNotes);
    if (quantity > 0) {
      onQuantityChange({
        menu_item_id: item.id,
        quantity,
        notes: newNotes.trim() || undefined,
      });
    }
  };

  return (
    <div className="order-item-selector">
      <div className="order-item-selector-main">
        <div className="order-item-selector-info">
          <h4 className="order-item-selector-name">{item.name}</h4>
          <p className="order-item-selector-description">{item.description}</p>
          <div className="order-item-selector-price">{formatPrice(item.price)}</div>
        </div>
        
        <div className="order-item-selector-controls">
          <button
            type="button"
            className="order-item-selector-btn order-item-selector-btn-decrement"
            onClick={handleDecrement}
            disabled={quantity === 0}
            aria-label="Decrease quantity"
          >
            −
          </button>
          <span className="order-item-selector-quantity">{quantity}</span>
          <button
            type="button"
            className="order-item-selector-btn order-item-selector-btn-increment"
            onClick={handleIncrement}
            disabled={!item.is_available}
            aria-label="Increase quantity"
          >
            +
          </button>
        </div>
      </div>
      
      {quantity > 0 && (
        <div className="order-item-selector-notes">
          <input
            type="text"
            className="order-item-selector-notes-input"
            placeholder="Special instructions (e.g., no garlic, extra spicy)"
            value={notes}
            onChange={handleNotesChange}
            maxLength={500}
          />
        </div>
      )}
    </div>
  );
}
