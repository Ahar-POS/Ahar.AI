/**
 * TableCard component.
 * 
 * Displays a single table with status, capacity, and quick action buttons.
 */

import React from 'react';
import { Table, TableStatus, TABLE_STATUS_LABELS, TABLE_STATUS_COLORS } from '../types/tables';
import './TableCard.css';

interface TableCardProps {
  table: Table;
  onStatusChange: (tableId: string, newStatus: TableStatus) => void;
}

/**
 * Table card component showing table details and status controls.
 */
export default function TableCard({ table, onStatusChange }: TableCardProps) {
  const handleStatusClick = (newStatus: TableStatus) => {
    if (newStatus !== table.status) {
      onStatusChange(table.id, newStatus);
    }
  };

  return (
    <div className="table-card">
      {/* Header with table info and status badge */}
      <div className="table-card-header">
        <div className="table-card-title">
          <h3 className="table-card-name">
            Table {table.table_number} — {table.location}
          </h3>
          <span
            className="table-card-status-badge"
            style={{ backgroundColor: TABLE_STATUS_COLORS[table.status] }}
          >
            {TABLE_STATUS_LABELS[table.status]}
          </span>
        </div>
      </div>

      {/* Capacity indicator */}
      <div className="table-card-capacity">
        <svg
          className="table-card-capacity-icon"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
          />
        </svg>
        <span>Capacity: {table.capacity}</span>
      </div>

      {/* Status action buttons */}
      <div className="table-card-actions">
        <button
          type="button"
          className={`table-card-action-btn ${
            table.status === TableStatus.AVAILABLE ? 'active' : ''
          }`}
          onClick={() => handleStatusClick(TableStatus.AVAILABLE)}
          aria-label="Mark as available"
        >
          Available
        </button>
        <button
          type="button"
          className={`table-card-action-btn ${
            table.status === TableStatus.OCCUPIED ? 'active' : ''
          }`}
          onClick={() => handleStatusClick(TableStatus.OCCUPIED)}
          aria-label="Mark as occupied"
        >
          Occupied
        </button>
        <button
          type="button"
          className={`table-card-action-btn ${
            table.status === TableStatus.RESERVED ? 'active' : ''
          }`}
          onClick={() => handleStatusClick(TableStatus.RESERVED)}
          aria-label="Mark as reserved"
        >
          Reserved
        </button>
        <button
          type="button"
          className={`table-card-action-btn ${
            table.status === TableStatus.CLOSED ? 'active' : ''
          }`}
          onClick={() => handleStatusClick(TableStatus.CLOSED)}
          aria-label="Mark as closed"
        >
          Closed
        </button>
      </div>
    </div>
  );
}
