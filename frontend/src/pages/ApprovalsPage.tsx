/**
 * Hyperpure Orders Page — read-only tracking of all orders placed on Hyperpure.
 *
 * Shows POs created by auto-approval or owner approval of the shopping list.
 * Two tabs: Open Orders (status=pending) and Delivered (status=fully_received).
 */

import React, { useState, useEffect, useCallback } from 'react';
import { getHyperpureOrders } from '../services/approvals';
import type { HyperpureOrder, HyperpureOrderItem } from '../services/approvals';
import { formatInventoryQuantity } from '../utils/inventoryUnits';
import './ApprovalsPage.css';

type TabType = 'open' | 'delivered' | 'portal';

const ApprovalsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('open');
  const [orders, setOrders] = useState<HyperpureOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (activeTab === 'portal') return;
    setLoading(true);
    setError(null);
    try {
      const statusFilter = activeTab === 'open' ? 'pending' : 'fully_received';
      const res = await getHyperpureOrders(statusFilter);
      setOrders(res.data ?? []);
    } catch {
      setError('Failed to load Hyperpure orders.');
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => { load(); }, [load]);

  const fmt = (iso?: string) => {
    if (!iso) return '—';
    const utc = iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`;
    return new Date(utc).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: true,
    });
  };

  const fmtCost = (paise: number) =>
    `₹${(paise / 100).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  const toggleExpand = (id: string) =>
    setExpandedId((prev) => (prev === id ? null : id));

  return (
    <div className="approvals-page">
      <div className="approvals-container">
        <header className="approvals-header">
          <h1>Hyperpure Orders</h1>
          <p>Track all orders placed through Hyperpure by the inventory agent</p>
        </header>

        {error && (
          <div className="error-banner">
            <span>⚠ {error}</span>
            <button onClick={() => setError(null)}>×</button>
          </div>
        )}

        <div className="hp-tabs">
          <button
            className={`hp-tab${activeTab === 'open' ? ' hp-tab--active' : ''}`}
            onClick={() => setActiveTab('open')}
          >
            Open Orders
          </button>
          <button
            className={`hp-tab${activeTab === 'delivered' ? ' hp-tab--active' : ''}`}
            onClick={() => setActiveTab('delivered')}
          >
            Delivered
          </button>
          <button
            className={`hp-tab${activeTab === 'portal' ? ' hp-tab--active' : ''}`}
            onClick={() => setActiveTab('portal')}
          >
            Hyperpure Portal
          </button>
        </div>

        {activeTab === 'portal' ? (
          <div className="hp-portal-container">
            <img
              src="/hyperpure-mock.png"
              alt="Hyperpure Portal Mockup"
              style={{ width: '100%', height: 'auto', display: 'block' }}
            />
          </div>
        ) : loading ? (
          <div className="loading-spinner">Loading…</div>
        ) : orders.length === 0 ? (
          <div className="empty-state">
            <p>{activeTab === 'open' ? 'No open Hyperpure orders.' : 'No delivered orders yet.'}</p>
            <p className="empty-state-subtitle">
              {activeTab === 'open'
                ? 'Orders appear here after the inventory agent places them on Hyperpure.'
                : 'Orders move here 60 seconds after placement (mock delivery).'}
            </p>
          </div>
        ) : (
          <div className="hp-orders-list">
            {orders.map((order) => (
              <div key={order._id} className="hp-order-card">
                <div
                  className="hp-order-header"
                  onClick={() => toggleExpand(order._id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && toggleExpand(order._id)}
                >
                  <div className="hp-order-ref">
                    <span className="hp-ref-number">{order.po_number}</span>
                    <span className={`hp-status-badge hp-status-${order.status === 'pending' ? 'open' : 'delivered'}`}>
                      {order.status === 'pending' ? 'Ordered' : 'Delivered'}
                    </span>
                  </div>
                  <div className="hp-order-meta">
                    <span>{order.items.length} item{order.items.length !== 1 ? 's' : ''}</span>
                    <span className="hp-order-cost">{fmtCost(order.total_cost_inr)}</span>
                    <span className="hp-order-date">Ordered: {fmt(order.ordered_at)}</span>
                    {order.delivered_at && (
                      <span className="hp-order-date">Delivered: {fmt(order.delivered_at)}</span>
                    )}
                  </div>
                  <span className="hp-expand-icon">{expandedId === order._id ? '▲' : '▼'}</span>
                </div>

                {expandedId === order._id && (
                  <div className="hp-order-items">
                    <table className="hp-items-table">
                      <thead>
                        <tr>
                          <th>Item</th>
                          <th>Quantity</th>
                          <th>Unit Cost</th>
                          <th>Line Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {order.items.map((item: HyperpureOrderItem) => {
                          const { value, unit, costPerUnit } = formatInventoryQuantity(
                            item.quantity,
                            item.unit,
                            item.unit_cost_inr
                          );
                          return (
                            <tr key={item.material_id}>
                              <td>{item.material_name}</td>
                              <td>{value} {unit}</td>
                              <td>{costPerUnit}</td>
                              <td className="hp-item-total">{fmtCost(item.line_total_inr)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ApprovalsPage;
