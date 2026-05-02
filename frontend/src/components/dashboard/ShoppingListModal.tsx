/**
 * ShoppingListModal — full popup for owner to review and approve escalated items.
 *
 * Shows per-item LLM reasoning, urgency, Hyperpure price.
 * Supports per-item approve/reject and bulk actions.
 * On approval → calls approve-items API which triggers immediate Hyperpure order.
 */

import { useState, useMemo } from 'react';
import { reviewShoppingListItems } from '../../services/approvals';
import type { ShoppingList, ShoppingListItem, POItemDecision } from '../../types/approvals';
import { formatInventoryQuantity } from '../../utils/inventoryUnits';
import { getIngredientIcon } from '../../utils/ingredientIcons';
import ConfirmModal from '../ConfirmModal';
import FloatingBanner from '../FloatingBanner';

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
  const [localItems, setLocalItems] = useState<ShoppingListItem[]>(pendingItems);
  const [decisions, setDecisions] = useState<Record<string, ItemDecision>>(() =>
    Object.fromEntries(pendingItems.map((i) => [i.material_id, { decision: null, rejectReason: '' }]))
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [itemToReject, setItemToReject] = useState<string | null>(null);
  const [notification, setNotification] = useState<string | null>(null);

  const setDecision = (materialId: string, decision: Decision) =>
    setDecisions((prev) => ({ ...prev, [materialId]: { ...prev[materialId], decision } }));

  const setRejectReason = (materialId: string, reason: string) =>
    setDecisions((prev) => ({ ...prev, [materialId]: { ...prev[materialId], rejectReason: reason } }));

  const handleRejectClick = (materialId: string) => {
    const dec = decisions[materialId];
    if (dec?.decision === 'reject') {
      if (dec.rejectReason) {
        setItemToReject(materialId);
      } else {
        setDecision(materialId, null);
      }
    } else {
      setDecision(materialId, 'reject');
    }
  };

  const handleApproveAll = async () => {
    const itemDecisions: POItemDecision[] = localItems.map((i) => ({
      material_id: i.material_id,
      action: 'approve',
      quantity: i.quantity_to_order,
    }));
    setSuccessMsg('Approved. Hyperpure order is being placed.');
    await submitDecisions(itemDecisions);
  };

  const handleSubmitSelected = async () => {
    const itemDecisions: POItemDecision[] = localItems
      .filter((i) => decisions[i.material_id].decision === 'approve')
      .map((i) => {
        const d = decisions[i.material_id];
        return {
          material_id: i.material_id,
          action: 'approve',
          quantity: i.quantity_to_order,
        };
      });

    if (itemDecisions.length === 0) {
      setError('Select at least one item to approve.');
      return;
    }

    setSuccessMsg(`${itemDecisions.length} item(s) approved. Hyperpure order is being placed.`);
    await submitDecisions(itemDecisions);
  };

  const handleConfirmSingleReject = async () => {
    if (!itemToReject) return;
    const materialId = itemToReject;
    const reason = decisions[materialId].rejectReason || 'Rejected by owner';
    
    setSubmitting(true);
    setError(null);
    try {
      await reviewShoppingListItems(list._id, {
        items: [{ material_id: materialId, action: 'reject', reason }]
      });
      // Remove from local items immediately
      const item = localItems.find(i => i.material_id === materialId);
      setLocalItems(prev => prev.filter(i => i.material_id !== materialId));
      setItemToReject(null);
      setNotification(`${item?.material_name || 'Item'} removed from shopping list.`);
    } catch {
      setError('Failed to reject item. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const submitDecisions = async (itemDecisions: POItemDecision[]) => {
    setSubmitting(true);
    setError(null);
    try {
      await reviewShoppingListItems(list._id, { items: itemDecisions });
      setSuccess(true);
      setTimeout(() => onClose(), 1500);
    } catch {
      setError('Failed to submit decisions. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const approvedCount = useMemo(() => 
    localItems.filter((i) => decisions[i.material_id]?.decision === 'approve').length,
    [localItems, decisions]
  );

  const fmtCost = (paise: number) =>
    `₹${(paise / 100).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  const totalCost = useMemo(() => 
    localItems.reduce((acc, i) => acc + (i.line_total_inr || 0), 0),
    [localItems]
  );

  const generatedTime = list.generated_at
    ? new Date(list.generated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    : '';

  if (localItems.length === 0 && !success) {
    onClose();
    return null;
  }

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
              {localItems.length} items pending · <span className="sl-modal-total">Total {fmtCost(totalCost)}</span> · generated at {generatedTime}
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
            <span>Action Recorded</span>
            <span className="sl-modal-meta">{successMsg}</span>
          </div>
        ) : (
          <>
            <div className="sl-modal-items">
              {localItems.map((item) => {
                const dec = decisions[item.material_id];
                const { value: qtyValue, unit: displayUnit, costPerUnit } = formatInventoryQuantity(
                  item.quantity_to_order, item.unit, item.unit_cost_inr ?? 0
                );
                const displayQty = `${qtyValue} ${displayUnit}`;
                const price = item.unit_cost_inr ? costPerUnit : null;
                const lineTotal = fmtCost(item.line_total_inr);
                const stockDays = typeof item.days_until_stockout === 'number'
                  ? `${item.days_until_stockout.toFixed(0)}d left`
                  : null;

                return (
                  <div
                    key={item.material_id}
                    className={`sl-modal-item ${dec?.decision === 'approve' ? 'sl-modal-item--approved' : ''} ${dec?.decision === 'reject' ? 'sl-modal-item--rejected' : ''}`}
                  >
                    <div className="sl-modal-item-main">
                      <div className="sl-modal-icon-container">
                        {getIngredientIcon(item.material_name)}
                      </div>

                      <div className="sl-modal-item-content">
                        <div className="sl-modal-item-row">
                          <div className="sl-modal-item-name-group">
                            <span className="sl-modal-item-name">{item.material_name}</span>
                            <UrgencyTag urgency={item.urgency} />
                          </div>
                          <span className="sl-item-total">{lineTotal}</span>
                        </div>

                        <div className="sl-modal-item-row sl-modal-item-row--sub">
                          <div className="sl-modal-item-details">
                            <span className="sl-item-qty">{displayQty}</span>
                            {price && <span className="sl-item-price"> · {price}</span>}
                          </div>
                          {stockDays && <span className="sl-stock-days">{stockDays}</span>}
                        </div>
                      </div>
                    </div>

                    <div className="sl-modal-item-footer">
                      {item.agent_reason ? (
                        <div className="sl-modal-item-reason">
                          <span className="sl-reason-icon">ⓘ</span>
                          <span>{item.agent_reason}</span>
                        </div>
                      ) : (
                        <div className="sl-modal-item-reason-placeholder" />
                      )}

                      <div className="sl-modal-item-controls">
                        <button
                          className={`sl-decision-btn sl-decision-btn--approve ${dec?.decision === 'approve' ? 'sl-decision-btn--active' : ''}`}
                          onClick={() => setDecision(item.material_id, dec?.decision === 'approve' ? null : 'approve')}
                          disabled={submitting}
                          title="Approve"
                        >
                          ✓
                        </button>
                        <button
                          className={`sl-decision-btn sl-decision-btn--reject ${dec?.decision === 'reject' ? 'sl-decision-btn--active' : ''}`}
                          onClick={() => handleRejectClick(item.material_id)}
                          disabled={submitting}
                          title={dec?.decision === 'reject' && dec.rejectReason ? "Confirm Reject" : "Reject"}
                        >
                          ✕
                        </button>
                      </div>
                    </div>

                    {dec?.decision === 'reject' && (
                      <div className="sl-reject-controls">
                        <select
                          className="sl-reject-reason"
                          value={dec.rejectReason}
                          onChange={(e) => setRejectReason(item.material_id, e.target.value)}
                        >
                          <option value="">Select reason for rejection…</option>
                          {REJECTION_REASONS.map((r) => (
                            <option key={r} value={r}>{r}</option>
                          ))}
                        </select>
                      </div>
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
                {approvedCount > 0 && approvedCount < localItems.length && (
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

      {itemToReject && (
        <ConfirmModal
          title="Confirm Rejection"
          message={`Are you sure you want to reject ${localItems.find(i => i.material_id === itemToReject)?.material_name}? This item will be removed from the current list.`}
          confirmLabel="Reject Item"
          variant="danger"
          onConfirm={handleConfirmSingleReject}
          onCancel={() => setItemToReject(null)}
        />
      )}
      {notification && (
        <FloatingBanner
          message={notification}
          onClose={() => setNotification(null)}
        />
      )}
    </div>
  );
}


