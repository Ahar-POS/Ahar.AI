/**
 * ShoppingListPanel — permanent Action Queue widget showing items
 * the Inventory Agent is requesting owner approval for.
 *
 * Shows escalated (pending_review) items only.
 * Badge reflects live pending count.
 * Clicking "Review" opens ShoppingListModal for full approval flow.
 */

import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { getPendingApprovals } from '../../services/approvals';
import type { ShoppingList, ShoppingListItem } from '../../types/approvals';
import ShoppingListModal from './ShoppingListModal';
import { formatInventoryQuantity } from '../../utils/inventoryUnits';
import { getIngredientIcon } from '../../utils/ingredientIcons';

const URGENCY_ORDER = { URGENT: 0, STANDARD: 1, LOW_PRIORITY: 2 };

function urgencyLabel(urgency: string) {
  switch (urgency) {
    case 'URGENT':       return { text: 'URGENT',   cls: 'urgency-urgent' };
    case 'STANDARD':     return { text: 'STANDARD', cls: 'urgency-standard' };
    case 'LOW_PRIORITY': return { text: 'LOW PRI',  cls: 'urgency-low' };
    default:             return { text: urgency,    cls: 'urgency-low' };
  }
}

interface Props {
  onRefresh?: () => void;
  onCountChange?: (count: number) => void;
  emptyLabel?: string;
}

export default function ShoppingListPanel({ onRefresh, onCountChange, emptyLabel }: Props) {
  const [list, setList] = useState<ShoppingList | null>(null);
  const [pendingItems, setPendingItems] = useState<ShoppingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  const PENDING_STATUSES = new Set(['pending_review', 'pending']);

  const load = useCallback(async () => {
    try {
      const res = await getPendingApprovals();
      const lists: ShoppingList[] = res.data ?? [];
      if (lists.length > 0) {
        const active = lists[0];
        setList(active);
        const pending = (active.items ?? [])
          .filter((i) => PENDING_STATUSES.has(i.item_status ?? 'pending_review'))
          .sort((a, b) => (URGENCY_ORDER[a.urgency] ?? 2) - (URGENCY_ORDER[b.urgency] ?? 2));
        setPendingItems(pending);
        onCountChange?.(pending.length);
      } else {
        // Keep last known list to avoid widget disappearing; just clear pending items
        setPendingItems([]);
        onCountChange?.(0);
      }
    } catch {
      // silently ignore — panel just shows empty state
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

  useEffect(() => {
    load();
  }, [load]);

  const handleModalClose = () => {
    setModalOpen(false);
    load();
    onRefresh?.();
  };

  const fmtCost = (paise: number) =>
    `₹${(paise / 100).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  const pendingCount = pendingItems.length;

  if (loading) {
    return (
      <div className="board-empty-state" aria-busy="true">
        <div className="board-empty-text">Loading…</div>
      </div>
    );
  }

  return (
    <>
      {pendingCount === 0 ? (
        <div className="board-empty-state">
          <div className="board-empty-icon">✓</div>
          <div className="board-empty-text">
            {emptyLabel || 'Inventory Agent verified stock levels. No procurement required.'}
          </div>
        </div>
      ) : (
        <button
          className="board-card-button"
          onClick={() => setModalOpen(true)}
          aria-label={`Review shopping list (${pendingCount} pending items)`}
        >
          <div className="board-card-compact board-card--info sl-card-fixed-height">
            <div className="board-card-name">Shopping list</div>
            
            <div className="sl-compact-summary">
              {pendingCount} item{pendingCount !== 1 ? 's' : ''} to review
            </div>

            <div className="sl-compact-list">
              {pendingItems.slice(0, 3).map((item) => {
                const urg = urgencyLabel(item.urgency);
                const { value: qtyValue, unit: displayUnit } = formatInventoryQuantity(
                  item.quantity_to_order, item.unit, item.unit_cost_inr ?? 0
                );
                return (
                  <div key={item.material_id} className="sl-compact-item">
                    <span className="sl-compact-icon">
                      {getIngredientIcon(item.material_name)}
                    </span>
                    <span className="sl-compact-item-name">{item.material_name}</span>
                    <span className="sl-compact-item-qty">{qtyValue} {displayUnit}</span>
                    <span className="sl-compact-item-total">{fmtCost(item.line_total_inr)}</span>
                    <span className={`sl-urgency-tag ${urg.cls}`}>{urg.text}</span>
                  </div>
                );
              })}
              {pendingCount > 3 && (
                <div className="sl-compact-more">+{pendingCount - 3} more items...</div>
              )}
            </div>

            <div className="sl-compact-action">
              Review and Approve →
            </div>
          </div>
        </button>
      )}

      {modalOpen && list && createPortal(
        <ShoppingListModal
          list={list}
          pendingItems={pendingItems}
          onClose={handleModalClose}
        />,
        document.body
      )}
    </>
  );
}
