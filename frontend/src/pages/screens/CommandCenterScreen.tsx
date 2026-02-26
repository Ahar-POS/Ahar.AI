/**
 * Command Center — Chat + Dashboard toggle with slide-up animation.
 */

import { useState } from 'react';
import ChatbotPage from '../ChatbotPage';
import CommandDashboard from '../../components/CommandDashboard';
import './CommandCenterScreen.css';

function DashboardIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export default function CommandCenterScreen() {
  const [showDashboard, setShowDashboard] = useState(false);

  const toggleButton = (
    <button
      type="button"
      className={`cc-dashboard-toggle${showDashboard ? ' cc-dashboard-toggle--active' : ''}`}
      onClick={() => setShowDashboard((prev) => !prev)}
      aria-label="Toggle dashboard"
      title="Toggle dashboard"
    >
      <DashboardIcon />
    </button>
  );

  return (
    <div className="cc-screen">
      {/* Chat view */}
      <div className={`cc-chat${showDashboard ? ' cc-chat--hidden' : ''}`}>
        <ChatbotPage dashboardToggle={toggleButton} />
      </div>

      {/* Dashboard overlay — slides up */}
      <div className={`cc-dashboard${showDashboard ? ' cc-dashboard--visible' : ''}`}>
        <CommandDashboard onClose={() => setShowDashboard(false)} />
      </div>
    </div>
  );
}
