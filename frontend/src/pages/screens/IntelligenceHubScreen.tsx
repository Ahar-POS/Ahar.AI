/**
 * Intelligence Hub — 2-tab screen: Menu Performance (coming soon) + Agent Bus
 */

import { useState, useMemo, useEffect, useCallback } from 'react';
import './IntelligenceHubScreen.css';

type AgentSource = 'finance' | 'inventory' | 'customer';
type Priority = 'high' | 'medium' | 'low';
type SortBy = 'recent' | 'impact';

interface InsightDetail {
  happening: string;
  why: string;
  actions: string[];
}

interface AgentAction {
  label: string;
  action_type: string;
}

interface AgentInsight {
  id: string;
  agent: AgentSource;
  priority: Priority;
  category: string;
  headline: string;
  summary: string;
  impact_inr: number | null;
  detail: InsightDetail;
  created_at: string;
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

const MOCK_INSIGHTS: AgentInsight[] = [
  {
    id: 'f1', agent: 'finance', priority: 'high', category: 'menu_optimization',
    headline: 'Chicken Wrap losing money',
    summary: 'Margins negative 14 days — ₹8,400/mo at risk',
    impact_inr: 8400,
    detail: {
      happening: 'Chicken Wrap has run negative margins for 14 consecutive days, losing ₹8,400 this month.',
      why: 'Raw chicken breast cost increased 22% since March. Current ₹180 price yields −₹12 per serving.',
      actions: ['Raise price to ₹210 to restore 15% margin', 'Or switch to chicken thigh — saves ₹18/serving'],
    },
    created_at: '2026-04-30T11:00:00',
  },
  {
    id: 'f2', agent: 'finance', priority: 'medium', category: 'cost_control',
    headline: 'Food cost at 38% — above target',
    summary: 'Exceeds 35% threshold, draining ₹5,200/mo',
    impact_inr: 5200,
    detail: {
      happening: 'Food cost % has been above the 35% safe threshold for 3 weeks.',
      why: 'Driven by Paneer Sub and Chicken Wrap COGS increases. Packaging costs also up 8%.',
      actions: ['Review portion sizes for top-3 COGS items', 'Renegotiate packaging supplier contract'],
    },
    created_at: '2026-04-29T23:00:00',
  },
  {
    id: 'f3', agent: 'finance', priority: 'low', category: 'pricing',
    headline: 'Tuesday lunch 30% below average',
    summary: 'Consistent weekly dip — 4th occurrence this month',
    impact_inr: 3100,
    detail: {
      happening: 'Every Tuesday 12–2 PM, revenue is ₹3,100 below the daily average. This has occurred 4 weeks running.',
      why: 'No promotions run on Tuesdays. Lunch combo items underperforming vs Thursday.',
      actions: ['Trial a Tuesday lunch combo at ₹199', 'Promote via WhatsApp broadcast Tuesday morning'],
    },
    created_at: '2026-04-29T12:00:00',
  },
  {
    id: 'i1', agent: 'inventory', priority: 'high', category: 'vendor_intelligence',
    headline: 'Chicken breast prices up 22%',
    summary: 'Highest-spend ingredient — consider alternate vendors',
    impact_inr: 12000,
    detail: {
      happening: 'Chicken breast unit cost has risen from ₹180/kg to ₹220/kg over 30 days — your largest ingredient spend.',
      why: 'Seasonal supply tightness. Your current vendor (Sharma Poultry) has raised prices twice this month.',
      actions: ['Get quotes from 2 alternate vendors', 'Consider 2-week forward contract to lock current price'],
    },
    created_at: '2026-04-30T06:15:00',
  },
  {
    id: 'i2', agent: 'inventory', priority: 'medium', category: 'waste_reduction',
    headline: 'Mint leaves wasted 3 weeks running',
    summary: 'Recurring waste — reduce order quantity',
    impact_inr: 1200,
    detail: {
      happening: 'Mint leaves have appeared in the waste log every week for 3 consecutive weeks.',
      why: 'Current order quantity (500g/week) exceeds usage (320g/week). 36% consistently wasted.',
      actions: ['Reduce weekly order to 350g', 'Or add a mint-forward dish to boost utilisation'],
    },
    created_at: '2026-04-28T06:30:00',
  },
  {
    id: 'c1', agent: 'customer', priority: 'medium', category: 'staffing',
    headline: 'Weekend tables turning 35% slower',
    summary: 'Rising footfall is straining turnaround time',
    impact_inr: 6000,
    detail: {
      happening: 'Average Sat/Sun table turnaround has increased from 42 min to 57 min over the last 3 weekends.',
      why: 'Weekend covers up 28%. Kitchen dispatch is the bottleneck — avg 24 min vs 16 min on weekdays.',
      actions: ['Add 1 kitchen staff on Sat/Sun service', 'Trial pre-prepped weekend menu to cut dispatch time'],
    },
    created_at: '2026-04-30T09:00:00',
  },
  {
    id: 'c2', agent: 'customer', priority: 'low', category: 'operations',
    headline: 'Delivery orders up 40% this month',
    summary: 'Kitchen capacity may be stretched soon',
    impact_inr: null,
    detail: {
      happening: 'Delivery order volume has grown 40% month-over-month — now 35% of total orders.',
      why: 'New Zomato promotion driving volume. Kitchen is coping now but nearing 85% capacity.',
      actions: ['Monitor kitchen capacity daily', 'Consider a delivery-only simplified menu if volume grows'],
    },
    created_at: '2026-04-27T14:00:00',
  },
];

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
  const [activeTab, setActiveTab]           = useState<'performance' | 'agent-bus'>('agent-bus');
  const [insights, setInsights]             = useState<AgentInsight[]>(MOCK_INSIGHTS);
  const [agentFilter, setAgentFilter]       = useState<AgentSource | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<Priority | 'all'>('all');
  const [sortBy, setSortBy]                 = useState<SortBy>('recent');
  const [selected, setSelected]             = useState<AgentInsight | null>(null);
  const [toast, setToast]                   = useState<ToastState | null>(null);
  const [lastRemoved, setLastRemoved]       = useState<AgentInsight | null>(null);

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
    const t = setTimeout(() => { setToast(null); setLastRemoved(null); }, 5000);
    return () => clearTimeout(t);
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
    pushToast(`Action initiated: ${action.label}`, insight);
  }, [pushToast]);

  const handleDismiss = useCallback((insight: AgentInsight) => {
    setInsights(prev => prev.filter(i => i.id !== insight.id));
    setSelected(null);
    pushToast('Card dismissed', insight);
  }, [pushToast]);

  const clearFilters = () => { setAgentFilter('all'); setPriorityFilter('all'); };

  return (
    <div className="ih-screen">
      {/* Tab nav */}
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
                    {a === 'customer' && <span className="ih-mock-tag">mock</span>}
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
            {filtered.length === 0 ? (
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

function InsightCard({ insight, onClick }: { insight: AgentInsight; onClick: () => void }) {
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
