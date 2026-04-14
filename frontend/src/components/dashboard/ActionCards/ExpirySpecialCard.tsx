import { useState } from 'react';
import {
  ExpirySpecialCard as ExpirySpecialCardData,
  approveExpirySpecial,
  rejectExpirySpecial,
} from '../../../services/ownerDashboard';

interface Props {
  card: ExpirySpecialCardData;
  variant?: 'compact' | 'detail';
  onDecided?: () => void;
}

export default function ExpirySpecialCard({ card, variant = 'detail', onDecided }: Props) {
  const [loading, setLoading] = useState(false);
  const [decided, setDecided] = useState(false);

  const handle = async (action: 'approve' | 'reject') => {
    setLoading(true);
    try {
      if (action === 'approve') {
        await approveExpirySpecial(card.special_id);
      } else {
        await rejectExpirySpecial(card.special_id);
      }
      setDecided(true);
      onDecided?.();
    } catch (err) {
      console.error(`Failed to ${action} expiry special:`, err);
    } finally {
      setLoading(false);
    }
  };

  const expiryLabel = card.expiry_date
    ? formatExpiry(card.expiry_date)
    : 'expires soon';

  if (variant === 'compact') {
    return (
      <div className="board-card-compact board-card--info">
        <div className="board-card-name">{card.material_name}</div>
        <span className="board-card-pill pill--info">{expiryLabel}</span>
      </div>
    );
  }

  return (
    <div className="action-card action-card--info">
      <div className="action-card-header">
        <span className="action-card-badge badge--info">Today's special</span>
        <span className="action-card-type-label">Expiry-based</span>
      </div>
      <div className="action-card-title">{card.material_name}</div>
      <div className="action-card-meta">Expires {card.expiry_date ?? 'soon'}</div>
      {card.suggestion && (
        <div className="action-card-suggestion">{card.suggestion}</div>
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

function formatExpiry(dateStr: string): string {
  if (!dateStr) return 'expires soon';
  const expiry = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.ceil((expiry.getTime() - now.getTime()) / 86400000);
  if (diffDays <= 0) return 'expires today';
  if (diffDays === 1) return 'expires tomorrow';
  return `expires in ${diffDays}d`;
}
