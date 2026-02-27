/**
 * Operations Floor — 50/50 split with Kitchen + Tables/Waiter toggle.
 */

import { useState } from 'react';
import KitchenPage from '../KitchenPage';
import TablesPage from '../TablesPage';
import WaiterPage from '../WaiterPage';
import OperationsDashboardWidget from '../../components/OperationsDashboardWidget';
import './OperationsFloorScreen.css';

type RightTab = 'tables' | 'quick-order';

export default function OperationsFloorScreen() {
  const [rightTab, setRightTab] = useState<RightTab>('tables');
  const [isDashboardOpen, setIsDashboardOpen] = useState(false);

  return (
    <div className="ops-floor">
      {/* Left: Kitchen orders */}
      <div className="ops-panel ops-panel--left">
        <div className="ops-panel-header">
          <h2 className="ops-panel-title">Kitchen Orders</h2>
        </div>
        <div className="ops-panel-content">
          <KitchenPage />
        </div>
      </div>

      {/* Right: Tables / Quick Order toggle */}
      <div className="ops-panel ops-panel--right" style={{ position: 'relative' }}>
        <div className="ops-panel-header">
          <div className="ops-toggle">
            <button
              type="button"
              className={`ops-toggle-btn${rightTab === 'tables' ? ' ops-toggle-btn--active' : ''}`}
              onClick={() => setRightTab('tables')}
            >
              Tables
            </button>
            <button
              type="button"
              className={`ops-toggle-btn${rightTab === 'quick-order' ? ' ops-toggle-btn--active' : ''}`}
              onClick={() => setRightTab('quick-order')}
            >
              Quick Order
            </button>
          </div>
        </div>
        <div className="ops-panel-content">
          {rightTab === 'tables' ? <TablesPage /> : <WaiterPage />}
        </div>

        {/* Floating Action Button for Dashboard */}
        <button
          className="ops-dashboard-fab"
          onClick={() => setIsDashboardOpen(true)}
          aria-label="Open Operations Dashboard"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="3" y1="9" x2="21" y2="9"></line>
            <line x1="9" y1="21" x2="9" y2="9"></line>
          </svg>
          <span>Ops Stats</span>
        </button>
      </div>

      {/* Dashboard Modal */}
      {isDashboardOpen && (
        <div className="ops-modal-overlay" onClick={() => setIsDashboardOpen(false)}>
          <div className="ops-modal-content" onClick={e => e.stopPropagation()}>
            <button
              className="ops-modal-close"
              onClick={() => setIsDashboardOpen(false)}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
            <OperationsDashboardWidget />
          </div>
        </div>
      )}
    </div>
  );
}
