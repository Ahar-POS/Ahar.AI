/**
 * OwnerDashboard — three-zone unified owner dashboard.
 *
 * Zone 1 (PulseStrip):  pinned top, polls every 30s.
 * Zone 2 (ActionQueue): scrollable cards, polls every 30s.
 * Zone 3 (Panels):      four tabbed panels, on-demand + manual refresh.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getPulseMetrics,
  getActionQueue,
  PulseMetrics,
  ActionQueueData,
} from '../services/ownerDashboard';

import PulseStrip from './dashboard/PulseStrip';
import ActionQueue from './dashboard/ActionQueue';
import LiveOperationsPanel from './dashboard/LiveOperationsPanel';
import BrandHealthPanel from './dashboard/BrandHealthPanel';
import './OwnerDashboard.css';

const POLL_INTERVAL_MS = 30_000;

const TICKER_MESSAGES = [
  "Revenue Agent: Scanning latest transactions for anomalies...",
  "Inventory Agent: Reconciling batch dispatches against sales...",
  "Menu Agent: Analyzing item popularity for weekend specials...",
  "Forecaster: Factoring in tomorrow's rain for supply adjustment...",
  "Compliance: Verifying staff clock-ins against schedule..."
];

function ActivityTicker() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((prev) => (prev + 1) % TICKER_MESSAGES.length);
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="agent-ticker">
      <div className="agent-ticker-track" style={{ transform: `translateY(-${index * 20}px)` }}>
        {TICKER_MESSAGES.map((msg, i) => (
          <div key={i} className="agent-ticker-item">{msg}</div>
        ))}
      </div>
    </div>
  );
}

export default function OwnerDashboard() {
  // Zone 1+2 state
  const [pulse, setPulse] = useState<PulseMetrics | null>(null);
  const [pulseUpdated, setPulseUpdated] = useState<Date>(new Date());
  const [pulsePeriod, setPulsePeriod] = useState<string>('today');
  const [actionQueue, setActionQueue] = useState<ActionQueueData | null>(null);
  const [zone12Loading, setZone12Loading] = useState(true);
  const [zone12Error, setZone12Error] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Zone 1+2 polling ──────────────────────────────────────────────────────

  const fetchZone12 = useCallback(async () => {
    try {
      const [p, q] = await Promise.all([
        getPulseMetrics(pulsePeriod),
        getActionQueue()
      ]);
      setPulse(p);
      setPulseUpdated(new Date());
      setActionQueue(q);
      setZone12Error(null);
    } catch {
      setZone12Error('Failed to load dashboard data. Retrying…');
    } finally {
      setZone12Loading(false);
    }
  }, [pulsePeriod]);

  useEffect(() => {
    fetchZone12();
    intervalRef.current = setInterval(fetchZone12, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchZone12]);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="owner-dash">
      {/* Header */}
      <div className="owner-dash-header">
        <div className="owner-dash-header-left">
          <h2 className="owner-dash-title">Ahar Intelligence</h2>
          <ActivityTicker />
        </div>
        <div className="owner-dash-header-right">
          <div className="agent-status">
            <div className="pulse-dot" />
            <span>Ahar AI Agents Active</span>
          </div>
        </div>
      </div>

      <div className="owner-dash-content-scroll">
        <div className="owner-dash-active-zones">
          {/* Zone 1: Pulse Strip */}
          <div className="owner-dash-zone1">
            {zone12Loading && !pulse ? (
              <div className="owner-dash-zone1-loading">Loading metrics…</div>
            ) : zone12Error && !pulse ? (
              <div className="owner-dash-zone1-error">{zone12Error}</div>
            ) : pulse ? (
              <PulseStrip
                data={pulse}
                lastUpdated={pulseUpdated}
                period={pulsePeriod}
                onPeriodChange={setPulsePeriod}
              />
            ) : null}
          </div>

          {/* Zone 2: Action Queue */}
          <div className="owner-dash-zone2">
            {actionQueue ? (
              <ActionQueue data={actionQueue} onRefresh={fetchZone12} />
            ) : zone12Loading ? (
              <div className="owner-dash-loading-row"><div className="spinner spinner-sm" /></div>
            ) : null}
          </div>
        </div>

        {/* Zone 3: New Operations & Brand Health */}
        <div className="owner-dash-zone3-redesign">
          <LiveOperationsPanel />
          <BrandHealthPanel />
        </div>
      </div>
    </div>
  );
}

