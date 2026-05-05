/**
 * Intelligence Hub — 2-tab screen: Menu Performance (coming soon) + Agent Bus
 */

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import './IntelligenceHubScreen.css';
import { getAgentFeed, dismissInsight, AgentInsight, AgentSource, Priority } from '../../services/agentFeedService';
import { triggerFinancialAgent, triggerCustomerExperienceAgent } from '../../services/agents';

type SortBy = 'recent' | 'impact';

interface AgentAction {
  label: string;
  action_type: string;
}

interface ToastState {
  message: string;
  undoInsight: AgentInsight | null;
}

const AGENT_CONFIG: Record<AgentSource, { label: string; color: string; bg: string }> = {
  finance:   { label: 'Finance',   color: '#2563eb', bg: '#eff6ff' },
  inventory: { label: 'Inventory', color: '#c2410c', bg: '#fff7ed' }, // orange-700 — distinct from medium amber
  customer:  { label: 'Customer',  color: '#16a34a', bg: '#f0fdf4' },
};

const PRIORITY_CONFIG: Record<Priority, { label: string; color: string }> = {
  high:   { label: 'HIGH', color: '#dc2626' },
  medium: { label: 'MED',  color: '#d97706' },
  low:    { label: 'LOW',  color: '#6b7280' },
};

const DESTRUCTIVE_ACTIONS = new Set(['remove_menu_item', 'reduce_order_qty']);

const CATEGORY_ACTIONS: Record<string, AgentAction[]> = {
  menu_optimization:  [{ label: 'Remove Menu Item',     action_type: 'remove_menu_item' }, { label: 'Find Alternatives',       action_type: 'find_alternatives' }],
  vendor_intelligence:[{ label: 'Search for Vendors',    action_type: 'search_vendors' },   { label: 'Get Price Quotes',        action_type: 'get_quotes' }],
  waste_reduction:    [{ label: 'Reduce Order Quantity', action_type: 'reduce_order_qty' }, { label: 'Create a New Dish',       action_type: 'create_dish' }],
  staffing:           [{ label: 'Schedule Extra Staff',  action_type: 'schedule_staff' },   { label: 'Optimise Menu for Speed', action_type: 'optimise_menu' }],
  pricing:            [{ label: 'Run a Promotion',       action_type: 'run_promotion' },    { label: 'Adjust Price',            action_type: 'adjust_price' }],
  cost_control:       [{ label: 'Review Portions',       action_type: 'review_portions' },  { label: 'Contact Supplier',        action_type: 'contact_supplier' }],
  operations:         [{ label: 'Set Capacity Alert',    action_type: 'set_alert' },        { label: 'Simplify Menu',           action_type: 'simplify_menu' }],
};


function relativeTime(iso: string): string {
  const hrs = Math.floor((Date.now() - new Date(iso).getTime()) / 3_600_000);
  if (hrs < 1) return 'Just now';
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function fmtImpact(inr: number | null): string {
  if (inr === null) return '';
  return `₹${inr.toLocaleString('en-IN')}/mo`;
}

// ── Toast with undo ───────────────────────────────────────────────────────────

function Toast({ toast, onUndo, onClose }: {
  toast: ToastState;
  onUndo: (() => void) | null;
  onClose: () => void;
}) {
  return (
    <div className="ih-toast" role="status" aria-live="polite" aria-atomic="true">
      <span className="ih-toast-check">✓</span>
      <span>{toast.message}</span>
      {onUndo && (
        <button type="button" className="ih-toast-undo" onClick={onUndo}>Undo</button>
      )}
      <button type="button" className="ih-toast-close" aria-label="Close notification" onClick={onClose}>×</button>
    </div>
  );
}

// ── Root ─────────────────────────────────────────────────────────────────────

export default function IntelligenceHubScreen() {
  const [, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab]           = useState<'performance' | 'agent-bus'>('agent-bus');
  const [insights, setInsights]             = useState<AgentInsight[]>([]);
  const [loading, setLoading]               = useState(true);
  const [agentRunning, setAgentRunning]     = useState(false);
  const [cxAgentRunning, setCxAgentRunning] = useState(false);
  const [agentFilter, setAgentFilter]       = useState<AgentSource | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<Priority | 'all'>('all');
  const [sortBy, setSortBy]                 = useState<SortBy>('recent');
  const [selected, setSelected]             = useState<AgentInsight | null>(null);
  const [toast, setToast]                   = useState<ToastState | null>(null);
  const [lastRemoved, setLastRemoved]       = useState<AgentInsight | null>(null);
  const toastTimerRef                       = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getAgentFeed()
      .then(data => { if (!cancelled) setInsights(data); })
      .catch(() => { /* degrade silently — empty state shown */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    let list = insights;
    if (agentFilter !== 'all')    list = list.filter(i => i.agent === agentFilter);
    if (priorityFilter !== 'all') list = list.filter(i => i.priority === priorityFilter);
    return [...list].sort(sortBy === 'impact'
      ? (a, b) => (b.impact_inr ?? 0) - (a.impact_inr ?? 0)
      : (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [insights, agentFilter, priorityFilter, sortBy]);

  const pushToast = useCallback((msg: string, removedInsight: AgentInsight | null) => {
    setLastRemoved(removedInsight);
    setToast({ message: msg, undoInsight: removedInsight });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => { setToast(null); setLastRemoved(null); }, 5000);
  }, []);

  const handleUndo = useCallback(() => {
    if (lastRemoved) {
      setInsights(prev => [lastRemoved, ...prev]);
      setLastRemoved(null);
      setToast(null);
    }
  }, [lastRemoved]);

  const handleAction = useCallback((insight: AgentInsight, action: AgentAction) => {
    setInsights(prev => prev.filter(i => i.id !== insight.id));
    setSelected(null);
    dismissInsight(insight.id).catch(() => {/* fire-and-forget */});
    pushToast(`Action initiated: ${action.label}`, insight);
  }, [pushToast]);

  const handleDismiss = useCallback((insight: AgentInsight) => {
    setInsights(prev => prev.filter(i => i.id !== insight.id));
    setSelected(null);
    dismissInsight(insight.id).catch(() => {/* fire-and-forget */});
    pushToast('Card dismissed', insight);
  }, [pushToast]);

  const clearFilters = () => { setAgentFilter('all'); setPriorityFilter('all'); };

  const handleChatAboutThis = useCallback((insight: AgentInsight) => {
    setSearchParams({
      screen: 'command-center',
      insightId: insight.id,
      insightHeadline: insight.headline,
    });
  }, [setSearchParams]);

  const handleRunFinanceAgent = async () => {
    setAgentRunning(true);
    try {
      await triggerFinancialAgent();
      const fresh = await getAgentFeed();
      setInsights(fresh);
    } catch {
      alert('Failed to trigger finance agent. Please try again.');
    } finally {
      setAgentRunning(false);
    }
  };

  const handleRunCxAgent = async () => {
    setCxAgentRunning(true);
    try {
      await triggerCustomerExperienceAgent();
      setTimeout(async () => {
        const fresh = await getAgentFeed();
        setInsights(fresh);
      }, 1000);
    } catch {
      alert('Failed to trigger customer experience agent. Please try again.');
    } finally {
      setCxAgentRunning(false);
    }
  };

  return (
    <div className="ih-screen">
      {/* Tab nav */}
      <div className="ih-tabs-row">
      <div className="ih-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'performance'}
          className={`ih-tab${activeTab === 'performance' ? ' ih-tab--active' : ''}`}
          onClick={() => setActiveTab('performance')}
        >
          Menu Performance
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'agent-bus'}
          className={`ih-tab${activeTab === 'agent-bus' ? ' ih-tab--active' : ''}`}
          onClick={() => setActiveTab('agent-bus')}
        >
          Agent Bus
          {insights.length > 0 && (
            <span className="ih-tab-badge" aria-label={`${insights.length} insights`}>{insights.length}</span>
          )}
        </button>
      </div>
      <button
        type="button"
        className="ih-run-agent-btn"
        onClick={handleRunFinanceAgent}
        disabled={agentRunning}
      >
        {agentRunning ? 'Running…' : 'Run Finance Agent'}
      </button>
      <button
        type="button"
        className="ih-run-agent-btn"
        onClick={handleRunCxAgent}
        disabled={cxAgentRunning}
      >
        {cxAgentRunning ? 'Running…' : 'Run CX Agent'}
      </button>
      </div>

      {/* Panels */}
      {activeTab === 'performance' ? (
        <div className="ih-coming-soon">
          <p className="ih-coming-soon-title">Menu Performance</p>
          <p className="ih-coming-soon-sub">
            Filterable SKU performance table with AI insights per item — coming soon
          </p>
        </div>
      ) : (
        <div className="ih-bus">
          {/* Controls */}
          <div className="ih-controls">
            <div className="ih-agent-filters" role="group" aria-label="Filter by agent">
              {(['all', 'finance', 'inventory', 'customer'] as const).map(a => {
                const isActive = agentFilter === a;
                const cfg = a !== 'all' ? AGENT_CONFIG[a] : null;
                return (
                  <button
                    key={a}
                    type="button"
                    aria-pressed={isActive}
                    className={`ih-filter-pill${isActive ? ' ih-filter-pill--active' : ''}${a === 'all' && isActive ? ' ih-filter-pill--all-active' : ''}`}
                    style={isActive && cfg ? { backgroundColor: cfg.color, color: '#fff', borderColor: cfg.color } : {}}
                    onClick={() => setAgentFilter(a)}
                  >
                    {a === 'all' ? 'All Agents' : cfg!.label}
                  </button>
                );
              })}
            </div>

            <div className="ih-right-controls">
              <div className="ih-priority-filters" role="group" aria-label="Filter by priority">
                {(['all', 'high', 'medium', 'low'] as const).map(p => {
                  const isActive = priorityFilter === p;
                  const cfg = p !== 'all' ? PRIORITY_CONFIG[p] : null;
                  return (
                    <button
                      key={p}
                      type="button"
                      aria-pressed={isActive}
                      className={`ih-filter-pill${isActive ? ' ih-filter-pill--active' : ''}${p === 'all' && isActive ? ' ih-filter-pill--all-active' : ''}`}
                      style={isActive && cfg ? { backgroundColor: cfg.color, color: '#fff', borderColor: cfg.color } : {}}
                      onClick={() => setPriorityFilter(p)}
                    >
                      {p === 'all' ? 'All' : cfg!.label}
                    </button>
                  );
                })}
              </div>
              <select
                className="ih-sort-select"
                value={sortBy}
                aria-label="Sort insights"
                onChange={e => setSortBy(e.target.value as SortBy)}
              >
                <option value="recent">Most Recent</option>
                <option value="impact">Highest Impact</option>
              </select>
            </div>
          </div>

          {/* Feed */}
          <div className="ih-feed" role="list">
            {loading ? (
              <div className="ih-empty">
                <p className="ih-empty-sub">Loading insights…</p>
              </div>
            ) : filtered.length === 0 ? (
              <div className="ih-empty">
                {insights.length === 0 ? (
                  <>
                    <p className="ih-empty-title">All caught up</p>
                    <p className="ih-empty-sub">No active insights right now. Check back tomorrow.</p>
                  </>
                ) : (
                  <>
                    <p className="ih-empty-title">No insights match these filters</p>
                    <button type="button" className="ih-empty-reset" onClick={clearFilters}>
                      Clear filters
                    </button>
                  </>
                )}
              </div>
            ) : (
              filtered.map(insight => (
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  onClick={() => setSelected(insight)}
                  onChat={() => handleChatAboutThis(insight)}
                />
              ))
            )}
          </div>
        </div>
      )}

      {/* Modal */}
      {selected && (
        <InsightModal
          insight={selected}
          onClose={() => setSelected(null)}
          onAction={handleAction}
          onDismiss={handleDismiss}
        />
      )}

      {/* Toast */}
      {toast && (
        <Toast
          toast={toast}
          onUndo={lastRemoved ? handleUndo : null}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}

// ── Compact card ──────────────────────────────────────────────────────────────

function InsightCard({ insight, onClick, onChat }: { insight: AgentInsight; onClick: () => void; onChat: () => void }) {
  const agent    = AGENT_CONFIG[insight.agent];
  const priority = PRIORITY_CONFIG[insight.priority];

  return (
    <div
      className="ih-card"
      style={{ borderLeftColor: agent.color }}
      onClick={onClick}
      role="listitem button"
      tabIndex={0}
      aria-label={`${agent.label} insight: ${insight.headline}`}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onClick())}
    >
      <div className="ih-card-top">
        <span className="ih-card-agent-badge" style={{ backgroundColor: agent.bg, color: agent.color }}>
          {agent.label}
        </span>
        <span className="ih-card-priority" style={{ color: priority.color }}>
          {priority.label}
        </span>
      </div>

      <p className="ih-card-headline">{insight.headline}</p>

      <div className="ih-card-bottom">
        <span className="ih-card-summary">{insight.summary}</span>
        <div className="ih-card-meta">
          {insight.impact_inr !== null && (
            <span className="ih-card-impact">{fmtImpact(insight.impact_inr)}</span>
          )}
          <span className="ih-card-time">{relativeTime(insight.created_at)}</span>
          <button
            type="button"
            className="ih-card-chat-btn"
            onClick={e => { e.stopPropagation(); onChat(); }}
            aria-label="Chat about this insight"
          >
            Chat about this
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Detail modal ──────────────────────────────────────────────────────────────

function InsightModal({
  insight, onClose, onAction, onDismiss,
}: {
  insight: AgentInsight;
  onClose: () => void;
  onAction: (insight: AgentInsight, action: AgentAction) => void;
  onDismiss: (insight: AgentInsight) => void;
}) {
  const agent    = AGENT_CONFIG[insight.agent];
  const priority = PRIORITY_CONFIG[insight.priority];
  const actions  = CATEGORY_ACTIONS[insight.category] ?? [];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="ih-overlay" onClick={onClose}>
      <div
        className="ih-modal"
        style={{ borderTopColor: agent.color }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ih-modal-title"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="ih-modal-header">
          <div className="ih-modal-badges">
            <span className="ih-card-agent-badge" style={{ backgroundColor: agent.bg, color: agent.color }}>
              {agent.label}
            </span>
            <span className="ih-card-priority" style={{ color: priority.color }}>
              {priority.label}
            </span>
            {insight.impact_inr !== null && (
              <span className="ih-modal-impact">{fmtImpact(insight.impact_inr)}</span>
            )}
          </div>
          <button type="button" className="ih-modal-close" aria-label="Close insight" onClick={onClose}>×</button>
        </div>

        <h3 className="ih-modal-title" id="ih-modal-title">{insight.headline}</h3>

        {/* Body */}
        <div className="ih-modal-body">
          <div className="ih-modal-section">
            <p className="ih-modal-section-label">What's happening</p>
            <p className="ih-modal-section-text">{insight.detail.happening}</p>
          </div>
          <div className="ih-modal-section">
            <p className="ih-modal-section-label">Why</p>
            <p className="ih-modal-section-text">{insight.detail.why}</p>
          </div>
          <div className="ih-modal-section">
            <p className="ih-modal-section-label">What to do</p>
            <ul className="ih-modal-todo">
              {insight.detail.actions.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="ih-modal-footer">
          <button type="button" className="ih-btn-dismiss" onClick={() => onDismiss(insight)}>
            Dismiss
          </button>
          {actions.length > 0 && (
            <div className="ih-modal-actions">
              <span className="ih-modal-actions-label">Quick actions</span>
              <div className="ih-modal-action-btns">
                {actions.map(action => (
                  <button
                    key={action.action_type}
                    type="button"
                    className={`ih-btn-action${DESTRUCTIVE_ACTIONS.has(action.action_type) ? ' ih-btn-action--destructive' : ''}`}
                    style={!DESTRUCTIVE_ACTIONS.has(action.action_type) ? { borderColor: agent.color, color: agent.color } : {}}
                    onClick={() => onAction(insight, action)}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
