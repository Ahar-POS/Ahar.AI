import { LowStockCard as LowStockCardData } from '../../../services/ownerDashboard';

interface Props {
  card: LowStockCardData;
  variant?: 'compact' | 'detail';
}

export default function LowStockCard({ card, variant = 'detail' }: Props) {
  const isCritical = card.severity === 'critical';
  const severityLabel = isCritical ? 'Critical' : 'Low';
  const severityClass = isCritical ? 'critical' : 'warning';

  if (variant === 'compact') {
    return (
      <div className={`board-card-compact board-card--${severityClass}`}>
        <div className="board-card-name">{card.material_name}</div>
        <span className={`board-card-pill pill--${severityClass}`}>{severityLabel}</span>
      </div>
    );
  }

  return (
    <div className={`action-card action-card--${severityClass}`}>
      <div className="action-card-header">
        <span className={`action-card-badge badge--${severityClass}`}>
          {isCritical ? 'Out of stock' : 'Low stock'}
        </span>
        <span className="action-card-type-label">Inventory</span>
      </div>
      <div className="action-card-title">{card.material_name}</div>
      <div className="action-card-meta">
        {isCritical
          ? `Stock: 0 ${card.unit} — reorder at ${card.reorder_level} ${card.unit}`
          : `${card.current_stock} ${card.unit} left — reorder level: ${card.reorder_level} ${card.unit}`}
      </div>
    </div>
  );
}
