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
import RevenueAnomalyCard from './ActionCards/RevenueAnomalyCard';
import ExpirySpecialCard from './ActionCards/ExpirySpecialCard';
import PromotionSuggestionCard from './ActionCards/PromotionSuggestionCard';
import ShoppingListPanel from './ShoppingListPanel';

const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000;      // 24 h
const FILTER_THRESHOLD_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

interface ColumnConfig {
  key: ActionCard['card_type'];
  label: string;
  emptyLabel: string;
}

function ShoppingIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
      <circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function StarIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function TagIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
      <line x1="7" y1="7" x2="7.01" y2="7" />
    </svg>
  );
}

const COLUMNS: ColumnConfig[] = [
  { key: 'revenue_anomaly',    label: 'Revenue Alerts',   emptyLabel: 'Revenue Agent verified today\'s transactions. All nominal.' },
  { key: 'expiry_special',     label: "Today's Specials", emptyLabel: 'Menu Agent analyzed patterns. No new specials needed.' },
  { key: 'promotion_suggestion', label: 'Promotions',     emptyLabel: 'CX Agent has no new promotion suggestions for today.' },
];

interface Props {
  data: ActionQueueData;
  onRefresh: () => void;
}

export default function ActionQueue({ data, onRefresh }: Props) {
  const [selectedCard, setSelectedCard] = useState<ActionCard | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [shoppingCount, setShoppingCount] = useState(0);

  const handleDismissAnomaly = useCallback((alertId: string) => {
    setDismissedIds((prev) => new Set([...prev, alertId]));
    setSelectedCard(null);
  }, []);

  // Group and filter cards
  const grouped = groupCards(data.cards, dismissedIds);

  return (
    <div className="action-queue">
      <div className="action-queue-content">
        <div className="action-board">
          <div className="board-column">
            <div className="board-column-header">
              <span className="board-column-title">
                <ShoppingIcon />
                Shopping List
              </span>
              {shoppingCount > 0 && (
                <span className="board-column-count">{shoppingCount}</span>
              )}
            </div>
            <div className="board-column-cards">
              <ShoppingListPanel onRefresh={onRefresh} onCountChange={setShoppingCount} />
            </div>
          </div>

          {COLUMNS.map((col) => {
            const cards = grouped[col.key as keyof typeof grouped] ?? [];
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
        <span className="board-column-title">
          {config.key === 'revenue_anomaly' ? <AlertIcon /> :
             config.key === 'promotion_suggestion' ? <TagIcon /> : <StarIcon />}
          {config.label}
        </span>
        {cards.length > 0 && (
          <span className="board-column-count">{cards.length}</span>
        )}
      </div>
      <div className="board-column-cards">
        {cards.length === 0 ? (
          <div className="board-empty-state">
            <div className="board-empty-icon">✓</div>
            <div className="board-empty-text">{config.emptyLabel}</div>
          </div>
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
    case 'revenue_anomaly': {
      const isStale = isStaleAnomaly(card.created_at);
      return <RevenueAnomalyCard card={card} variant="compact" isStale={isStale} />;
    }
    case 'expiry_special':
      return <ExpirySpecialCard card={card} variant="compact" />;
    case 'promotion_suggestion':
      return <PromotionSuggestionCard card={card} variant="compact" />;
    default:
      return null;
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
    case 'promotion_suggestion':
      return <PromotionSuggestionCard card={card} variant="detail" onDecided={onRefresh} />;
    default:
      return null;
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────

function groupCards(
  cards: ActionCard[],
  dismissedIds: Set<string>,
): Record<'revenue_anomaly' | 'expiry_special' | 'promotion_suggestion', ActionCard[]> {
  const result: Record<'revenue_anomaly' | 'expiry_special' | 'promotion_suggestion', ActionCard[]> = {
    revenue_anomaly: [],
    expiry_special: [],
    promotion_suggestion: [],
  };

  for (const card of cards) {
    if (card.card_type === 'po_approval') continue;
    if (card.card_type === 'low_stock') continue; // explicitly removed from dashboard

    if (card.card_type === 'revenue_anomaly') {
      if (dismissedIds.has(card.alert_id)) continue;
      const age = Date.now() - new Date(card.created_at).getTime();
      if (age > FILTER_THRESHOLD_MS) continue;
      result.revenue_anomaly.push(card);
    }

    if (card.card_type === 'expiry_special') {
      result.expiry_special.push(card);
    }

    if (card.card_type === 'promotion_suggestion') {
      result.promotion_suggestion.push(card);
    }
  }

  return result;
}

function isStaleAnomaly(createdAt: string): boolean {
  if (!createdAt) return false;
  return Date.now() - new Date(createdAt).getTime() > STALE_THRESHOLD_MS;
}

function cardTitle(card: ActionCard): string {
  switch (card.card_type) {
    case 'low_stock':            return card.material_name;
    case 'revenue_anomaly':      return card.message || 'Revenue alert';
    case 'expiry_special':       return card.material_name;
    case 'promotion_suggestion': return card.menu_item_names.join(' + ') || 'Promotion';
    default:                     return '';
  }
}

function modalTitle(card: ActionCard): string {
  switch (card.card_type) {
    case 'low_stock':            return 'Stock Detail';
    case 'revenue_anomaly':      return 'Revenue Alert';
    case 'expiry_special':       return "Today's Special";
    case 'promotion_suggestion': return 'Promotion Suggestion';
    default:                     return '';
  }
}
