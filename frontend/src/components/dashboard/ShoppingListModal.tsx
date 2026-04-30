/**
 * ShoppingListModal — full popup for owner to review and approve escalated items.
 *
 * Shows per-item LLM reasoning, urgency, Hyperpure price.
 * Supports per-item approve/reject and bulk actions.
 * On approval → calls approve-items API which triggers immediate Hyperpure order.
 */

import { useState } from 'react';
import { approveShoppingListItems } from '../../services/approvals';
import type { ShoppingList, ShoppingListItem } from '../../types/approvals';
import { formatInventoryQuantity } from '../../utils/inventoryUnits';

const REJECTION_REASONS = [
  'Too expensive',
  'Already have stock',
  'Wrong supplier',
  'Ordering in bulk later',
  'Other',
];

type Decision = 'approve' | 'reject' | null;

interface ItemDecision {
  decision: Decision;
  rejectReason: string;
}

function UrgencyTag({ urgency }: { urgency: string }) {
  const map: Record<string, { text: string; cls: string }> = {
    URGENT:       { text: 'URGENT',   cls: 'urgency-urgent' },
    STANDARD:     { text: 'STANDARD', cls: 'urgency-standard' },
    LOW_PRIORITY: { text: 'LOW PRI',  cls: 'urgency-low' },
  };
  const tag = map[urgency] ?? { text: urgency, cls: 'urgency-low' };
  return <span className={`sl-urgency-tag ${tag.cls}`}>{tag.text}</span>;
}

interface Props {
  list: ShoppingList;
  pendingItems: ShoppingListItem[];
  onClose: () => void;
}

export default function ShoppingListModal({ list, pendingItems, onClose }: Props) {
  const [decisions, setDecisions] = useState<Record<string, ItemDecision>>(() =>
    Object.fromEntries(pendingItems.map((i) => [i.material_id, { decision: null, rejectReason: '' }]))
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const setDecision = (materialId: string, decision: Decision) =>
    setDecisions((prev) => ({ ...prev, [materialId]: { ...prev[materialId], decision } }));

  const setRejectReason = (materialId: string, reason: string) =>
    setDecisions((prev) => ({ ...prev, [materialId]: { ...prev[materialId], rejectReason: reason } }));

  const handleApproveAll = async () => {
    const allIds = pendingItems.map((i) => i.material_id);
    setDecisions(Object.fromEntries(allIds.map((id) => [id, { decision: 'approve', rejectReason: '' }])));
    await submitApprovals(allIds);
  };

  const handleSubmitSelected = async () => {
    const approvedIds = Object.entries(decisions)
      .filter(([, d]) => d.decision === 'approve')
      .map(([id]) => id);
    if (approvedIds.length === 0) {
      setError('Select at least one item to approve.');
      return;
    }
    await submitApprovals(approvedIds);
  };

  const submitApprovals = async (materialIds: string[]) => {
    setSubmitting(true);
    setError(null);
    try {
      await approveShoppingListItems(list._id, { material_ids: materialIds });
      setSuccess(true);
      setTimeout(() => onClose(), 1500);
    } catch {
      setError('Failed to submit approval. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const approvedCount = Object.values(decisions).filter((d) => d.decision === 'approve').length;
  const generatedTime = list.generated_at
    ? new Date(list.generated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div
      className="sl-modal-backdrop"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label="Shopping list review"
    >
      <div className="sl-modal">
        <div className="sl-modal-header">
          <div className="sl-modal-title-group">
            <span className="sl-modal-title">Shopping List Review</span>
            <span className="sl-modal-meta">
              {pendingItems.length} items pending · generated at {generatedTime}
              {list.confidence_score > 0 && (
                <span className="sl-modal-conf"> · conf {(list.confidence_score * 100).toFixed(0)}%</span>
              )}
            </span>
          </div>
          <button className="sl-modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {list.reasoning && (
          <div className="sl-modal-reasoning">
            <span className="sl-reasoning-icon">💡</span>
            <span className="sl-reasoning-text">{list.reasoning}</span>
          </div>
        )}

        {success ? (
          <div className="sl-modal-success">
            ✓ Approved — Hyperpure order is being placed.
          </div>
        ) : (
          <>
            <div className="sl-modal-items">
              {pendingItems.map((item) => {
                const dec = decisions[item.material_id];
                const { value: qtyValue, unit: displayUnit, costPerUnit } = formatInventoryQuantity(
                  item.quantity_to_order, item.unit, item.unit_cost_inr ?? 0
                );
                const displayQty = `${qtyValue} ${displayUnit}`;
                const price = item.unit_cost_inr ? costPerUnit : null;
                const stockDays = typeof item.days_until_stockout === 'number'
                  ? `${item.days_until_stockout.toFixed(0)}d left`
                  : null;

                return (
                  <div
                    key={item.material_id}
                    className={`sl-modal-item ${dec?.decision === 'approve' ? 'sl-modal-item--approved' : ''} ${dec?.decision === 'reject' ? 'sl-modal-item--rejected' : ''}`}
                  >
                    <div className="sl-modal-item-info">
                      <div className="sl-modal-item-top">
                        <span className="sl-modal-item-name">{item.material_name}</span>
                        <UrgencyTag urgency={item.urgency} />
                      </div>
                      <div className="sl-modal-item-details">
                        <span>{displayQty}</span>
                        {price && <span>{price}</span>}
                        {stockDays && <span className="sl-stock-days">{stockDays}</span>}
                      </div>
                      {item.agent_reason && (
                        <div className="sl-modal-item-reason">
                          <span className="sl-reason-icon">⚠</span>
                          <span>{item.agent_reason}</span>
                        </div>
                      )}
                    </div>

                    <div className="sl-modal-item-controls">
                      <button
                        className={`sl-decision-btn sl-decision-btn--approve ${dec?.decision === 'approve' ? 'sl-decision-btn--active' : ''}`}
                        onClick={() => setDecision(item.material_id, dec?.decision === 'approve' ? null : 'approve')}
                        disabled={submitting}
                      >
                        ✓
                      </button>
                      <button
                        className={`sl-decision-btn sl-decision-btn--reject ${dec?.decision === 'reject' ? 'sl-decision-btn--active' : ''}`}
                        onClick={() => setDecision(item.material_id, dec?.decision === 'reject' ? null : 'reject')}
                        disabled={submitting}
                      >
                        ✕
                      </button>
                    </div>

                    {dec?.decision === 'reject' && (
                      <select
                        className="sl-reject-reason"
                        value={dec.rejectReason}
                        onChange={(e) => setRejectReason(item.material_id, e.target.value)}
                      >
                        <option value="">Select reason…</option>
                        {REJECTION_REASONS.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    )}
                  </div>
                );
              })}
            </div>

            {error && <div className="sl-modal-error">{error}</div>}

            <div className="sl-modal-footer">
              <button
                className="btn btn-outline"
                onClick={onClose}
                disabled={submitting}
              >
                Close
              </button>
              <div className="sl-modal-footer-actions">
                <button
                  className="btn btn-primary"
                  onClick={handleApproveAll}
                  disabled={submitting}
                >
                  {submitting ? 'Placing order…' : 'Approve All & Order'}
                </button>
                {approvedCount > 0 && approvedCount < pendingItems.length && (
                  <button
                    className="btn btn-success"
                    onClick={handleSubmitSelected}
                    disabled={submitting}
                  >
                    Approve {approvedCount} Selected
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
