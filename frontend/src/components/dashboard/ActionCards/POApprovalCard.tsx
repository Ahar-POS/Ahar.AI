/**
 * POApprovalCard — progressive disclosure PO approval UI.
 *
 * compact variant: shows list_id, cost, pending count pill — no buttons (used in board columns).
 * detail variant:  full review UI with Approve All / Review Items / POItemRows (used in modal).
 */

import { useState, useEffect } from 'react';
import {
  POApprovalCard as POApprovalCardData,
  POItemDecision,
  reviewPurchaseOrder,
} from '../../../services/ownerDashboard';
import api from '../../../services/api';
import { formatInventoryQuantity } from '../../../utils/inventoryUnits';

const REJECTION_REASONS = [
  'Too expensive',
  'Already have stock',
  'Wrong supplier',
  'Other',
];

interface ItemState {
  action: 'approve' | 'reject' | null;
  quantity: string;
  reason: string;
}

interface ShoppingListItem {
  material_id: string;
  material_name: string;
  quantity_to_order: number;
  unit: string;
  unit_cost_inr: number;
  urgency: string;
  status?: string;
}

interface Props {
  card: POApprovalCardData;
  variant?: 'compact' | 'detail';
  onDecisionSubmitted: () => void;
}

export default function POApprovalCard({ card, variant = 'detail', onDecisionSubmitted }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [items, setItems] = useState<Record<string, ItemState>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ageLabel = formatAge(card.generated_at);

  const setItemAction = (materialId: string, action: 'approve' | 'reject') => {
    setItems((prev) => ({
      ...prev,
      [materialId]: { ...defaultItem(prev[materialId]), action },
    }));
  };

  const setItemQuantity = (materialId: string, value: string) => {
    setItems((prev) => ({
      ...prev,
      [materialId]: { ...defaultItem(prev[materialId]), quantity: value },
    }));
  };

  const setItemReason = (materialId: string, reason: string) => {
    setItems((prev) => ({
      ...prev,
      [materialId]: { ...defaultItem(prev[materialId]), reason },
    }));
  };

  const buildDecisions = (): POItemDecision[] =>
    Object.entries(items)
      .filter(([, s]) => s.action !== null)
      .map(([materialId, s]) => ({
        material_id: materialId,
        action: s.action as 'approve' | 'reject',
        quantity: s.action === 'approve' ? (parseFloat(s.quantity) || undefined) : undefined,
        reason: s.action === 'reject' ? s.reason || undefined : undefined,
      }));

  const handleApproveAll = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await reviewPurchaseOrder(card.po_id, []);
      onDecisionSubmitted();
    } catch {
      setError('Failed to submit. Try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitDecisions = async () => {
    const decisions = buildDecisions();
    if (decisions.length === 0) {
      setError('Select at least one item decision before submitting.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await reviewPurchaseOrder(card.po_id, decisions);
      onDecisionSubmitted();
    } catch {
      setError('Failed to submit decisions. Try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (variant === 'compact') {
    return (
      <div className="board-card-compact board-card--po">
        <div className="board-card-name">{card.list_id}</div>
        <div className="board-card-sub">
          ₹{formatCost(card.total_cost_inr)} · {card.supplier_count} supplier{card.supplier_count !== 1 ? 's' : ''}
        </div>
        <span className="board-card-pill pill--warning">{card.pending_items} pending</span>
      </div>
    );
  }

  return (
    <div className="action-card action-card--po">
      <div className="action-card-header">
        <span className="action-card-badge badge--warning">PO approval</span>
        <span className="action-card-type-label">
          {card.pending_items} of {card.total_items} pending · {ageLabel}
        </span>
      </div>
      <div className="action-card-title">{card.list_id}</div>
      <div className="action-card-meta">
        ₹{card.total_cost_inr.toLocaleString('en-IN')} across {card.supplier_count} supplier{card.supplier_count !== 1 ? 's' : ''}
      </div>

      {!expanded && (
        <div className="po-card-actions">
          <button className="btn btn-sm btn-success" onClick={handleApproveAll} disabled={submitting}>
            Approve All
          </button>
          <button className="btn btn-sm btn-outline" onClick={() => setExpanded(true)}>
            Review Items
          </button>
        </div>
      )}

      {expanded && (
        <div className="po-items-review">
          <div className="po-items-note">
            Decide on specific items. You can submit partial decisions and return later.
          </div>
          <POItemRows
            poId={card.po_id}
            itemStates={items}
            onSetAction={setItemAction}
            onSetQuantity={setItemQuantity}
            onSetReason={setItemReason}
          />
          {error && <div className="po-review-error">{error}</div>}
          <div className="po-review-actions">
            <button className="btn btn-sm btn-outline" onClick={() => setExpanded(false)}>
              Collapse
            </button>
            <button className="btn btn-sm btn-primary" onClick={handleSubmitDecisions} disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit Decisions'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Per-item rows ──────────────────────────────────────────────────────────

function POItemRows({
  poId,
  itemStates,
  onSetAction,
  onSetQuantity,
  onSetReason,
}: {
  poId: string;
  itemStates: Record<string, ItemState>;
  onSetAction: (id: string, action: 'approve' | 'reject') => void;
  onSetQuantity: (id: string, qty: string) => void;
  onSetReason: (id: string, reason: string) => void;
}) {
  const [listItems, setListItems] = useState<ShoppingListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.get(`/approvals/${poId}`)
      .then((res) => { if (!cancelled) setListItems(res.data.data?.items ?? []); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [poId]);

  if (loading) return <div className="po-items-loading">Loading items…</div>;
  if (listItems.length === 0) return <div className="po-items-empty">No items found.</div>;

  return (
    <div className="po-item-list">
      {listItems.map((item) => {
        const state = itemStates[item.material_id] ?? defaultItem(undefined);
        const alreadyDecided = item.status === 'approved' || item.status === 'rejected';
        const disp = formatInventoryQuantity(item.quantity_to_order, item.unit, item.unit_cost_inr);

        return (
          <div key={item.material_id} className={`po-item-row ${alreadyDecided ? 'po-item-row--decided' : ''}`}>
            <div className="po-item-info">
              <span className="po-item-name">{item.material_name}</span>
              <span className="po-item-detail">
                {disp.value} {disp.unit} · {disp.costPerUnit}
              </span>
              {alreadyDecided && (
                <span className={`po-item-decided-badge po-item-decided-badge--${item.status}`}>
                  {item.status}
                </span>
              )}
            </div>

            {!alreadyDecided && (
              <div className="po-item-controls">
                <button
                  className={`po-toggle-btn ${state.action === 'approve' ? 'po-toggle-btn--active-approve' : ''}`}
                  onClick={() => onSetAction(item.material_id, 'approve')}
                >
                  Approve
                </button>
                {state.action === 'approve' && (
                  <input
                    type="number"
                    className="po-qty-input"
                    placeholder={String(item.quantity_to_order)}
                    value={state.quantity}
                    onChange={(e) => onSetQuantity(item.material_id, e.target.value)}
                    min={0}
                  />
                )}
                <button
                  className={`po-toggle-btn ${state.action === 'reject' ? 'po-toggle-btn--active-reject' : ''}`}
                  onClick={() => onSetAction(item.material_id, 'reject')}
                >
                  Reject
                </button>
                {state.action === 'reject' && (
                  <select
                    className="po-reason-select"
                    value={state.reason}
                    onChange={(e) => onSetReason(item.material_id, e.target.value)}
                  >
                    <option value="">Select reason…</option>
                    {REJECTION_REASONS.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function defaultItem(existing?: ItemState): ItemState {
  return existing ?? { action: null, quantity: '', reason: '' };
}

function formatAge(isoDate: string): string {
  if (!isoDate) return '';
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatCost(inr: number): string {
  if (inr >= 100000) return `${(inr / 100000).toFixed(1)}L`;
  if (inr >= 1000) return `${(inr / 1000).toFixed(1)}K`;
  return inr.toLocaleString('en-IN');
}
