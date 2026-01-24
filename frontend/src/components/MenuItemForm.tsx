/**
 * MenuItemForm component.
 * 
 * Modal form for creating and editing menu items.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  MenuItem,
  CreateMenuItemData,
  UpdateMenuItemData,
  IngredientTag,
  PrepType,
  PREP_TYPE_LABELS,
} from '../types/menu';
import { rupeesToPaise, paiseToRupees } from '../utils/currency';
import './MenuItemForm.css';

interface MenuItemFormProps {
  item?: MenuItem | null;
  categories: string[];
  onClose: () => void;
  onSubmit: (data: CreateMenuItemData | UpdateMenuItemData) => Promise<void>;
}

/**
 * Menu item form modal component.
 */
export default function MenuItemForm({
  item,
  categories,
  onClose,
  onSubmit,
}: MenuItemFormProps) {
  const isEditing = !!item;

  // Form state
  const [name, setName] = useState(item?.name || '');
  const [description, setDescription] = useState(item?.description || '');
  const [priceRupees, setPriceRupees] = useState(
    item ? paiseToRupees(item.price).toString() : ''
  );
  const [category, setCategory] = useState(item?.category || '');
  const [categoryInput, setCategoryInput] = useState(item?.category || '');
  const [selectedTags, setSelectedTags] = useState<IngredientTag[]>(
    item?.tags || []
  );
  const [customIngredients, setCustomIngredients] = useState<string[]>([]);
  const [ingredientInput, setIngredientInput] = useState('');
  const [prepType, setPrepType] = useState<PrepType>(
    item?.prep_type || PrepType.COLD
  );
  const [isAvailable, setIsAvailable] = useState(item?.is_available ?? true);

  // UI state
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showCategorySuggestions, setShowCategorySuggestions] = useState(false);
  const categoryDropdownTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Filter categories based on input
  const filteredCategories = categories.filter((cat) =>
    cat.toLowerCase().includes(categoryInput.toLowerCase())
  );

  // Available ingredient tags (all tags from enum)
  const allTags = Object.values(IngredientTag);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (categoryDropdownTimeoutRef.current) {
        clearTimeout(categoryDropdownTimeoutRef.current);
      }
    };
  }, []);

  /**
   * Validate form data.
   */
  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!name.trim()) {
      newErrors.name = 'Name is required';
    } else if (name.length > 100) {
      newErrors.name = 'Name must be 100 characters or less';
    }

    if (!description.trim()) {
      newErrors.description = 'Description is required';
    } else if (description.length > 500) {
      newErrors.description = 'Description must be 500 characters or less';
    }

    const price = parseFloat(priceRupees);
    if (!priceRupees.trim()) {
      newErrors.price = 'Price is required';
    } else if (isNaN(price) || price < 0) {
      newErrors.price = 'Price must be a valid positive number';
    }

    if (!categoryInput.trim()) {
      newErrors.category = 'Category is required';
    } else if (categoryInput.length > 50) {
      newErrors.category = 'Category must be 50 characters or less';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Handle form submission.
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (!validate()) {
      return;
    }

    setSubmitting(true);
    try {
      const pricePaise = rupeesToPaise(parseFloat(priceRupees));
      const formData: CreateMenuItemData | UpdateMenuItemData = {
        name: name.trim(),
        description: description.trim(),
        price: pricePaise,
        category: categoryInput.trim(),
        tags: selectedTags,
        prep_type: prepType,
        is_available: isAvailable,
      };

      await onSubmit(formData);
      onClose();
    } catch (err) {
      setErrors({
        submit: err instanceof Error ? err.message : 'Failed to save menu item',
      });
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * Toggle tag selection.
   */
  const toggleTag = (tag: IngredientTag) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  /**
   * Add custom ingredient from text input.
   */
  const addCustomIngredient = () => {
    const trimmed = ingredientInput.trim().toLowerCase();
    if (trimmed && !customIngredients.includes(trimmed)) {
      setCustomIngredients((prev) => [...prev, trimmed]);
      setIngredientInput('');
    }
  };

  /**
   * Remove custom ingredient.
   */
  const removeCustomIngredient = (ingredient: string) => {
    setCustomIngredients((prev) => prev.filter((i) => i !== ingredient));
  };

  /**
   * Handle ingredient input key press.
   */
  const handleIngredientKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addCustomIngredient();
    }
  };

  /**
   * Handle category input change.
   */
  const handleCategoryChange = (value: string) => {
    setCategoryInput(value);
    setCategory(value);
    setShowCategorySuggestions(true);
  };

  /**
   * Select category from suggestions.
   */
  const selectCategory = (cat: string) => {
    setCategoryInput(cat);
    setCategory(cat);
    setShowCategorySuggestions(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content menu-item-form-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isEditing ? 'Edit Menu Item' : 'Add Menu Item'}</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
            disabled={submitting}
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {errors.submit && (
            <div className="form-error">
              <p>{errors.submit}</p>
            </div>
          )}

          {/* Name */}
          <div className="form-group">
            <label htmlFor="menu-item-name">
              Name <span className="form-required">*</span>
            </label>
            <input
              id="menu-item-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Classic Turkey Club"
              required
              disabled={submitting}
              maxLength={100}
              className={errors.name ? 'form-input-error' : ''}
            />
            {errors.name && <span className="form-field-error">{errors.name}</span>}
          </div>

          {/* Description */}
          <div className="form-group">
            <label htmlFor="menu-item-description">
              Description <span className="form-required">*</span>
            </label>
            <textarea
              id="menu-item-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the menu item..."
              required
              disabled={submitting}
              maxLength={500}
              rows={3}
              className={errors.description ? 'form-input-error' : ''}
            />
            <div className="form-helper-text">
              {description.length}/500 characters
            </div>
            {errors.description && (
              <span className="form-field-error">{errors.description}</span>
            )}
          </div>

          {/* Price */}
          <div className="form-group">
            <label htmlFor="menu-item-price">
              Price (₹) <span className="form-required">*</span>
            </label>
            <input
              id="menu-item-price"
              type="number"
              step="0.01"
              min="0"
              value={priceRupees}
              onChange={(e) => setPriceRupees(e.target.value)}
              placeholder="125.00"
              required
              disabled={submitting}
              className={errors.price ? 'form-input-error' : ''}
            />
            {errors.price && <span className="form-field-error">{errors.price}</span>}
          </div>

          {/* Category */}
          <div className="form-group">
            <label htmlFor="menu-item-category">
              Category <span className="form-required">*</span>
            </label>
            <div className="form-category-wrapper">
              <div className="form-category-input-group">
                <select
                  id="menu-item-category-select"
                  value={category}
                  onChange={(e) => {
                    const selected = e.target.value;
                    if (selected) {
                      setCategory(selected);
                      setCategoryInput(selected);
                      setShowCategorySuggestions(false);
                    }
                  }}
                  onBlur={() => {
                    // Clear any existing timeout
                    if (categoryDropdownTimeoutRef.current) {
                      clearTimeout(categoryDropdownTimeoutRef.current);
                    }
                    // Set new timeout to hide suggestions after blur
                    categoryDropdownTimeoutRef.current = setTimeout(() => {
                      setShowCategorySuggestions(false);
                    }, 200);
                  }}
                  disabled={submitting}
                  className="form-category-select"
                >
                  <option value="">Select or type new...</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
                <input
                  id="menu-item-category"
                  type="text"
                  value={categoryInput}
                  onChange={(e) => handleCategoryChange(e.target.value)}
                  onFocus={() => setShowCategorySuggestions(true)}
                  placeholder="Or type a new category..."
                  required
                  disabled={submitting}
                  maxLength={50}
                  className={errors.category ? 'form-input-error' : ''}
                />
              </div>
              {showCategorySuggestions && filteredCategories.length > 0 && (
                <div className="form-category-suggestions">
                  {filteredCategories.map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      className="form-category-suggestion"
                      onClick={() => selectCategory(cat)}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {errors.category && (
              <span className="form-field-error">{errors.category}</span>
            )}
          </div>

          {/* Ingredient Tags */}
          <div className="form-group">
            <label>Ingredient Tags</label>
            
            {/* Custom ingredient input */}
            <div className="form-ingredient-input-group">
              <input
                type="text"
                value={ingredientInput}
                onChange={(e) => setIngredientInput(e.target.value)}
                onKeyPress={handleIngredientKeyPress}
                placeholder="Type custom ingredient and press Enter..."
                disabled={submitting}
                className="form-ingredient-text-input"
              />
              <button
                type="button"
                className="btn btn-secondary form-add-ingredient-btn"
                onClick={addCustomIngredient}
                disabled={submitting || !ingredientInput.trim()}
              >
                Add
              </button>
            </div>

            {/* Custom ingredients display */}
            {customIngredients.length > 0 && (
              <div className="form-custom-ingredients">
                {customIngredients.map((ingredient) => (
                  <span key={ingredient} className="form-custom-ingredient-tag">
                    {ingredient}
                    <button
                      type="button"
                      className="form-custom-ingredient-remove"
                      onClick={() => removeCustomIngredient(ingredient)}
                      disabled={submitting}
                      aria-label={`Remove ${ingredient}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* Enum tags */}
            <div className="form-tags-container">
              {allTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  className={`form-tag ${selectedTags.includes(tag) ? 'form-tag-selected' : ''}`}
                  onClick={() => toggleTag(tag)}
                  disabled={submitting}
                >
                  {tag}
                </button>
              ))}
            </div>
            
            {/* Selected tags summary */}
            {(selectedTags.length > 0 || customIngredients.length > 0) && (
              <div className="form-helper-text">
                Selected: {[...selectedTags, ...customIngredients].join(', ')}
              </div>
            )}
          </div>

          {/* Prep Type */}
          <div className="form-group">
            <label htmlFor="menu-item-prep-type">
              Preparation Type <span className="form-required">*</span>
            </label>
            <select
              id="menu-item-prep-type"
              value={prepType}
              onChange={(e) => setPrepType(e.target.value as PrepType)}
              required
              disabled={submitting}
            >
              {Object.values(PrepType).map((type) => (
                <option key={type} value={type}>
                  {PREP_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>

          {/* Availability */}
          <div className="form-group form-group-checkbox">
            <label className="form-checkbox-label">
              <input
                type="checkbox"
                checked={isAvailable}
                onChange={(e) => setIsAvailable(e.target.checked)}
                disabled={submitting}
              />
              <span>Available for ordering</span>
            </label>
          </div>

          {/* Form actions */}
          <div className="modal-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting}
            >
              {submitting ? 'Saving...' : isEditing ? 'Update Item' : 'Create Item'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
