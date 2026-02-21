import React from 'react';
import type { Issue } from '../services/insightsService';

interface IssueCardProps {
  issue: Issue;
}

const CATEGORY_ICONS: Record<string, string> = {
  financial: '💰',
  inventory: '📦',
  operational: '⚙️',
};

const IssueCard: React.FC<IssueCardProps> = ({ issue }) => {
  const priority = issue.priority.toLowerCase();
  const category = issue.category.toLowerCase();

  const categoryIcon = CATEGORY_ICONS[category] ?? '📊';

  return (
    <article className={`issue-card issue-card--${priority}`}>
      {/* Header */}
      <div className="issue-card-header">
        <div className="issue-card-category">
          <span className="issue-category-icon" aria-hidden="true">{categoryIcon}</span>
          <span className="issue-category-badge">{issue.category}</span>
        </div>
        <span className={`issue-priority-badge issue-priority-badge--${priority}`}>
          {issue.priority}
        </span>
      </div>

      {/* Title */}
      <h4 className="issue-title">{issue.title}</h4>

      {/* Root Cause */}
      <div className="issue-section">
        <span className="issue-section-label">Root Cause</span>
        <p className="issue-section-content">{issue.root_cause}</p>
      </div>

      {/* Impact */}
      <div className="issue-section">
        <span className="issue-section-label">Impact</span>
        <p className="issue-section-content issue-section-content--impact">{issue.impact}</p>
      </div>

      {/* Recommendation */}
      <div className="issue-section">
        <span className="issue-section-label">Recommendation</span>
        <p className="issue-section-content">{issue.recommendation}</p>
      </div>

      {/* Savings */}
      {issue.estimated_savings > 0 && (
        <div className="issue-savings-footer">
          <span className="issue-savings-label">Est. monthly savings</span>
          <span className="issue-savings-value">
            ₹{(issue.estimated_savings / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </span>
        </div>
      )}
    </article>
  );
};

export default IssueCard;
