/**
 * Intelligence Hub — Minimalistic design with horizontal scrolling cards
 */

import { useEffect, useState, useCallback } from 'react';
import { insightsService, InsightsResponse, Issue, TokenUsage } from '../../services/insightsService';
import {
  triggerFinancialAgent,
  triggerInventoryAgent,
  triggerDemandForecaster,
  triggerOperationsAnalysis,
} from '../../services/agents';
import AharIcon from '../../components/AharIcon';
import './IntelligenceHubScreen.css';

interface AgentDef {
  id: string;
  label: string;
  trigger: () => Promise<unknown>;
}

const AGENTS: AgentDef[] = [
  { id: 'financial', label: 'Financial Analysis', trigger: triggerFinancialAgent },
  { id: 'inventory', label: 'Inventory Analysis', trigger: triggerInventoryAgent },
  { id: 'demand', label: 'Demand Forecasting', trigger: triggerDemandForecaster },
  { id: 'operations', label: 'Operations Analysis', trigger: triggerOperationsAnalysis },
];

const CATEGORY_LABELS: Record<string, string> = {
  financial: 'Financial Issues',
  inventory: 'Inventory Issues',
  operational: 'Operational Issues',
};

const CATEGORY_ORDER = ['financial', 'inventory', 'operational'];

export default function IntelligenceHubScreen() {
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningAgent, setRunningAgent] = useState<string | null>(null);
  const [lastRuns, setLastRuns] = useState<Record<string, string>>({});
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);

  const loadInsights = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const now = new Date();
      const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      const response = await insightsService.generateInsights({
        start_date: thirtyDaysAgo.toISOString().split('T')[0],
        end_date: now.toISOString().split('T')[0],
        scope: ['financial', 'inventory', 'operational'],
      });
      setInsights(response.data.insights);
      setUsage(response.data.usage ?? null);
    } catch {
      setError('Failed to load insights. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInsights();
  }, [loadInsights]);

  const handleTriggerAgent = async (agent: AgentDef) => {
    if (runningAgent) return;
    setRunningAgent(agent.id);
    try {
      await agent.trigger();
      setLastRuns((prev) => ({ ...prev, [agent.id]: new Date().toLocaleTimeString() }));
      // Refresh insights after agent completes
      await loadInsights();
    } catch {
      // Silently handle
    } finally {
      setRunningAgent(null);
    }
  };

  // Group issues by category
  const groupedIssues: Record<string, Issue[]> = {};
  if (insights?.critical_issues) {
    for (const issue of insights.critical_issues) {
      const cat = issue.category.toLowerCase();
      if (!groupedIssues[cat]) groupedIssues[cat] = [];
      groupedIssues[cat].push(issue);
    }
  }

  // Compute savings breakdown
  const savingsByCategory: Record<string, number> = {};
  if (insights?.critical_issues) {
    for (const issue of insights.critical_issues) {
      const cat = issue.category.toLowerCase();
      savingsByCategory[cat] = (savingsByCategory[cat] ?? 0) + (issue.estimated_savings ?? 0);
    }
  }

  return (
    <div className="intel-hub">
      {/* Left sidebar */}
      <aside className="intel-sidebar">
        <div className="intel-sidebar-brand">
          <AharIcon size={24} className="intel-sparkle" />
          <span className="intel-sidebar-brand-text">Intelligence</span>
        </div>

        <div className="intel-sidebar-agents">
          {AGENTS.map((agent) => (
            <button
              key={agent.id}
              type="button"
              className={`intel-agent-btn${runningAgent === agent.id ? ' intel-agent-btn--running' : ''}`}
              onClick={() => handleTriggerAgent(agent)}
              disabled={runningAgent !== null}
              title={agent.label}
            >
              <span className="intel-agent-btn-label">{agent.label}</span>
              {runningAgent === agent.id && (
                <span className="intel-agent-btn-status">●</span>
              )}
            </button>
          ))}
        </div>

        {/* Token usage in sidebar */}
        {insights && (
          <div className="intel-sidebar-footer">
            <div className="intel-sidebar-usage">
              {usage ? (
                <>
                  <span className="intel-sidebar-usage-label">Tokens</span>
                  <span className="intel-sidebar-usage-value">
                    {(usage.input_tokens + usage.output_tokens).toLocaleString()}
                  </span>
                </>
              ) : (
                <span className="intel-sidebar-usage-cache">⚡ Cached</span>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* Right content */}
      <div className="intel-content">
        {loading ? (
          <div className="intel-loader">
            <div className="spinner spinner-lg" />
            <p>Analyzing your restaurant data...</p>
          </div>
        ) : error ? (
          <div className="intel-error">
            <p>{error}</p>
            <button type="button" className="btn btn-primary btn-sm" onClick={loadInsights}>
              Retry
            </button>
          </div>
        ) : insights ? (
          <>
            {/* Compact header with savings */}
            <div className="intel-header">
              <div className="intel-header-savings">
                <span className="intel-header-label">Monthly Savings Potential</span>
                <span className="intel-header-value">
                  ₹{(insights.estimated_monthly_savings ?? 0).toLocaleString()}
                </span>
              </div>
              <div className="intel-header-breakdown">
                {CATEGORY_ORDER.map((cat) => (
                  <div key={cat} className="intel-header-stat">
                    <span className="intel-header-stat-value">
                      ₹{(savingsByCategory[cat] ?? 0).toLocaleString()}
                    </span>
                    <span className="intel-header-stat-label">
                      {cat}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* All issues in one unified grid */}
            <div className="intel-issues-container">
              {CATEGORY_ORDER.map((cat) => {
                const issues = groupedIssues[cat] ?? [];
                if (issues.length === 0) return null;

                return issues.slice(0, 6).map((issue) => (
                  <IssueCard
                    key={issue.id}
                    issue={issue}
                    onReview={() => setSelectedIssue(issue)}
                  />
                ));
              })}
            </div>
          </>
        ) : null}
      </div>

      {/* Modal for Issue Details */}
      {selectedIssue && (
        <div className="intel-modal-overlay" onClick={() => setSelectedIssue(null)}>
          <div className="intel-modal" onClick={e => e.stopPropagation()}>
            <div className="intel-modal-header">
              <h3 className="intel-modal-title">{selectedIssue.title}</h3>
              <p className="intel-modal-impact">Estimated Impact: ₹{selectedIssue.estimated_savings?.toLocaleString() ?? 0} / month</p>
            </div>

            <div className="intel-modal-body">
              <div className="intel-modal-section">
                <h4>Description</h4>
                <p>{selectedIssue.impact}</p>
              </div>

              <div className="intel-modal-section">
                <h4>Recommended Action</h4>
                <p>{selectedIssue.recommendation}</p>
              </div>
            </div>

            <div className="intel-modal-footer">
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setSelectedIssue(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary intel-modal-approve"
                onClick={() => {
                  alert(`Fix applied for: ${selectedIssue.title}`);
                  setSelectedIssue(null);
                }}
              >
                Approve & Execute Action
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function IssueCard({ issue, onReview }: { issue: Issue; onReview: () => void }) {
  const priorityClass = issue.priority === 'high' ? 'intel-card--high'
    : issue.priority === 'medium' ? 'intel-card--medium'
      : 'intel-card--low';

  const categoryConfig = issue.category === 'financial'
    ? { emoji: '📈', name: 'Revenue Growth', color: '#10b981' }
    : issue.category === 'inventory'
      ? { emoji: '📦', name: 'Inventory', color: '#f59e0b' }
      : { emoji: '⚙️', name: 'Operations', color: '#3b82f6' };

  // Derive confidence and effort from priority
  const confidenceMap = { high: '85%', medium: '70%', low: '55%' };
  const effortMap = { high: 'low effort', medium: 'medium effort', low: 'high effort' };
  const confidence = confidenceMap[issue.priority as keyof typeof confidenceMap] || '70%';
  const effort = effortMap[issue.priority as keyof typeof effortMap] || 'medium effort';

  // Calculate min/max range (±30% of estimated savings)
  const minSavings = Math.round(issue.estimated_savings * 0.7);
  const maxSavings = Math.round(issue.estimated_savings * 1.3);

  return (
    <div className={`intel-card ${priorityClass}`} onClick={onReview}>
      <div className="intel-card-header-badges">
        <span className="intel-card-category-badge" style={{ backgroundColor: `${categoryConfig.color}15`, color: categoryConfig.color }}>
          {categoryConfig.emoji} {categoryConfig.name}
        </span>
        <div className="intel-card-meta-badges">
          <span className="intel-card-confidence-badge">{confidence} confidence</span>
          <span className="intel-card-effort-badge">{effort}</span>
        </div>
      </div>

      <h3 className="intel-card-title">{issue.title}</h3>

      <div className="intel-card-impact-section">
        <span className="intel-card-impact-label">Expected Impact:</span>
        <div className="intel-card-impact-value">
          ₹{issue.estimated_savings.toLocaleString()}<span className="intel-card-impact-period">/month</span>
        </div>
        <span className="intel-card-impact-range">
          (₹{minSavings.toLocaleString()} – ₹{maxSavings.toLocaleString()})
        </span>
      </div>
    </div>
  );
}

