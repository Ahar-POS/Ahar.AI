import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { strategicInsightsService, type StrategicInsights, type Opportunity, type Risk, type TokenUsage } from '../services/strategicInsightsService';
import './InsightsPage.css';

const CATEGORY_ICONS: Record<string, string> = {
  revenue_growth: '📈',
  cost_reduction: '💰',
  operational_efficiency: '⚡',
  menu_optimization: '🍽️',
  customer_experience: '😊',
  supply_chain: '🚚',
  financial: '💸',
  operational: '⚙️',
  compliance: '📋',
  market: '🏪',
};

const CATEGORY_COLORS: Record<string, string> = {
  revenue_growth: '#10b981',
  cost_reduction: '#3b82f6',
  operational_efficiency: '#8b5cf6',
  menu_optimization: '#f59e0b',
  customer_experience: '#ec4899',
  supply_chain: '#ef4444',
  financial: '#dc2626',
  operational: '#f97316',
  compliance: '#eab308',
  market: '#6366f1',
};

export default function InsightsPage() {
  // DEBUG: Verify new code is loading
  console.log('🎯 STRATEGIC INSIGHTS UI LOADED - NEW VERSION');

  const [insights, setInsights] = useState<StrategicInsights | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeQuickRange, setActiveQuickRange] = useState<number | null>(30);

  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [compareToPrevious, setCompareToPrevious] = useState(false);

  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [cacheHit, setCacheHit] = useState(false);

  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [loadingLatest, setLoadingLatest] = useState(true);

  // Default date range (last 30 days)
  useEffect(() => {
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);
    setEndDate(today.toISOString().split('T')[0]);
    setStartDate(thirtyDaysAgo.toISOString().split('T')[0]);
  }, []);

  // Auto-load the last cached strategic insight on mount (no date range required)
  useEffect(() => {
    let cancelled = false;
    strategicInsightsService
      .getLatestInsights()
      .then((result) => {
        if (cancelled || !result.success) return;
        setInsights(result.data.insights);
        setUsage(result.data.usage);
        setCacheHit(result.data.cache_hit ?? true);
      })
      .catch(() => {
        // No cached insight or network error: leave empty state; user can generate
        if (!cancelled) setError(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingLatest(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

    try {
      setLoading(true);
      setError(null);

      const result = await strategicInsightsService.generateInsights({
        start_date: startDate,
        end_date: endDate,
        compare_to_previous: compareToPrevious,
      });

      if (result.success) {
        setInsights(result.data.insights);
        setUsage(result.data.usage);
        setCacheHit(result.data.cache_hit);
      } else {
        setError('Failed to generate strategic insights');
      }
    } catch (err: unknown) {
      console.error('Strategic insights generation error:', err);
      const message =
        err instanceof Error
          ? err.message
          : (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data
              ?.error?.message ?? 'Failed to generate strategic insights';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpanded = (id: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const formatCurrency = (paise: number) =>
    `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 0 })}`;

  const formatConfidence = (confidence: number) =>
    `${(confidence * 100).toFixed(0)}%`;

  return (
    <div className="home-panel">
      {/* Controls Card */}
      <div className="insights-controls-card">
        <div className="insights-page-header">
          <h2 className="insights-page-title">🎯 Strategic Business Insights (NEW)</h2>
          <p className="insights-page-description">
            AI-powered strategic analysis identifying opportunities and risks with evidence-based recommendations
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

        {/* Compare Toggle */}
        <div className="insights-section">
          <label className="insights-compare-toggle">
            <input
              type="checkbox"
              checked={compareToPrevious}
              onChange={(e) => setCompareToPrevious(e.target.checked)}
            />
            <span className="insights-compare-label">Compare to previous period</span>
          </label>
        </div>

        {/* Generate */}
        <div className="insights-generate-section">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={loading}
            className="btn btn-primary insights-generate-btn"
          >
            {loading ? 'Analyzing...' : 'Generate Strategic Insights'}
          </button>
          {!loading && (
            <span className="insights-generate-hint">
              Deep analysis may take 2–5 minutes
            </span>
          )}
        </div>

        {/* Token usage */}
        {insights && usage && (
          <div className="insights-token-usage" title={cacheHit ? 'Retrieved from cache' : 'API token usage for this run'}>
            {cacheHit ? (
              <span className="insights-token-usage-cache">⚡ From cache (no API tokens used)</span>
            ) : (
              <>
                <span className="insights-token-usage-label">Tokens:</span>
                <span className="insights-token-usage-value">
                  {usage.total_tokens.toLocaleString()} total
                </span>
                <span className="insights-token-usage-detail">
                  ({usage.input_tokens.toLocaleString()}↑ · {usage.output_tokens.toLocaleString()}↓ · ${usage.cost_usd.toFixed(3)})
                </span>
              </>
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
          <p className="insights-loading-title">Strategic Analysis in Progress…</p>
          <p className="insights-loading-subtitle">
            AI agent is iteratively exploring your data to identify opportunities and risks. This may take 2–5 minutes.
          </p>
        </div>
      )}

      {/* Results */}
      {insights && !loading && !loadingLatest && (
        <div className="insights-results">
          {/* Executive Summary */}
          <div className="strategic-summary-card">
            <h3 className="strategic-summary-title">Executive Summary</h3>
            <div className="strategic-summary-text strategic-summary-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{insights.executive_summary}</ReactMarkdown>
            </div>
            <div className="strategic-summary-meta">
              <span>📊 {insights.analysis_period.duration_days} days analyzed</span>
              <span>🔄 {insights.iterations_used} iterations</span>
              <span>✨ {insights.opportunities.length} opportunities</span>
              <span>⚠️ {insights.risks.length} risks</span>
            </div>
          </div>

          {/* Opportunities Section */}
          <div className="insights-issues-section">
            <div className="insights-issues-header">
              <h3 className="insights-issues-title">💡 Opportunities</h3>
              <span className="insights-issues-count-badge">
                {insights.opportunities.length}
              </span>
            </div>

            {insights.opportunities.length === 0 ? (
              <div className="insights-success-empty" role="status">
                <span className="insights-success-icon">💡</span>
                <p className="insights-success-title">No Opportunities Identified</p>
                <p className="insights-success-description">
                  The AI analysis did not identify significant opportunities in this period.
                </p>
              </div>
            ) : (
              <div className="insights-issues-grid">
                {insights.opportunities.map((opp) => (
                  <OpportunityCard
                    key={opp.id}
                    opportunity={opp}
                    expanded={expandedItems.has(opp.id)}
                    onToggle={() => toggleExpanded(opp.id)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Risks Section */}
          <div className="insights-issues-section">
            <div className="insights-issues-header">
              <h3 className="insights-issues-title">⚠️ Risks</h3>
              <span className="insights-issues-count-badge insights-issues-count-badge--risk">
                {insights.risks.length}
              </span>
            </div>

            {insights.risks.length === 0 ? (
              <div className="insights-success-empty" role="status">
                <span className="insights-success-icon">✅</span>
                <p className="insights-success-title">No Critical Risks Detected</p>
                <p className="insights-success-description">
                  Your restaurant operations appear stable with no critical risks identified.
                </p>
              </div>
            ) : (
              <div className="insights-issues-grid">
                {insights.risks.map((risk) => (
                  <RiskCard
                    key={risk.id}
                    risk={risk}
                    expanded={expandedItems.has(risk.id)}
                    onToggle={() => toggleExpanded(risk.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Loading latest (initial load only) */}
      {loadingLatest && !insights && (
        <div className="insights-loading insights-loading--latest" role="status" aria-live="polite">
          <div className="insights-loading-spinner" aria-hidden="true" />
          <p className="insights-loading-title">Loading latest insight…</p>
        </div>
      )}

      {/* Empty State */}
      {!insights && !loading && !loadingLatest && (
        <div className="insights-empty-state" role="status">
          <span className="insights-empty-icon">🎯</span>
          <p className="insights-empty-title">No Strategic Insights Generated Yet</p>
          <p className="insights-empty-description">
            Select a date range and click "Generate Strategic Insights" to discover opportunities and risks
          </p>
        </div>
      )}
    </div>
  );
}

// ===== Opportunity Card Component =====

interface OpportunityCardProps {
  opportunity: Opportunity;
  expanded: boolean;
  onToggle: () => void;
}

function OpportunityCard({ opportunity, expanded, onToggle }: OpportunityCardProps) {
  const formatCurrency = (paise: number) =>
    `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 0 })}`;

  const categoryColor = CATEGORY_COLORS[opportunity.category] || '#6b7280';
  const categoryIcon = CATEGORY_ICONS[opportunity.category] || '💡';

  return (
    <div className="issue-card" style={{ borderLeftColor: categoryColor }}>
      <div className="issue-header">
        <div className="issue-header-top">
          <span className="issue-category" style={{ backgroundColor: `${categoryColor}20`, color: categoryColor }}>
            {categoryIcon} {opportunity.category.replace(/_/g, ' ')}
          </span>
          <div className="issue-badges">
            <span className="issue-badge issue-badge--confidence" title="Confidence score">
              {(opportunity.confidence * 100).toFixed(0)}% confidence
            </span>
            <span className="issue-badge issue-badge--effort" title="Implementation effort">
              {opportunity.effort} effort
            </span>
          </div>
        </div>
        <h4 className="issue-title">{opportunity.title}</h4>
      </div>

      <div className="issue-body">
        <div className="issue-impact">
          <span className="issue-impact-label">Expected Impact:</span>
          <span className="issue-impact-value" style={{ color: categoryColor }}>
            {formatCurrency(opportunity.impact_expected)}/month
          </span>
          <span className="issue-impact-range">
            ({formatCurrency(opportunity.impact_min)} – {formatCurrency(opportunity.impact_max)})
          </span>
        </div>

        <p className="issue-description">{opportunity.description}</p>

        {/* Evidence */}
        <div className="issue-section">
          <div className="issue-section-header">
            <strong>📊 Evidence ({opportunity.evidence.length} data points)</strong>
          </div>
          <div className="evidence-grid">
            {opportunity.evidence.slice(0, expanded ? undefined : 2).map((ev, idx) => (
              <div key={idx} className="evidence-item">
                <span className="evidence-metric">{ev.metric}:</span>
                <span className="evidence-value">{ev.value}</span>
                {ev.statistically_significant && <span className="evidence-badge">✓ Significant</span>}
              </div>
            ))}
          </div>
          {opportunity.evidence.length > 2 && !expanded && (
            <button className="evidence-show-more" onClick={onToggle}>
              Show {opportunity.evidence.length - 2} more evidence points
            </button>
          )}
        </div>

        {expanded && (
          <>
            {/* Assumptions */}
            <div className="issue-section">
              <strong>📋 Assumptions:</strong>
              <ul className="issue-list">
                {opportunity.assumptions.map((assumption, idx) => (
                  <li key={idx}>{assumption}</li>
                ))}
              </ul>
            </div>

            {/* Actionable Steps */}
            <div className="issue-section">
              <strong>✅ Action Plan ({opportunity.timeline}):</strong>
              <ol className="issue-list issue-list--ordered">
                {opportunity.actionable_steps.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ol>
            </div>
          </>
        )}

        <button className="issue-expand-btn" onClick={onToggle}>
          {expanded ? '↑ Show Less' : '↓ Show More Details'}
        </button>
      </div>
    </div>
  );
}

// ===== Risk Card Component =====

interface RiskCardProps {
  risk: Risk;
  expanded: boolean;
  onToggle: () => void;
}

function RiskCard({ risk, expanded, onToggle }: RiskCardProps) {
  const formatCurrency = (paise: number) =>
    `₹${(Math.abs(paise) / 100).toLocaleString('en-IN', { minimumFractionDigits: 0 })}`;

  const categoryColor = CATEGORY_COLORS[risk.category] || '#dc2626';
  const categoryIcon = CATEGORY_ICONS[risk.category] || '⚠️';

  const severityColors: Record<string, string> = {
    low: '#10b981',
    medium: '#f59e0b',
    high: '#ef4444',
    critical: '#dc2626',
  };

  const severityColor = severityColors[risk.severity] || '#ef4444';

  return (
    <div className="issue-card issue-card--risk" style={{ borderLeftColor: categoryColor }}>
      <div className="issue-header">
        <div className="issue-header-top">
          <span className="issue-category" style={{ backgroundColor: `${categoryColor}20`, color: categoryColor }}>
            {categoryIcon} {risk.category.replace(/_/g, ' ')}
          </span>
          <div className="issue-badges">
            <span className="issue-badge" style={{ backgroundColor: `${severityColor}20`, color: severityColor }}>
              {risk.severity.toUpperCase()}
            </span>
            <span className="issue-badge issue-badge--probability" title="Probability">
              {(risk.probability * 100).toFixed(0)}% likely
            </span>
          </div>
        </div>
        <h4 className="issue-title">{risk.title}</h4>
      </div>

      <div className="issue-body">
        <div className="issue-impact">
          <span className="issue-impact-label">Potential Loss:</span>
          <span className="issue-impact-value issue-impact-value--loss">
            {formatCurrency(risk.impact_expected)}
          </span>
          <span className="issue-impact-range">
            ({formatCurrency(risk.impact_min)} – {formatCurrency(risk.impact_max)})
          </span>
        </div>

        <p className="issue-description">{risk.description}</p>

        {/* Evidence */}
        <div className="issue-section">
          <div className="issue-section-header">
            <strong>📊 Evidence ({risk.evidence.length} data points)</strong>
          </div>
          <div className="evidence-grid">
            {risk.evidence.slice(0, expanded ? undefined : 2).map((ev, idx) => (
              <div key={idx} className="evidence-item">
                <span className="evidence-metric">{ev.metric}:</span>
                <span className="evidence-value">{ev.value}</span>
                {ev.statistically_significant && <span className="evidence-badge">✓ Significant</span>}
              </div>
            ))}
          </div>
          {risk.evidence.length > 2 && !expanded && (
            <button className="evidence-show-more" onClick={onToggle}>
              Show {risk.evidence.length - 2} more evidence points
            </button>
          )}
        </div>

        {expanded && (
          <>
            {/* Mitigation Steps */}
            <div className="issue-section">
              <strong>🛡️ Mitigation Plan ({risk.timeline}):</strong>
              <ol className="issue-list issue-list--ordered">
                {risk.mitigation_steps.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ol>
            </div>
          </>
        )}

        <button className="issue-expand-btn" onClick={onToggle}>
          {expanded ? '↑ Show Less' : '↓ Show More Details'}
        </button>
      </div>
    </div>
  );
}
