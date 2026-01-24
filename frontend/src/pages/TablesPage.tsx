/**
 * TablesPage component.
 * 
 * Main page for managing restaurant tables.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Table, TableStatus, TableStats, CreateTableData } from '../types/tables';
import {
  getTables,
  updateTableStatus,
  calculateTableStats,
  createTable,
} from '../services/tables';
import TableCard from '../components/TableCard';
import './TablesPage.css';

/**
 * Tables management page component.
 */
export default function TablesPage() {
  const [tables, setTables] = useState<Table[]>([]);
  const [stats, setStats] = useState<TableStats>({
    total: 0,
    available: 0,
    occupied: 0,
    reserved: 0,
    closed: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  /**
   * Handle Add Table button click.
   */
  const handleAddTableClick = () => {
    setShowAddModal(true);
  };

  /**
   * Handle form submission for creating a new table.
   */
  const handleCreateTable = async (formData: {
    table_number: number;
    location: string;
    capacity: number;
  }) => {
    try {
      const newTableData: CreateTableData = {
        ...formData,
        status: TableStatus.AVAILABLE,
      };
      
      const createdTable = await createTable(newTableData);
      
      // Refresh tables list
      await loadTables();
      setShowAddModal(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create table');
    }
  };

  /**
   * Load tables from API.
   */
  const loadTables = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getTables();
      setTables(data);
      setStats(calculateTableStats(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tables');
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Handle table status change.
   */
  const handleStatusChange = async (tableId: string, newStatus: TableStatus) => {
    try {
      const updatedTable = await updateTableStatus(tableId, newStatus);
      
      // Update local state and recalculate stats with updated data
      setTables((prev) => {
        const updated = prev.map((t) => (t.id === tableId ? updatedTable : t));
        setStats(calculateTableStats(updated));
        return updated;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update table status');
    }
  };

  /**
   * Load tables on component mount.
   */
  useEffect(() => {
    loadTables();
  }, [loadTables]);

  return (
    <div className="tables-page">
      {/* Header with stats */}
      <div className="tables-page-header">
        <div>
          <h1 className="tables-page-title">Tables Management</h1>
          <p className="tables-page-subtitle">{stats.total} tables total</p>
        </div>
        
        {/* Stats summary */}
        <div className="tables-page-stats">
          <div className="table-stat available">
            <span className="table-stat-label">Available</span>
            <span className="table-stat-value">{stats.available}</span>
          </div>
          <div className="table-stat occupied">
            <span className="table-stat-label">Occupied</span>
            <span className="table-stat-value">{stats.occupied}</span>
          </div>
          <div className="table-stat reserved">
            <span className="table-stat-label">Reserved</span>
            <span className="table-stat-value">{stats.reserved}</span>
          </div>
        </div>
        
        {/* Add Table button */}
        <button
          type="button"
          className="btn btn-primary tables-page-add-btn"
          onClick={handleAddTableClick}
        >
          + Add Table
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="tables-page-error">
          <p>{error}</p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadTables}
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="tables-page-loading">
          <div className="spinner" />
          <p>Loading tables...</p>
        </div>
      )}

      {/* Tables grid */}
      {!loading && !error && tables.length === 0 && (
        <div className="tables-page-empty">
          <p>No tables found</p>
          <button 
            type="button" 
            className="btn btn-primary"
            onClick={handleAddTableClick}
          >
            Add Table
          </button>
        </div>
      )}

      {!loading && !error && tables.length > 0 && (
        <div className="tables-page-grid">
          {tables.map((table) => (
            <TableCard
              key={table.id}
              table={table}
              onStatusChange={handleStatusChange}
            />
          ))}
        </div>
      )}

      {/* Add Table Modal */}
      {showAddModal && (
        <AddTableModal
          onClose={() => setShowAddModal(false)}
          onSubmit={handleCreateTable}
        />
      )}
    </div>
  );
}

/**
 * Add Table Modal Component.
 */
interface AddTableModalProps {
  onClose: () => void;
  onSubmit: (data: { table_number: number; location: string; capacity: number }) => void;
}

function AddTableModal({ onClose, onSubmit }: AddTableModalProps) {
  const [tableNumber, setTableNumber] = useState('');
  const [location, setLocation] = useState('');
  const [capacity, setCapacity] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const num = parseInt(tableNumber, 10);
    const cap = parseInt(capacity, 10);

    if (!num || num < 1) {
      setValidationError('Table number must be a positive integer');
      return;
    }

    if (!location.trim()) {
      setValidationError('Location is required');
      return;
    }

    if (!cap || cap < 1 || cap > 20) {
      setValidationError('Capacity must be between 1 and 20');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit({
        table_number: num,
        location: location.trim(),
        capacity: cap,
      });
      // Reset form on success
      setTableNumber('');
      setLocation('');
      setCapacity('');
    } catch (err) {
      // Error handling is done in parent component
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New Table</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit} className="modal-form">
          {validationError && (
            <div className="form-error">
              <p>{validationError}</p>
            </div>
          )}
          <div className="form-group">
            <label htmlFor="table-number">Table Number *</label>
            <input
              id="table-number"
              type="number"
              min="1"
              value={tableNumber}
              onChange={(e) => setTableNumber(e.target.value)}
              required
              disabled={submitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="location">Location *</label>
            <input
              id="location"
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., Window Seat, Patio A"
              required
              disabled={submitting}
              maxLength={100}
            />
          </div>
          <div className="form-group">
            <label htmlFor="capacity">Capacity *</label>
            <input
              id="capacity"
              type="number"
              min="1"
              max="20"
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
              required
              disabled={submitting}
            />
          </div>
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
              {submitting ? 'Creating...' : 'Create Table'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
