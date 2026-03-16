/**
 * BillsTab - Display and manage bills/invoices.
 */
import React, { useState, useEffect } from 'react';
import './TabsCommon.css';
import { Bill, BillStatus, BillFilter } from '../../types/inventory';
import {
  getBills,
  approvePendingBill,
  rejectPendingBill,
  formatCurrency,
  formatDate,
  getStatusColor,
  getStatusLabel
} from '../../services/documents';

const BillsTab: React.FC = () => {
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filters, setFilters] = useState<BillFilter>({});
  const [expandedBill, setExpandedBill] = useState<string | null>(null);
  const [itemDrafts, setItemDrafts] = useState<Record<string, Bill['items']>>({});
  const [updatingBillId, setUpdatingBillId] = useState<string | null>(null);

  useEffect(() => {
    loadBills();
  }, [page, filters]);

  const loadBills = async () => {
    setLoading(true);
    setLoadError(null);

    try {
      const response = await getBills(page, 20, filters);
      setBills(response.data);
      setItemDrafts((prev) => {
        const next = { ...prev };
        response.data.forEach((bill) => {
          next[bill._id] = bill.items.map((item) => ({ ...item }));
        });
        return next;
      });
      setTotalPages(response.pagination.total_pages);
    } catch (err: any) {
      setLoadError(err.message || 'Failed to load bills');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (filterKey: keyof BillFilter, value: any) => {
    setFilters({ ...filters, [filterKey]: value });
    setPage(1);
  };

  const toggleBillExpansion = (billId: string) => {
    setExpandedBill(expandedBill === billId ? null : billId);
  };

  const handleQuantityEdit = (billId: string, itemIndex: number, quantity: number) => {
    setItemDrafts((prev) => {
      const next = { ...prev };
      const items = [...(next[billId] || [])];
      if (!items[itemIndex]) return prev;
      const unitCost = items[itemIndex].unit_cost_inr;
      items[itemIndex] = {
        ...items[itemIndex],
        quantity,
        line_total_inr: Math.round(quantity * unitCost)
      };
      next[billId] = items;
      return next;
    });
  };

  const handleApprovePending = async (bill: Bill) => {
    const items = itemDrafts[bill._id] || bill.items;
    setUpdatingBillId(bill._id);
    setUpdateError(null);
    try {
      await approvePendingBill(bill._id, { items });
      await loadBills();
    } catch (err: any) {
      setUpdateError(err.message || 'Failed to approve pending bill');
    } finally {
      setUpdatingBillId(null);
    }
  };

  const handleRejectPending = async (bill: Bill) => {
    const items = itemDrafts[bill._id] || bill.items;
    setUpdatingBillId(bill._id);
    setUpdateError(null);
    try {
      await rejectPendingBill(bill._id, { items, reason: 'Rejected from Bills tab' });
      await loadBills();
    } catch (err: any) {
      setUpdateError(err.message || 'Failed to reject pending bill');
    } finally {
      setUpdatingBillId(null);
    }
  };

  if (loading && bills.length === 0) {
    return <div className="loading-state">Loading bills...</div>;
  }

  if (loadError) {
    return <div className="error-state">Error: {loadError}</div>;
  }

  return (
    <div className="bills-tab">
      <div className="tab-header">
        <h2>Bills & Invoices</h2>
        <p className="tab-description">View and track bills with price variance detection</p>
      </div>

      {updateError && <div className="error-state">Error: {updateError}</div>}

      {/* Filters */}
      <div className="filters-section">
        <select
          value={filters.status || ''}
          onChange={(e) => handleFilterChange('status', e.target.value || undefined)}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          <option value={BillStatus.PENDING_REVIEW}>Pending Review</option>
          <option value={BillStatus.APPROVED}>Approved</option>
          <option value={BillStatus.REJECTED}>Rejected</option>
        </select>

        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={filters.has_price_discrepancies || false}
            onChange={(e) => handleFilterChange('has_price_discrepancies', e.target.checked || undefined)}
          />
          <span>Show only bills with price discrepancies</span>
        </label>
      </div>

      {/* Bill List */}
      {bills.length === 0 ? (
        <div className="empty-state">
          <p>No bills found</p>
        </div>
      ) : (
        <>
          <div className="bill-list">
            {bills.map((bill) => {
              const billStatus = bill.status || BillStatus.PENDING_REVIEW;
              return (
              <div key={bill._id} className="bill-card">
                <div className="bill-header" onClick={() => toggleBillExpansion(bill._id)}>
                  <div className="bill-main-info">
                    <h3>{bill.invoice_number}</h3>
                    <p className="bill-supplier">{bill.supplier_name || bill.supplier_id}</p>
                    {bill.has_price_discrepancies && (
                      <span className="variance-flag">⚠️ Price Variance</span>
                    )}
                  </div>
                  <div className="bill-summary">
                    <span className={`status-badge ${getStatusColor(billStatus)}`}>
                      {getStatusLabel(billStatus)}
                    </span>
                    <span className="bill-total">{formatCurrency(bill.total_amount_inr)}</span>
                    <span className="bill-date">{formatDate(bill.invoice_date)}</span>
                    <span className="expand-icon">{expandedBill === bill._id ? '▼' : '▶'}</span>
                  </div>
                </div>

                {expandedBill === bill._id && (
                  <div className="bill-details">
                    {billStatus === BillStatus.PENDING_REVIEW && (
                      <div className="bill-status-actions">
                        <button
                          className="status-update-btn"
                          onClick={() => handleRejectPending(bill)}
                          disabled={updatingBillId === bill._id}
                        >
                          {updatingBillId === bill._id ? 'Updating...' : 'Reject Bill'}
                        </button>
                        <button
                          className="status-update-btn"
                          onClick={() => handleApprovePending(bill)}
                          disabled={updatingBillId === bill._id}
                        >
                          {updatingBillId === bill._id ? 'Updating...' : 'Approve Bill'}
                        </button>
                      </div>
                    )}

                    <div className="bill-info-grid">
                      <div className="info-item">
                        <label>Delivery Date:</label>
                        <span>{formatDate(bill.actual_delivery_date)}</span>
                      </div>
                      <div className="info-item">
                        <label>Total Items:</label>
                        <span>{bill.items.length}</span>
                      </div>
                      <div className="info-item">
                        <label>Linked PO:</label>
                        <span>{bill.linked_po_id || 'None'}</span>
                      </div>
                      <div className="info-item">
                        <label>Inventory Updated:</label>
                        <span>{bill.inventory_updated ? '✓ Yes' : '✗ No'}</span>
                      </div>
                    </div>

                    {/* Price Variance Summary */}
                    {bill.has_price_discrepancies && bill.price_variance_summary && (
                      <div className="variance-summary">
                        <h4>Price Variances</h4>
                        <p className="variance-total">
                          Total Variance: {formatCurrency(bill.price_variance_summary.total_variance_amount_inr)}
                        </p>
                        <table className="variance-table">
                          <thead>
                            <tr>
                              <th>Item</th>
                              <th>PO Price</th>
                              <th>Bill Price</th>
                              <th>Variance %</th>
                              <th>Variance Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {bill.price_variance_summary.item_variances.map((variance, index) => (
                              <tr key={index}>
                                <td>{variance.material_name}</td>
                                <td>{formatCurrency(variance.po_unit_cost_inr)}</td>
                                <td>{formatCurrency(variance.bill_unit_cost_inr)}</td>
                                <td className={variance.variance_pct > 0 ? 'positive-variance' : 'negative-variance'}>
                                  {variance.variance_pct > 0 ? '+' : ''}{variance.variance_pct.toFixed(2)}%
                                </td>
                                <td>{formatCurrency(variance.variance_amount_inr)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    <h4>Items</h4>
                    <table className="items-table">
                      <thead>
                        <tr>
                          <th>Material</th>
                          <th>Quantity</th>
                          <th>Unit</th>
                          <th>Unit Cost</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(itemDrafts[bill._id] || bill.items).map((item, index) => (
                          <tr key={index}>
                            <td>{item.material_name}</td>
                            <td>
                              {billStatus === BillStatus.PENDING_REVIEW ? (
                                <input
                                  type="number"
                                  className="editable-field"
                                  value={item.quantity}
                                  min={0}
                                  step="0.01"
                                  onChange={(e) => handleQuantityEdit(
                                    bill._id,
                                    index,
                                    Number(e.target.value || 0)
                                  )}
                                />
                              ) : (
                                item.quantity
                              )}
                            </td>
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
            );
            })}
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

export default BillsTab;
