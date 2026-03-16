/**
 * PurchaseOrdersTab - Display and manage purchase orders.
 */
import React, { useState, useEffect } from 'react';
import './TabsCommon.css';
import { PurchaseOrder, POStatus, PurchaseOrderFilter } from '../../types/inventory';
import { getPurchaseOrders, formatCurrency, formatDate, getStatusColor, getStatusLabel } from '../../services/documents';

const PurchaseOrdersTab: React.FC = () => {
  const [pos, setPos] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filters, setFilters] = useState<PurchaseOrderFilter>({});
  const [expandedPO, setExpandedPO] = useState<string | null>(null);

  useEffect(() => {
    loadPurchaseOrders();
  }, [page, filters]);

  const loadPurchaseOrders = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await getPurchaseOrders(page, 20, filters);
      setPos(response.data);
      setTotalPages(response.pagination.total_pages);
    } catch (err: any) {
      setError(err.message || 'Failed to load purchase orders');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (filterKey: keyof PurchaseOrderFilter, value: any) => {
    setFilters({ ...filters, [filterKey]: value });
    setPage(1);
  };

  const togglePOExpansion = (poId: string) => {
    setExpandedPO(expandedPO === poId ? null : poId);
  };

  if (loading && pos.length === 0) {
    return <div className="loading-state">Loading purchase orders...</div>;
  }

  if (error) {
    return <div className="error-state">Error: {error}</div>;
  }

  return (
    <div className="purchase-orders-tab">
      <div className="tab-header">
        <h2>Purchase Orders</h2>
        <p className="tab-description">View and track purchase orders</p>
      </div>

      {/* Filters */}
      <div className="filters-section">
        <select
          value={filters.status || ''}
          onChange={(e) => handleFilterChange('status', e.target.value || undefined)}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          <option value={POStatus.PENDING}>Pending</option>
          <option value={POStatus.PARTIALLY_RECEIVED}>Partially Received</option>
          <option value={POStatus.FULLY_RECEIVED}>Fully Received</option>
          <option value={POStatus.CANCELLED}>Cancelled</option>
        </select>
      </div>

      {/* PO List */}
      {pos.length === 0 ? (
        <div className="empty-state">
          <p>No purchase orders found</p>
        </div>
      ) : (
        <>
          <div className="po-list">
            {pos.map((po) => (
              <div key={po._id} className="po-card">
                <div className="po-header" onClick={() => togglePOExpansion(po._id)}>
                  <div className="po-main-info">
                    <h3>{po.po_number}</h3>
                    <p className="po-supplier">{po.supplier_name || po.supplier_id}</p>
                  </div>
                  <div className="po-summary">
                    <span className={`status-badge ${getStatusColor(po.status)}`}>
                      {getStatusLabel(po.status)}
                    </span>
                    <span className="po-total">{formatCurrency(po.total_amount_inr)}</span>
                    <span className="po-date">{formatDate(po.po_date)}</span>
                    <span className="expand-icon">{expandedPO === po._id ? '▼' : '▶'}</span>
                  </div>
                </div>

                {expandedPO === po._id && (
                  <div className="po-details">
                    <div className="po-info-grid">
                      <div className="info-item">
                        <label>Expected Delivery:</label>
                        <span>{formatDate(po.expected_delivery_date)}</span>
                      </div>
                      <div className="info-item">
                        <label>Total Items:</label>
                        <span>{po.items.length}</span>
                      </div>
                      <div className="info-item">
                        <label>Created By:</label>
                        <span>{po.created_by}</span>
                      </div>
                      <div className="info-item">
                        <label>Created:</label>
                        <span>{formatDate(po.created_at)}</span>
                      </div>
                    </div>

                    <h4>Items</h4>
                    <table className="items-table">
                      <thead>
                        <tr>
                          <th>Material</th>
                          <th>Ordered</th>
                          <th>Received</th>
                          <th>Unit</th>
                          <th>Unit Cost</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {po.items.map((item, index) => (
                          <tr key={index}>
                            <td>{item.material_name}</td>
                            <td>{item.quantity_ordered}</td>
                            <td>{item.quantity_received}</td>
                            <td>{item.unit}</td>
                            <td>{formatCurrency(item.unit_cost_inr)}</td>
                            <td>{formatCurrency(item.line_total_inr)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                Previous
              </button>
              <span>Page {page} of {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default PurchaseOrdersTab;
