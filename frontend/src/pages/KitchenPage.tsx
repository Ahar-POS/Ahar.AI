/**
 * KitchenPage component.
 * 
 * Main page for kitchen staff to view and manage orders.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Order } from '../types/orders';
import {
  getKitchenOrders,
  startCookingOrder,
  markOrderComplete,
  moveOrderToWaiting,
} from '../services/orders';
import OrderCard from '../components/OrderCard';
import './KitchenPage.css';

/**
 * Polling interval for kitchen orders (in milliseconds).
 * Can be configured via environment variable VITE_KITCHEN_POLL_INTERVAL_MS.
 * Defaults to 5000ms (5 seconds).
 */
const POLLING_INTERVAL_MS = import.meta.env.VITE_KITCHEN_POLL_INTERVAL_MS
  ? parseInt(import.meta.env.VITE_KITCHEN_POLL_INTERVAL_MS, 10)
  : 5000;

/**
 * Kitchen page component for order management.
 */
export default function KitchenPage() {
  const [waitingOrders, setWaitingOrders] = useState<Order[]>([]);
  const [nextUpOrders, setNextUpOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingOrders, setProcessingOrders] = useState<Set<string>>(new Set());

  /**
   * Load kitchen orders.
   */
  const loadOrders = useCallback(async () => {
    try {
      setError(null);
      const data = await getKitchenOrders();
      setWaitingOrders(data.waiting);
      setNextUpOrders(data.next_up);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load orders');
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Load orders on mount and set up polling.
   */
  useEffect(() => {
    loadOrders();

    // Poll at configured interval
    const interval = setInterval(() => {
      loadOrders();
    }, POLLING_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [loadOrders]);

  /**
   * Handle start cooking.
   */
  const handleStartCooking = async (orderId: string) => {
    try {
      setProcessingOrders(prev => new Set(prev).add(orderId));
      await startCookingOrder(orderId);
      await loadOrders(); // Refresh orders
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start cooking');
    } finally {
      setProcessingOrders(prev => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    }
  };

  /**
   * Handle mark complete.
   */
  const handleMarkComplete = async (orderId: string) => {
    try {
      setProcessingOrders(prev => new Set(prev).add(orderId));
      await markOrderComplete(orderId);
      await loadOrders(); // Refresh orders
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to mark order as complete');
    } finally {
      setProcessingOrders(prev => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    }
  };

  /**
   * Handle move to waiting.
   */
  const handleMoveToWaiting = async (orderId: string) => {
    try {
      setProcessingOrders(prev => new Set(prev).add(orderId));
      await moveOrderToWaiting(orderId);
      await loadOrders(); // Refresh orders
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to move order to waiting');
    } finally {
      setProcessingOrders(prev => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="kitchen-page">
        <div className="kitchen-page-loading">
          <div className="spinner" />
          <p>Loading orders...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="kitchen-page">
      {/* Header */}
      <div className="kitchen-page-header">
        <h1 className="kitchen-page-title">Kitchen View</h1>
      </div>

      {/* Error message */}
      {error && (
        <div className="kitchen-page-error">
          <p>{error}</p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Orders sections */}
      <div className="kitchen-page-content">
        {/* Waiting section */}
        <div className="kitchen-page-section">
          <h2 className="kitchen-page-section-title">
            Waiting ({waitingOrders.length})
          </h2>
          {waitingOrders.length === 0 ? (
            <div className="kitchen-page-empty">
              <p>No orders waiting</p>
            </div>
          ) : (
            <div className="kitchen-page-orders">
              {waitingOrders.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onStartCooking={handleStartCooking}
                  isProcessing={processingOrders.has(order.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Next Up section */}
        <div className="kitchen-page-section">
          <h2 className="kitchen-page-section-title">
            Next Up ({nextUpOrders.length})
          </h2>
          {nextUpOrders.length === 0 ? (
            <div className="kitchen-page-empty">
              <p>No orders in progress</p>
            </div>
          ) : (
            <div className="kitchen-page-orders">
              {nextUpOrders.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onMarkComplete={handleMarkComplete}
                  onMoveToWaiting={handleMoveToWaiting}
                  isProcessing={processingOrders.has(order.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
