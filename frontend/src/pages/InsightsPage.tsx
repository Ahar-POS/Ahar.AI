import React, { useState } from 'react';
import { insightsService, type InsightsResponse, type TokenUsage } from '../services/insightsService';
import IssueCard from '../components/IssueCard';
import './InsightsPage.css';

type ScopeKey = 'financial' | 'inventory' | 'operational';

const SCOPE_OPTIONS: { key: ScopeKey; label: string; icon: string }[] = [
  { key: 'financial', label: 'Financial', icon: '💰' },
  { key: 'inventory', label: 'Inventory', icon: '📦' },
  { key: 'operational', label: 'Operational', icon: '⚙️' },
];

export default function InsightsPage() {
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeQuickRange, setActiveQuickRange] = useState<number | null>(30);

  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [scope, setScope] = useState<Record<ScopeKey, boolean>>({
    financial: true,
    inventory: true,
    operational: true,
  });

  /** Token usage from last API call (null when result was from cache) */
  const [usage, setUsage] = useState<TokenUsage | null>(null);

  React.useEffect(() => {
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);
    setEndDate(today.toISOString().split('T')[0]);
    setStartDate(thirtyDaysAgo.toISOString().split('T')[0]);
  }, []);

  const handleScopeToggle = (key: ScopeKey) => {
    setScope((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const setQuickRange = (days: number) => {
    const today = new Date();
    const pastDate = new Date(today);
    pastDate.setDate(today.getDate() - days);
    setEndDate(today.toISOString().split('T')[0]);
    setStartDate(pastDate.toISOString().split('T')[0]);
    setActiveQuickRange(days);
  };

  const handleDateChange = (setter: React.Dispatch<React.SetStateAction<string>>) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setter(e.target.value);
      setActiveQuickRange(null);
    };

  const handleGenerate = async () => {
    if (!startDate || !endDate) {
      setError('Please select both start and end dates');
      return;
    }

    const selectedScope = (Object.entries(scope) as [ScopeKey, boolean][])
      .filter(([, isSelected]) => isSelected)
      .map(([key]) => key);

    if (selectedScope.length === 0) {
      setError('Please select at least one analysis scope');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const result = await insightsService.generateInsights({
        start_date: startDate,
        end_date: endDate,
        scope: selectedScope,
      });

      if (result.success) {
        setInsights(result.data.insights);
        setUsage(result.data.usage ?? null);
      } else {
        setError('Failed to generate insights');
      }
    } catch (err: unknown) {
      console.error('Insights generation error:', err);
      const message =
        err instanceof Error
          ? err.message
          : (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data
              ?.error?.message ?? 'Failed to generate insights';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (paise: number) =>
    `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

  return (
    <div className="home-panel">
      {/* Controls Card */}
      <div className="insights-controls-card">
        <div className="insights-page-header">
          <h2 className="insights-page-title">AI-Powered Restaurant Insights</h2>
          <p className="insights-page-description">
            Comprehensive analysis of financial losses, inventory waste, and operational
            inefficiencies
          </p>
        </div>

        {/* Date Range */}
        <div className="insights-section">
          <span className="insights-section-label">Date Range</span>
          <div className="insights-date-row">
            <input
              type="date"
              value={startDate}
              onChange={handleDateChange(setStartDate)}
              className="form-input"
              aria-label="Start date"
            />
            <span className="insights-date-separator">to</span>
            <input
              type="date"
              value={endDate}
              onChange={handleDateChange(setEndDate)}
              className="form-input"
              aria-label="End date"
            />
            <div className="insights-quick-ranges">
              {[7, 30, 90].map((days) => (
                <button
                  key={days}
                  type="button"
                  className={`insights-quick-btn${activeQuickRange === days ? ' active' : ''}`}
                  onClick={() => setQuickRange(days)}
                >
                  {days}d
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Analysis Scope */}
        <div className="insights-section">
          <span className="insights-section-label">Analysis Scope</span>
          <div className="insights-scope-grid">
            {SCOPE_OPTIONS.map(({ key, label, icon }) => (
              <label
                key={key}
                className={`insights-scope-item${scope[key] ? ' selected' : ''}`}
                aria-pressed={scope[key]}
              >
                <input
                  type="checkbox"
                  checked={scope[key]}
                  onChange={() => handleScopeToggle(key)}
                />
                <span className="insights-scope-checkmark" aria-hidden="true" />
                <span className="insights-scope-icon" aria-hidden="true">{icon}</span>
                <span className="insights-scope-label">{label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Generate */}
        <div className="insights-generate-section">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={loading}
            className="btn btn-primary insights-generate-btn"
          >
            {loading ? 'Analyzing...' : 'Generate Insights'}
          </button>
          {!loading && (
            <span className="insights-generate-hint">
              Analysis may take 30–60 seconds
            </span>
          )}
        </div>

        {/* Token usage: show in controls card when we have insights so it's always visible */}
        {insights && (
          <div className="insights-token-usage" title={usage ? 'API token usage for this run' : 'Retrieved from cache'}>
            {usage ? (
              <>
                <span className="insights-token-usage-label">Tokens:</span>
                <span className="insights-token-usage-value">
                  {(usage.input_tokens + usage.output_tokens).toLocaleString()} total
                </span>
                <span className="insights-token-usage-detail">
                  ({usage.input_tokens.toLocaleString()}↑ input · {usage.output_tokens.toLocaleString()}↓ output)
                </span>
              </>
            ) : (
              <span className="insights-token-usage-cache">From cache (no API tokens used)</span>
            )}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="insights-error" role="alert">
          <span className="insights-error-icon">⚠️</span>
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="insights-loading" role="status" aria-live="polite">
          <div className="insights-loading-spinner" aria-hidden="true" />
          <p className="insights-loading-title">Analyzing Restaurant Data…</p>
          <p className="insights-loading-subtitle">
            AI is performing a comprehensive root-cause analysis across your selected period.
          </p>
        </div>
      )}

      {/* Results */}
      {insights && !loading && (
        <div className="insights-results">
          {/* Savings Banner */}
          <div className="insights-savings-banner">
            <div className="insights-savings-left">
              <span className="insights-savings-label">Potential Monthly Savings</span>
              <span className="insights-savings-amount">
                {formatCurrency(insights.estimated_monthly_savings)}
              </span>
              <span className="insights-savings-footnote">
                Estimated recoverable losses
              </span>
            </div>
            <div className="insights-savings-right">
              <span className="insights-savings-issues-count">
                {insights.critical_issues.length}
              </span>
              <span className="insights-savings-issues-label">
                {insights.critical_issues.length === 1 ? 'Issue' : 'Issues'} identified
              </span>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="insights-stats-grid">
            <div className="insights-stat-card insights-stat-card--revenue">
              <p className="insights-stat-label">Total Revenue</p>
              <p className="insights-stat-value">
                {formatCurrency(insights.financial_summary.total_revenue)}
              </p>
            </div>

            <div className="insights-stat-card insights-stat-card--loss">
              <p className="insights-stat-label">Revenue Loss</p>
              <p className="insights-stat-value insights-stat-value--loss">
                {formatCurrency(insights.financial_summary.revenue_loss)}
              </p>
            </div>

            <div className="insights-stat-card insights-stat-card--inventory">
              <p className="insights-stat-label">Low Stock Items</p>
              <p className="insights-stat-value">
                {insights.inventory_summary.low_stock_items}
              </p>
            </div>

            <div className="insights-stat-card insights-stat-card--operational">
              <p className="insights-stat-label">Orders Completed</p>
              <p className="insights-stat-value">
                {insights.operational_summary.orders_completed}
              </p>
            </div>
          </div>

          {/* Critical Issues */}
          <div className="insights-issues-section">
            <div className="insights-issues-header">
              <h3 className="insights-issues-title">Critical Issues</h3>
              <span className="insights-issues-count-badge">
                {insights.critical_issues.length}
              </span>
            </div>

            {insights.critical_issues.length === 0 ? (
              <div className="insights-success-empty" role="status">
                <span className="insights-success-icon">✅</span>
                <p className="insights-success-title">No Critical Issues Found</p>
                <p className="insights-success-description">
                  Your restaurant operations are running smoothly for this period.
                </p>
              </div>
            ) : (
              <div className="insights-issues-grid">
                {insights.critical_issues.map((issue) => (
                  <IssueCard key={issue.id} issue={issue} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!insights && !loading && (
        <div className="insights-empty-state" role="status">
          <span className="insights-empty-icon">📊</span>
          <p className="insights-empty-title">No Insights Generated Yet</p>
          <p className="insights-empty-description">
            Select a date range and click "Generate Insights" to analyse your restaurant
            operations
          </p>
        </div>
      )}
    </div>
  );
}
