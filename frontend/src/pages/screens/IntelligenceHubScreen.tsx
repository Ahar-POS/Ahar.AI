/**
 * Intelligence Hub — 20/80 split with black sidebar + insights content.
 */

import { useEffect, useState, useCallback } from 'react';
import { insightsService, InsightsResponse, Issue } from '../../services/insightsService';
import {
  triggerFinancialAgent,
  triggerInventoryAgent,
  triggerDemandForecaster,
  triggerOperationsAnalysis,
} from '../../services/agents';
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningAgent, setRunningAgent] = useState<string | null>(null);
  const [lastRuns, setLastRuns] = useState<Record<string, string>>({});

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
          <AharSparkle />
          <span className="intel-sidebar-brand-text">Ahar</span>
        </div>

        <div className="intel-sidebar-agents">
          {AGENTS.map((agent) => (
            <button
              key={agent.id}
              type="button"
              className={`intel-agent-btn${runningAgent === agent.id ? ' intel-agent-btn--running' : ''}`}
              onClick={() => handleTriggerAgent(agent)}
              disabled={runningAgent !== null}
            >
              <span className="intel-agent-btn-label">{agent.label}</span>
              {runningAgent === agent.id && (
                <span className="intel-agent-btn-status">Running...</span>
              )}
              {lastRuns[agent.id] && runningAgent !== agent.id && (
                <span className="intel-agent-btn-time">Last: {lastRuns[agent.id]}</span>
              )}
            </button>
          ))}
        </div>
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
            {/* Hero savings */}
            <div className="intel-hero">
              <div className="intel-hero-main">
                <div className="intel-hero-label">Estimated Monthly Savings</div>
                <div className="intel-hero-value">
                  ₹{(insights.estimated_monthly_savings ?? 0).toLocaleString()}
                </div>
              </div>
              <div className="intel-hero-breakdown">
                {CATEGORY_ORDER.map((cat) => (
                  <div key={cat} className="intel-hero-item">
                    <span className="intel-hero-item-label">
                      {cat.charAt(0).toUpperCase() + cat.slice(1)}
                    </span>
                    <span className="intel-hero-item-value">
                      ₹{(savingsByCategory[cat] ?? 0).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Issue sections */}
            <div className="intel-sections">
              {CATEGORY_ORDER.map((cat) => {
                const issues = groupedIssues[cat] ?? [];
                if (issues.length === 0) return null;
                const visible = issues.slice(0, 3);
                const remaining = issues.length - 3;

                return (
                  <div key={cat} className="intel-section">
                    <div className="intel-section-header">
                      <h3 className="intel-section-title">
                        {CATEGORY_LABELS[cat] ?? cat}
                      </h3>
                      <span className="intel-section-count">{issues.length} issues</span>
                    </div>
                    <div className="intel-cards">
                      {visible.map((issue) => (
                        <IssueCard key={issue.id} issue={issue} />
                      ))}
                    </div>
                    {remaining > 0 && (
                      <button type="button" className="intel-see-all">
                        See all {issues.length} {cat} issues
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

function IssueCard({ issue }: { issue: Issue }) {
  const priorityClass = issue.priority === 'high' ? 'intel-card--high'
    : issue.priority === 'medium' ? 'intel-card--medium'
    : 'intel-card--low';

  return (
    <div className={`intel-card ${priorityClass}`}>
      <div className="intel-card-header">
        <span className="intel-card-title">{issue.title}</span>
        {issue.estimated_savings > 0 && (
          <span className="intel-card-savings">₹{issue.estimated_savings.toLocaleString()}</span>
        )}
      </div>
      <p className="intel-card-impact">{issue.impact}</p>
      <div className="intel-card-footer">
        <span className="intel-card-rec">{issue.recommendation}</span>
        <button type="button" className="intel-card-fix">Fix this</button>
      </div>
    </div>
  );
}

function AharSparkle() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" className="intel-sparkle">
      <path
        d="M14 2L16.5 10.5L25 14L16.5 17.5L14 26L11.5 17.5L3 14L11.5 10.5L14 2Z"
        fill="#ffffff"
        opacity="0.9"
      />
      <path
        d="M22 4L23 7L26 8L23 9L22 12L21 9L18 8L21 7L22 4Z"
        fill="#ffffff"
        opacity="0.5"
      />
    </svg>
  );
}
