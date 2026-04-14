/**
 * ActionQueue — Zone 2.
 *
 * Renders a Trello-style 4-column board. Cards are grouped by type and shown
 * as compact summary tiles. Clicking a tile opens a modal with full details.
 * Revenue anomaly cards older than 7 days are auto-filtered; 24h–7d are shown
 * with a "stale" visual indicator and a dismiss option in the modal.
 */

import { useState, useCallback } from 'react';
import { ActionCard, ActionQueueData } from '../../services/ownerDashboard';
import LowStockCard from './ActionCards/LowStockCard';
import POApprovalCard from './ActionCards/POApprovalCard';
import RevenueAnomalyCard from './ActionCards/RevenueAnomalyCard';
import ExpirySpecialCard from './ActionCards/ExpirySpecialCard';

const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000;      // 24 h
const FILTER_THRESHOLD_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

interface ColumnConfig {
  key: ActionCard['card_type'];
  label: string;
  emptyLabel: string;
}

const COLUMNS: ColumnConfig[] = [
  { key: 'low_stock',       label: 'Low Stock',     emptyLabel: 'No stock issues' },
  { key: 'po_approval',     label: 'PO Approvals',  emptyLabel: 'No pending POs'  },
  { key: 'revenue_anomaly', label: 'Revenue Alerts', emptyLabel: 'No alerts'       },
  { key: 'expiry_special',  label: "Today's Specials", emptyLabel: 'No suggestions' },
];

interface Props {
  data: ActionQueueData;
  onRefresh: () => void;
}

export default function ActionQueue({ data, onRefresh }: Props) {
  const [selectedCard, setSelectedCard] = useState<ActionCard | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  const handleDismissAnomaly = useCallback((alertId: string) => {
    setDismissedIds((prev) => new Set([...prev, alertId]));
    setSelectedCard(null);
  }, []);

  if (data.total_cards === 0) {
    return (
      <div className="action-queue">
        <div className="zone-header">
          <span className="zone-title">Action Queue</span>
        </div>
        <div className="action-queue-empty">
          <span className="action-queue-empty-icon">✓</span>
          <span>All clear — nothing needs your attention right now.</span>
        </div>
      </div>
    );
  }

  // Group and filter cards
  const grouped = groupCards(data.cards, dismissedIds);
  const activeCount = Object.values(grouped).reduce((sum, arr) => sum + arr.length, 0);

  return (
    <div className="action-queue">
      <div className="zone-header">
        <span className="zone-title">Action Queue</span>
        {activeCount > 0 && <span className="zone-count">{activeCount}</span>}
      </div>

      <div className="action-board">
        {COLUMNS.map((col) => {
          const cards = grouped[col.key] ?? [];
          return (
            <BoardColumn
              key={col.key}
              config={col}
              cards={cards}
              onCardClick={setSelectedCard}
            />
          );
        })}
      </div>

      {selectedCard && (
        <CardDetailModal
          card={selectedCard}
          onClose={() => setSelectedCard(null)}
          onRefresh={() => { onRefresh(); setSelectedCard(null); }}
          onDismissAnomaly={handleDismissAnomaly}
        />
      )}
    </div>
  );
}

// ── Board Column ───────────────────────────────────────────────────────────

function BoardColumn({
  config,
  cards,
  onCardClick,
}: {
  config: ColumnConfig;
  cards: ActionCard[];
  onCardClick: (card: ActionCard) => void;
}) {
  return (
    <div className="board-column">
      <div className="board-column-header">
        <span className="board-column-title">{config.label}</span>
        {cards.length > 0 && (
          <span className="board-column-count">{cards.length}</span>
        )}
      </div>
      <div className="board-column-cards">
        {cards.length === 0 ? (
          <div className="board-column-empty">{config.emptyLabel}</div>
        ) : (
          cards.map((card, i) => (
            <button
              key={i}
              className="board-card-button"
              onClick={() => onCardClick(card)}
              aria-label={`View details for ${cardTitle(card)}`}
            >
              <CompactCardRenderer card={card} />
            </button>
          ))
        )}
      </div>
    </div>
  );
}

// ── Compact renderers (gist only, no actions) ─────────────────────────────

function CompactCardRenderer({ card }: { card: ActionCard }) {
  switch (card.card_type) {
    case 'low_stock':
      return <LowStockCard card={card} variant="compact" />;
    case 'po_approval':
      return <POApprovalCard card={card} variant="compact" onDecisionSubmitted={() => {}} />;
    case 'revenue_anomaly': {
      const isStale = isStaleAnomaly(card.created_at);
      return <RevenueAnomalyCard card={card} variant="compact" isStale={isStale} />;
    }
    case 'expiry_special':
      return <ExpirySpecialCard card={card} variant="compact" />;
  }
}

// ── Detail Modal ───────────────────────────────────────────────────────────

function CardDetailModal({
  card,
  onClose,
  onRefresh,
  onDismissAnomaly,
}: {
  card: ActionCard;
  onClose: () => void;
  onRefresh: () => void;
  onDismissAnomaly: (id: string) => void;
}) {
  return (
    <div
      className="card-modal-backdrop"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog"
      aria-modal="true"
    >
      <div className="card-modal">
        <div className="card-modal-header">
          <span className="card-modal-title">{modalTitle(card)}</span>
          <button className="card-modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="card-modal-body">
          <DetailCardRenderer
            card={card}
            onRefresh={onRefresh}
            onDismissAnomaly={onDismissAnomaly}
          />
        </div>
      </div>
    </div>
  );
}

function DetailCardRenderer({
  card,
  onRefresh,
  onDismissAnomaly,
}: {
  card: ActionCard;
  onRefresh: () => void;
  onDismissAnomaly: (id: string) => void;
}) {
  switch (card.card_type) {
    case 'low_stock':
      return <LowStockCard card={card} variant="detail" />;
    case 'po_approval':
      return <POApprovalCard card={card} variant="detail" onDecisionSubmitted={onRefresh} />;
    case 'revenue_anomaly': {
      const isStale = isStaleAnomaly(card.created_at);
      return (
        <RevenueAnomalyCard
          card={card}
          variant="detail"
          isStale={isStale}
          onDismiss={() => onDismissAnomaly(card.alert_id)}
        />
      );
    }
    case 'expiry_special':
      return <ExpirySpecialCard card={card} variant="detail" onDecided={onRefresh} />;
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────

function groupCards(
  cards: ActionCard[],
  dismissedIds: Set<string>,
): Record<ActionCard['card_type'], ActionCard[]> {
  const result: Record<ActionCard['card_type'], ActionCard[]> = {
    low_stock: [],
    po_approval: [],
    revenue_anomaly: [],
    expiry_special: [],
  };

  for (const card of cards) {
    if (card.card_type === 'revenue_anomaly') {
      // Skip dismissed
      if (dismissedIds.has(card.alert_id)) continue;
      // Filter out cards older than 7 days
      const age = Date.now() - new Date(card.created_at).getTime();
      if (age > FILTER_THRESHOLD_MS) continue;
    }
    result[card.card_type].push(card);
  }

  return result;
}

function isStaleAnomaly(createdAt: string): boolean {
  if (!createdAt) return false;
  return Date.now() - new Date(createdAt).getTime() > STALE_THRESHOLD_MS;
}

function cardTitle(card: ActionCard): string {
  switch (card.card_type) {
    case 'low_stock':       return card.material_name;
    case 'po_approval':     return card.list_id;
    case 'revenue_anomaly': return card.message || 'Revenue alert';
    case 'expiry_special':  return card.material_name;
  }
}

function modalTitle(card: ActionCard): string {
  switch (card.card_type) {
    case 'low_stock':       return 'Stock Detail';
    case 'po_approval':     return 'Review Purchase Order';
    case 'revenue_anomaly': return 'Revenue Alert';
    case 'expiry_special':  return "Today's Special";
  }
}
