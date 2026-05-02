import { useState } from 'react';
import {
  PromotionSuggestionCard as PromotionSuggestionCardData,
  approvePromotionSuggestion,
  rejectPromotionSuggestion,
} from '../../../services/ownerDashboard';
import './PromotionSuggestionCard.css';

interface Props {
  card: PromotionSuggestionCardData;
  variant?: 'compact' | 'detail';
  onDecided?: () => void;
}

export default function PromotionSuggestionCard({ card, variant = 'detail', onDecided }: Props) {
  const [loading, setLoading] = useState(false);
  const [decided, setDecided] = useState(false);

  const handle = async (action: 'approve' | 'reject') => {
    setLoading(true);
    try {
      if (action === 'approve') {
        await approvePromotionSuggestion(card.suggestion_id);
      } else {
        await rejectPromotionSuggestion(card.suggestion_id);
      }
      setDecided(true);
      onDecided?.();
    } catch (err) {
      console.error(`Failed to ${action} promotion suggestion:`, err);
    } finally {
      setLoading(false);
    }
  };

  const promoTypeClass = `promo-type-badge--${card.promo_type.toLowerCase()}`;
  const itemsLabel = card.menu_item_names.join(' + ');

  if (variant === 'compact') {
    return (
      <div className="board-card-compact board-card--info">
        <span className={`promo-type-badge ${promoTypeClass}`}>{card.promo_type.replace('_', ' ')}</span>
        <div className="board-card-name">{itemsLabel}</div>
        <span className="board-card-pill pill--info">{card.discount_pct}% OFF</span>
      </div>
    );
  }

  return (
    <div className="action-card action-card--info">
      <div className="action-card-header">
        <span className={`action-card-badge promo-type-badge ${promoTypeClass}`}>
          {card.promo_type.replace(/_/g, ' ')}
        </span>
        <span className="action-card-type-label">Promotion</span>
      </div>
      <div className="action-card-title">{itemsLabel}</div>
      <div className="action-card-meta">{card.discount_pct}% off today</div>
      <div className="action-card-meta">Confidence: {Math.round(card.confidence * 100)}%</div>
      {card.description && (
        <div className="action-card-suggestion">{card.description}</div>
      )}
      {card.reasoning && (
        <div className="action-card-reasoning">{card.reasoning}</div>
      )}
      {decided ? (
        <div className="action-card-meta">Decision recorded.</div>
      ) : (
        <div className="po-card-actions">
          <button
            className="btn btn-sm btn-success"
            disabled={loading}
            onClick={() => handle('approve')}
          >
            Approve
          </button>
          <button
            className="btn btn-sm btn-outline"
            disabled={loading}
            onClick={() => handle('reject')}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
