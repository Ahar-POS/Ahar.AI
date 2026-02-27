/**
 * OrderCard component.
 * 
 * Displays a single order with items, wait time, and action buttons for kitchen view.
 */

import { Order, OrderStatus, ORDER_STATUS_LABELS } from '../types/orders';
import './OrderCard.css';

interface OrderCardProps {
  order: Order;
  onStartCooking?: (orderId: string) => void;
  onMarkComplete?: (orderId: string) => void;
  onMoveToWaiting?: (orderId: string) => void;
  isProcessing?: boolean;
}

/**
 * Calculate wait time in minutes from sent_to_kitchen_at timestamp.
 */
function calculateWaitTime(sentToKitchenAt?: string): number | null {
  if (!sentToKitchenAt) return null;

  const sentTime = new Date(sentToKitchenAt).getTime();
  const now = Date.now();
  const diffMs = now - sentTime;
  const diffMinutes = Math.floor(diffMs / (1000 * 60));

  return diffMinutes;
}

/**
 * Format wait time for display.
 */
function formatWaitTime(minutes: number | null): string {
  if (minutes === null) return 'N/A';
  return `${minutes}m`;
}

/**
 * Get table display name from order.
 * 
 * @param order - Order object with table information
 * @returns Formatted table display string or 'Takeaway'
 */
function getTableDisplayName(order: Order): string {
  if (!order.table_id) {
    return 'Takeaway';
  }

  if (order.table_number && order.table_location) {
    return `Table ${order.table_number} - ${order.table_location}`;
  }

  if (order.table_number) {
    return `Table ${order.table_number}`;
  }

  // Fallback to table_id if number/location not available
  return `Table ${order.table_id}`;
}

/**
 * Order card component for kitchen view.
 */
export default function OrderCard({
  order,
  onStartCooking,
  onMarkComplete,
  onMoveToWaiting,
  isProcessing = false,
}: OrderCardProps) {
  const waitTime = calculateWaitTime(order.sent_to_kitchen_at);
  const isWaiting = order.status === OrderStatus.SENT_TO_KITCHEN;
  const isInProgress = order.status === OrderStatus.IN_PROGRESS;

  const handleStartCooking = () => {
    if (onStartCooking) {
      onStartCooking(order.id);
    }
  };

  const handleMarkComplete = () => {
    if (onMarkComplete) {
      onMarkComplete(order.id);
    }
  };

  const handleMoveToWaiting = () => {
    if (onMoveToWaiting) {
      onMoveToWaiting(order.id);
    }
  };

  return (
    <div className="order-card">
      {/* Header with table info and status */}
      <div className="order-card-header">
        <div className="order-card-title">
          <h3 className="order-card-table">
            {getTableDisplayName(order)}
          </h3>
          <div className="order-card-meta">
            <span className="order-card-time">
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <circle cx="8" cy="8" r="6" />
                <path d="M8 4v4l3 2" />
              </svg>
              {formatWaitTime(waitTime)}
            </span>
            <span
              className={`order-card-status ${isWaiting ? 'status-waiting' : 'status-in-progress'
                }`}
            >
              {ORDER_STATUS_LABELS[order.status]}
            </span>
          </div>
        </div>
      </div>

      {/* Order items */}
      <div className="order-card-items">
        {order.items.map((item, index) => (
          <div key={`${item.menu_item_id}-${index}`} className="order-card-item">
            <div className="order-card-item-main">
              <span className="order-card-item-quantity">{item.quantity}x</span>
              <span className="order-card-item-name">{item.name_snapshot}</span>
            </div>
            {item.notes && (
              <div className="order-card-item-notes">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zM8 4v4M8 10h.01" />
                </svg>
                {item.notes}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Action buttons */}
      <div className="order-card-actions">
        {isWaiting && onStartCooking && (
          <button
            type="button"
            className="order-card-action-btn order-card-action-primary"
            onClick={handleStartCooking}
            disabled={isProcessing}
          >
            {isProcessing ? 'Processing...' : 'Start Cooking'}
          </button>
        )}

        {isInProgress && (
          <>
            {onMarkComplete && (
              <button
                type="button"
                className="order-card-action-btn order-card-action-primary"
                onClick={handleMarkComplete}
                disabled={isProcessing}
              >
                {isProcessing ? 'Processing...' : 'Mark Complete'}
              </button>
            )}
            {onMoveToWaiting && (
              <button
                type="button"
                className="order-card-action-btn order-card-action-secondary"
                onClick={handleMoveToWaiting}
                disabled={isProcessing}
                aria-label="Move to waiting"
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <path d="M1 4l6 6 6-6" />
                </svg>
                Move to Waiting
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
