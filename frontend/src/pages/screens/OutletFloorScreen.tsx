/**
 * Outlet Floor — 50/50 split with Kitchen + Tables/Waiter toggle.
 */

import { useState } from 'react';
import KitchenPage from '../KitchenPage';
import TablesPage from '../TablesPage';
import WaiterPage from '../WaiterPage';
import OutletDashboardWidget from '../../components/OutletDashboardWidget';
import './OutletFloorScreen.css';

type RightTab = 'tables' | 'quick-order';

export default function OutletFloorScreen() {
  const [rightTab, setRightTab] = useState<RightTab>('tables');
  const [isDashboardOpen, setIsDashboardOpen] = useState(false);

  return (
    <div className="outlet-floor">
      {/* Left: Kitchen orders */}
      <div className="outlet-panel outlet-panel--left">
        <div className="outlet-panel-header">
          <h2 className="outlet-panel-title">Kitchen Orders</h2>
        </div>
        <div className="outlet-panel-content">
          <KitchenPage />
        </div>
      </div>

      {/* Right: Tables / Quick Order toggle */}
      <div className="outlet-panel outlet-panel--right" style={{ position: 'relative' }}>
        <div className="outlet-panel-header">
          <div className="outlet-toggle">
            <button
              type="button"
              className={`outlet-toggle-btn${rightTab === 'tables' ? ' outlet-toggle-btn--active' : ''}`}
              onClick={() => setRightTab('tables')}
            >
              Tables
            </button>
            <button
              type="button"
              className={`outlet-toggle-btn${rightTab === 'quick-order' ? ' outlet-toggle-btn--active' : ''}`}
              onClick={() => setRightTab('quick-order')}
            >
              Quick Order
            </button>
          </div>
        </div>
        <div className="outlet-panel-content">
          {rightTab === 'tables' ? <TablesPage /> : <WaiterPage />}
        </div>

        {/* Floating Action Button for Dashboard */}
        <button
          className="outlet-dashboard-fab"
          onClick={() => setIsDashboardOpen(true)}
          aria-label="Open Outlet Dashboard"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="3" y1="9" x2="21" y2="9"></line>
            <line x1="9" y1="21" x2="9" y2="9"></line>
          </svg>
          <span>Outlet Stats</span>
        </button>
      </div>

      {/* Dashboard Modal */}
      {isDashboardOpen && (
        <div className="outlet-modal-overlay" onClick={() => setIsDashboardOpen(false)}>
          <div className="outlet-modal-content" onClick={e => e.stopPropagation()}>
            <button
              className="outlet-modal-close"
              onClick={() => setIsDashboardOpen(false)}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
            <OutletDashboardWidget />
          </div>
        </div>
      )}
    </div>
  );
}
