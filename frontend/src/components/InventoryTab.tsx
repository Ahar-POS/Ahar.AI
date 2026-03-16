import React, { useState, useEffect } from 'react';
import { inventoryService } from '../services/inventory';
import type { InventoryItem, InventoryItemCreate, InventoryItemUpdate, InventoryFilters } from '../types/inventory';
import ConfirmModal from './ConfirmModal';
import './InventoryTab.css';

const EMPTY_CREATE_FORM: InventoryItemCreate = {
  material_id: '',
  material_name: '',
  category: '',
  unit: '',
  unit_cost_inr: 0,
  reorder_level: 0,
  reorder_qty: 0,
  current_stock: 0,
  max_stock: 0,
  lead_time_days: 1,
  supplier_id: '',
  last_restock_date: null,
  shelf_life_days: 0,
  storage_temp_c: '',
  is_perishable: 'No',
};

export const InventoryTab: React.FC = () => {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [perishableFilter, setPerishableFilter] = useState<string>('');
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [editForm, setEditForm] = useState<InventoryItemUpdate>({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [showLowStock, setShowLowStock] = useState(false);
  const [deletingItem, setDeletingItem] = useState<InventoryItem | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState<InventoryItemCreate>({ ...EMPTY_CREATE_FORM });
  const [savingAdd, setSavingAdd] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const limit = 20;

  useEffect(() => {
    loadItems();
  }, [page, categoryFilter, perishableFilter]);

  const loadItems = async () => {
    try {
      setLoading(true);
      setError(null);
      setShowLowStock(false);

      const filters: InventoryFilters = {};
      if (categoryFilter) filters.category = categoryFilter;
      if (perishableFilter) filters.is_perishable = perishableFilter;

      const response = await inventoryService.getAllItems(page, limit, filters);
      setItems(Array.isArray(response?.data) ? response.data : []);
      setTotalPages(response?.pagination?.total_pages ?? 1);
      setTotalItems(response?.pagination?.total ?? 0);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: { message?: string } } } };
      setError(e.response?.data?.error?.message || 'Failed to load inventory');
    } finally {
      setLoading(false);
    }
  };

  const loadLowStockItems = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await inventoryService.getLowStockItems();
      setItems(Array.isArray(response?.data) ? response.data : []);
      setShowLowStock(true);
      setTotalPages(1);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: { message?: string } } } };
      setError(e.response?.data?.error?.message || 'Failed to load low stock items');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (item: InventoryItem) => {
    setEditingItem(item);
    setEditForm({
      material_name: item.material_name,
      category: item.category,
      unit: item.unit,
      unit_cost_inr: item.unit_cost_inr,
      reorder_level: item.reorder_level,
      reorder_qty: item.reorder_qty,
      current_stock: item.current_stock,
      max_stock: item.max_stock,
      lead_time_days: item.lead_time_days,
      supplier_id: item.supplier_id,
      last_restock_date: item.last_restock_date,
      shelf_life_days: item.shelf_life_days,
      storage_temp_c: item.storage_temp_c,
      is_perishable: item.is_perishable,
    });
  };

  const handleCloseEdit = () => {
    setEditingItem(null);
    setEditForm({});
    setSavingEdit(false);
  };

  const handleOpenAdd = () => {
    setAddForm({ ...EMPTY_CREATE_FORM });
    setAddError(null);
    setShowAddModal(true);
  };

  const handleCloseAdd = () => {
    setShowAddModal(false);
    setAddForm({ ...EMPTY_CREATE_FORM });
    setAddError(null);
    setSavingAdd(false);
  };

  const handleAddSave = async () => {
    if (!addForm.material_id.trim() || !addForm.material_name.trim()) {
      setAddError('Material ID and Name are required.');
      return;
    }
    try {
      setSavingAdd(true);
      setAddError(null);
      await inventoryService.createItem(addForm);
      handleCloseAdd();
      loadItems();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: { message?: string } } } };
      setAddError(e.response?.data?.error?.message || 'Failed to create inventory item');
      setSavingAdd(false);
    }
  };

  const handleSave = async () => {
    if (!editingItem) return;
    try {
      setSavingEdit(true);
      await inventoryService.updateItem(editingItem._id, editForm);
      handleCloseEdit();
      loadItems();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: { message?: string } } } };
      setError(e.response?.data?.error?.message || 'Failed to update item');
      setSavingEdit(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingItem) return;
    try {
      await inventoryService.deleteItem(deletingItem._id);
      setDeletingItem(null);
      loadItems();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: { message?: string } } } };
      setError(e.response?.data?.error?.message || 'Failed to delete item');
      setDeletingItem(null);
    }
  };

  const getStockStatus = (item: InventoryItem): { text: string; cls: string } => {
    if (item.current_stock <= item.reorder_level) return { text: 'Low Stock', cls: 'low' };
    if (item.current_stock >= item.max_stock) return { text: 'Full', cls: 'full' };
    return { text: 'Normal', cls: 'normal' };
  };

  const itemsSafe = items ?? [];
  const lowStockCount = itemsSafe.filter((i) => i.current_stock <= i.reorder_level).length;
  const categories = [...new Set(itemsSafe.map((item) => item.category))].sort();
  const hasActiveFilters = !!(categoryFilter || perishableFilter || showLowStock);

  if (loading && itemsSafe.length === 0) {
    return (
      <div className="inventory-loading">
        <div className="spinner spinner-lg" role="status" aria-label="Loading" />
        <span>Loading inventory…</span>
      </div>
    );
  }

  return (
    <div className="inventory-tab-wrapper">
      {/* ── Header ───────────────────────────────────────────── */}
      <div className="inventory-header">
        <div className="inventory-header-left">
          <h2 className="inventory-title">Raw Material Inventory</h2>
          <p className="inventory-subtitle">
            {showLowStock ? 'Showing items below reorder level' : `${totalItems} items across all categories`}
          </p>
        </div>
        <div className="inventory-header-actions">
          <button
            className="btn btn-primary btn-sm"
            onClick={handleOpenAdd}
            disabled={loading}
            aria-label="Add new inventory item"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add Item
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setShowLowStock(false);
              loadItems();
            }}
            disabled={loading}
            aria-label="Refresh inventory"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M23 4v6h-6M1 20v-6h6" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* ── Stats Row ─────────────────────────────────────────── */}
      <div className="inventory-stats">
        <div className="inventory-stat-card primary">
          <span className="inventory-stat-label">Total Items</span>
          <span className="inventory-stat-value">{totalItems || itemsSafe.length}</span>
        </div>
        <div className={`inventory-stat-card ${lowStockCount > 0 ? 'warning' : 'success'}`}>
          <span className="inventory-stat-label">Low Stock</span>
          <span className="inventory-stat-value">{lowStockCount}</span>
        </div>
        <div className="inventory-stat-card">
          <span className="inventory-stat-label">Categories</span>
          <span className="inventory-stat-value">{categories.length}</span>
        </div>
        <div className="inventory-stat-card">
          <span className="inventory-stat-label">Current Page</span>
          <span className="inventory-stat-value">{page}/{totalPages || 1}</span>
        </div>
      </div>

      {/* ── Error Alert ──────────────────────────────────────── */}
      {error && (
        <div className="inventory-alert error" role="alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {error}
        </div>
      )}

      {/* ── Low Stock Banner ─────────────────────────────────── */}
      {showLowStock && (
        <div className="inventory-lowstock-banner">
          <span className="inventory-lowstock-banner-text">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            Showing {itemsSafe.length} item{itemsSafe.length !== 1 ? 's' : ''} below reorder level
          </span>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => { setShowLowStock(false); loadItems(); }}
          >
            View All
          </button>
        </div>
      )}

      {/* ── Filters ──────────────────────────────────────────── */}
      <div className="inventory-filters">
        <span className="inventory-filter-label">Filter:</span>

        <button
          className={`btn btn-sm ${showLowStock ? 'btn-primary' : 'btn-outline'}`}
          onClick={loadLowStockItems}
          disabled={loading}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          </svg>
          Low Stock
        </button>

        <div className="inventory-filter-divider" />

        <select
          value={categoryFilter}
          onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
          className="inventory-filter-select"
          aria-label="Filter by category"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>

        <select
          value={perishableFilter}
          onChange={(e) => { setPerishableFilter(e.target.value); setPage(1); }}
          className="inventory-filter-select"
          aria-label="Filter by perishability"
        >
          <option value="">All Items</option>
          <option value="Yes">Perishable</option>
          <option value="No">Non-Perishable</option>
        </select>

        {hasActiveFilters && (
          <>
            <div className="inventory-filter-divider" />
            <span className="inventory-filters-active-tag">
              Filtered
              <button
                onClick={() => { setCategoryFilter(''); setPerishableFilter(''); setShowLowStock(false); setPage(1); loadItems(); }}
                aria-label="Clear all filters"
              >
                ×
              </button>
            </span>
          </>
        )}
      </div>

      {/* ── Table ────────────────────────────────────────────── */}
      <div className="inventory-table-wrapper">
        {loading && (
          <div style={{ padding: 'var(--spacing-md)', textAlign: 'center', borderBottom: '1px solid var(--color-border)' }}>
            <div className="spinner" style={{ margin: '0 auto' }} aria-label="Refreshing" />
          </div>
        )}

        <div className="inventory-table-scroll">
          <table className="inventory-table">
            <thead>
              <tr>
                <th scope="col">Material ID</th>
                <th scope="col">Name</th>
                <th scope="col">Category</th>
                <th scope="col">Stock</th>
                <th scope="col">Unit</th>
                <th scope="col">Reorder Level</th>
                <th scope="col">Status</th>
                <th scope="col">Unit Cost</th>
                <th scope="col">Perishable</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {itemsSafe.length === 0 && !loading ? (
                <tr>
                  <td colSpan={10}>
                    <div className="inventory-empty">
                      <div className="inventory-empty-icon">📦</div>
                      <p className="inventory-empty-title">No items found</p>
                      <p className="inventory-empty-text">
                        {hasActiveFilters ? 'Try adjusting your filters.' : 'No inventory items are available yet.'}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                itemsSafe.map((item) => {
                  const status = getStockStatus(item);
                  return (
                    <tr key={item._id}>
                      <td>
                        <span className="inventory-table-id">{item.material_id}</span>
                      </td>
                      <td>
                        <span className="inventory-table-name">{item.material_name}</span>
                      </td>
                      <td>
                        <span className="inventory-table-meta">{item.category}</span>
                      </td>
                      <td>
                        <span className="inventory-table-stock">{item.current_stock}</span>
                      </td>
                      <td>
                        <span className="inventory-table-meta">{item.unit}</span>
                      </td>
                      <td>
                        <span className="inventory-table-meta">{item.reorder_level}</span>
                      </td>
                      <td>
                        <span className={`stock-badge ${status.cls}`}>{status.text}</span>
                      </td>
                      <td>
                        <span className="inventory-table-cost">₹{(item.unit_cost_inr / 100).toFixed(2)}</span>
                      </td>
                      <td>
                        <span className={`perishable-badge ${item.is_perishable === 'Yes' ? 'yes' : 'no'}`}>
                          {item.is_perishable === 'Yes' ? '🌿 Yes' : 'No'}
                        </span>
                      </td>
                      <td>
                        <div className="inventory-table-actions">
                          <button
                            className="inventory-action-btn edit"
                            onClick={() => handleEdit(item)}
                            aria-label={`Edit ${item.material_name}`}
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                            </svg>
                            Edit
                          </button>
                          <button
                            className="inventory-action-btn delete"
                            onClick={() => setDeletingItem(item)}
                            aria-label={`Delete ${item.material_name}`}
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                              <path d="M10 11v6M14 11v6" />
                            </svg>
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Pagination ───────────────────────────────────────── */}
      {!showLowStock && totalPages > 1 && (
        <div className="inventory-pagination">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
          >
            ← Previous
          </button>
          <span className="inventory-page-info">Page {page} of {totalPages}</span>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || loading}
          >
            Next →
          </button>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════
          EDIT MODAL
          ════════════════════════════════════════════════════ */}
      {editingItem && (
        <div
          className="inventory-modal-overlay"
          onClick={handleCloseEdit}
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-modal-title"
        >
          <div className="inventory-modal" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="inventory-modal-header">
              <div className="inventory-modal-header-left">
                <h3 id="edit-modal-title" className="inventory-modal-title">Edit Inventory Item</h3>
                <p className="inventory-modal-subtitle">{editingItem.material_name}</p>
              </div>
              <button
                className="inventory-modal-close"
                onClick={handleCloseEdit}
                aria-label="Close modal"
              >
                ×
              </button>
            </div>

            {/* Body */}
            <div className="inventory-modal-body">
              {/* Identification */}
              <div className="inventory-modal-section">
                <p className="inventory-modal-section-title">Identification</p>
                <div className="inventory-modal-grid">
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-material-id">Material ID</label>
                    <input
                      id="edit-material-id"
                      type="text"
                      value={editingItem.material_id}
                      disabled
                      className="inventory-form-input is-id"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-material-name">Material Name</label>
                    <input
                      id="edit-material-name"
                      type="text"
                      value={editForm.material_name ?? ''}
                      onChange={(e) => setEditForm({ ...editForm, material_name: e.target.value })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-category">Category</label>
                    <input
                      id="edit-category"
                      type="text"
                      value={editForm.category ?? ''}
                      onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-unit">Unit</label>
                    <input
                      id="edit-unit"
                      type="text"
                      value={editForm.unit ?? ''}
                      onChange={(e) => setEditForm({ ...editForm, unit: e.target.value })}
                      className="inventory-form-input"
                    />
                  </div>
                </div>
              </div>

              {/* Stock Levels */}
              <div className="inventory-modal-section">
                <p className="inventory-modal-section-title">Stock Levels</p>
                <div className="inventory-modal-grid">
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-current-stock">Current Stock</label>
                    <input
                      id="edit-current-stock"
                      type="number"
                      value={editForm.current_stock ?? 0}
                      onChange={(e) => setEditForm({ ...editForm, current_stock: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-max-stock">Max Stock</label>
                    <input
                      id="edit-max-stock"
                      type="number"
                      value={editForm.max_stock ?? 0}
                      onChange={(e) => setEditForm({ ...editForm, max_stock: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-reorder-level">Reorder Level</label>
                    <input
                      id="edit-reorder-level"
                      type="number"
                      value={editForm.reorder_level ?? 0}
                      onChange={(e) => setEditForm({ ...editForm, reorder_level: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-reorder-qty">Reorder Quantity</label>
                    <input
                      id="edit-reorder-qty"
                      type="number"
                      value={editForm.reorder_qty ?? 0}
                      onChange={(e) => setEditForm({ ...editForm, reorder_qty: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                </div>
              </div>

              {/* Pricing & Supplier */}
              <div className="inventory-modal-section">
                <p className="inventory-modal-section-title">Pricing & Supplier</p>
                <div className="inventory-modal-grid">
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-unit-cost">Unit Cost (₹)</label>
                    <input
                      id="edit-unit-cost"
                      type="number"
                      step="0.01"
                      value={((editForm.unit_cost_inr ?? 0) / 100).toFixed(2)}
                      onChange={(e) => setEditForm({ ...editForm, unit_cost_inr: Math.round(parseFloat(e.target.value) * 100) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-supplier-id">Supplier ID</label>
                    <input
                      id="edit-supplier-id"
                      type="text"
                      value={editForm.supplier_id ?? ''}
                      onChange={(e) => setEditForm({ ...editForm, supplier_id: e.target.value })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-lead-time">Lead Time (Days)</label>
                    <input
                      id="edit-lead-time"
                      type="number"
                      value={editForm.lead_time_days ?? 0}
                      onChange={(e) => setEditForm({ ...editForm, lead_time_days: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-last-restock">Last Restock Date</label>
                    <input
                      id="edit-last-restock"
                      type="text"
                      value={editForm.last_restock_date ?? ''}
                      onChange={(e) => setEditForm({ ...editForm, last_restock_date: e.target.value })}
                      placeholder="YYYY-MM-DD"
                      className="inventory-form-input"
                    />
                  </div>
                </div>
              </div>

              {/* Storage & Perishability */}
              <div className="inventory-modal-section">
                <p className="inventory-modal-section-title">Storage & Perishability</p>
                <div className="inventory-modal-grid">
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-shelf-life">Shelf Life (Days)</label>
                    <input
                      id="edit-shelf-life"
                      type="number"
                      value={editForm.shelf_life_days ?? 0}
                      onChange={(e) => setEditForm({ ...editForm, shelf_life_days: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-storage-temp">Storage Temp (°C)</label>
                    <input
                      id="edit-storage-temp"
                      type="text"
                      value={editForm.storage_temp_c ?? ''}
                      onChange={(e) => setEditForm({ ...editForm, storage_temp_c: e.target.value })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="edit-perishable">Perishable</label>
                    <select
                      id="edit-perishable"
                      value={editForm.is_perishable ?? 'No'}
                      onChange={(e) => setEditForm({ ...editForm, is_perishable: e.target.value })}
                      className="inventory-form-input"
                    >
                      <option value="Yes">Yes</option>
                      <option value="No">No</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="inventory-modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleCloseEdit}
                disabled={savingEdit}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSave}
                disabled={savingEdit}
              >
                {savingEdit ? (
                  <>
                    <span className="spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }} />
                    Saving…
                  </>
                ) : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════
          ADD ITEM MODAL
          ════════════════════════════════════════════════════ */}
      {showAddModal && (
        <div
          className="inventory-modal-overlay"
          onClick={handleCloseAdd}
          role="dialog"
          aria-modal="true"
          aria-labelledby="add-modal-title"
        >
          <div className="inventory-modal" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="inventory-modal-header">
              <div className="inventory-modal-header-left">
                <h3 id="add-modal-title" className="inventory-modal-title">Add Inventory Item</h3>
                <p className="inventory-modal-subtitle">Fill in the details for the new raw material</p>
              </div>
              <button
                className="inventory-modal-close"
                onClick={handleCloseAdd}
                aria-label="Close modal"
              >
                ×
              </button>
            </div>

            {/* Body */}
            <div className="inventory-modal-body">
              {addError && (
                <div className="inventory-alert error" role="alert" style={{ marginBottom: 'var(--spacing-md)' }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  {addError}
                </div>
              )}

              {/* Identification */}
              <div className="inventory-modal-section">
                <p className="inventory-modal-section-title">Identification</p>
                <div className="inventory-modal-grid">
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-material-id">
                      Material ID <span style={{ color: 'var(--color-error)' }}>*</span>
                    </label>
                    <input
                      id="add-material-id"
                      type="text"
                      value={addForm.material_id}
                      onChange={(e) => setAddForm({ ...addForm, material_id: e.target.value })}
                      placeholder="e.g. RM051"
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-material-name">
                      Material Name <span style={{ color: 'var(--color-error)' }}>*</span>
                    </label>
                    <input
                      id="add-material-name"
                      type="text"
                      value={addForm.material_name}
                      onChange={(e) => setAddForm({ ...addForm, material_name: e.target.value })}
                      placeholder="e.g. Basmati Rice"
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-category">Category</label>
                    <input
                      id="add-category"
                      type="text"
                      value={addForm.category}
                      onChange={(e) => setAddForm({ ...addForm, category: e.target.value })}
                      placeholder="e.g. Grains"
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-unit">Unit</label>
                    <input
                      id="add-unit"
                      type="text"
                      value={addForm.unit}
                      onChange={(e) => setAddForm({ ...addForm, unit: e.target.value })}
                      placeholder="e.g. kg"
                      className="inventory-form-input"
                    />
                  </div>
                </div>
              </div>

              {/* Stock Levels */}
              <div className="inventory-modal-section">
                <p className="inventory-modal-section-title">Stock Levels</p>
                <div className="inventory-modal-grid">
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-current-stock">Current Stock</label>
                    <input
                      id="add-current-stock"
                      type="number"
                      min="0"
                      value={addForm.current_stock}
                      onChange={(e) => setAddForm({ ...addForm, current_stock: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-max-stock">Max Stock</label>
                    <input
                      id="add-max-stock"
                      type="number"
                      min="0"
                      value={addForm.max_stock}
                      onChange={(e) => setAddForm({ ...addForm, max_stock: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-reorder-level">Reorder Level</label>
                    <input
                      id="add-reorder-level"
                      type="number"
                      min="0"
                      value={addForm.reorder_level}
                      onChange={(e) => setAddForm({ ...addForm, reorder_level: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-reorder-qty">Reorder Quantity</label>
                    <input
                      id="add-reorder-qty"
                      type="number"
                      min="0"
                      value={addForm.reorder_qty}
                      onChange={(e) => setAddForm({ ...addForm, reorder_qty: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                </div>
              </div>

              {/* Pricing & Supplier */}
              <div className="inventory-modal-section">
                <p className="inventory-modal-section-title">Pricing & Supplier</p>
                <div className="inventory-modal-grid">
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-unit-cost">Unit Cost (₹)</label>
                    <input
                      id="add-unit-cost"
                      type="number"
                      min="0"
                      step="0.01"
                      value={(addForm.unit_cost_inr / 100).toFixed(2)}
                      onChange={(e) => setAddForm({ ...addForm, unit_cost_inr: Math.round(parseFloat(e.target.value) * 100) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-supplier-id">Supplier ID</label>
                    <input
                      id="add-supplier-id"
                      type="text"
                      value={addForm.supplier_id}
                      onChange={(e) => setAddForm({ ...addForm, supplier_id: e.target.value })}
                      placeholder="e.g. SUP001"
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-lead-time">Lead Time (Days)</label>
                    <input
                      id="add-lead-time"
                      type="number"
                      min="0"
                      value={addForm.lead_time_days}
                      onChange={(e) => setAddForm({ ...addForm, lead_time_days: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-last-restock">Last Restock Date</label>
                    <input
                      id="add-last-restock"
                      type="text"
                      value={addForm.last_restock_date ?? ''}
                      onChange={(e) => setAddForm({ ...addForm, last_restock_date: e.target.value || null })}
                      placeholder="YYYY-MM-DD"
                      className="inventory-form-input"
                    />
                  </div>
                </div>
              </div>

              {/* Storage & Perishability */}
              <div className="inventory-modal-section">
                <p className="inventory-modal-section-title">Storage & Perishability</p>
                <div className="inventory-modal-grid">
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-shelf-life">Shelf Life (Days)</label>
                    <input
                      id="add-shelf-life"
                      type="number"
                      min="0"
                      value={addForm.shelf_life_days}
                      onChange={(e) => setAddForm({ ...addForm, shelf_life_days: parseInt(e.target.value) || 0 })}
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-storage-temp">Storage Temp (°C)</label>
                    <input
                      id="add-storage-temp"
                      type="text"
                      value={addForm.storage_temp_c}
                      onChange={(e) => setAddForm({ ...addForm, storage_temp_c: e.target.value })}
                      placeholder="e.g. 2-8°C or Room Temp"
                      className="inventory-form-input"
                    />
                  </div>
                  <div className="inventory-form-group">
                    <label className="inventory-form-label" htmlFor="add-perishable">Perishable</label>
                    <select
                      id="add-perishable"
                      value={addForm.is_perishable}
                      onChange={(e) => setAddForm({ ...addForm, is_perishable: e.target.value })}
                      className="inventory-form-input"
                    >
                      <option value="Yes">Yes</option>
                      <option value="No">No</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="inventory-modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleCloseAdd}
                disabled={savingAdd}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleAddSave}
                disabled={savingAdd}
              >
                {savingAdd ? (
                  <>
                    <span className="spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }} />
                    Saving…
                  </>
                ) : 'Add Item'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════
          DELETE CONFIRMATION MODAL
          ════════════════════════════════════════════════════ */}
      {deletingItem && (
        <ConfirmModal
          title="Delete Inventory Item"
          message={`Are you sure you want to delete "${deletingItem.material_name}" (${deletingItem.material_id})? This action cannot be undone.`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeletingItem(null)}
          variant="danger"
        />
      )}
    </div>
  );
};
