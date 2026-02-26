/**
 * Operations Floor — 50/50 split with Kitchen + Tables/Waiter toggle.
 */

import { useState } from 'react';
import KitchenPage from '../KitchenPage';
import TablesPage from '../TablesPage';
import WaiterPage from '../WaiterPage';
import './OperationsFloorScreen.css';

type RightTab = 'tables' | 'quick-order';

export default function OperationsFloorScreen() {
  const [rightTab, setRightTab] = useState<RightTab>('tables');

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
      <div className="ops-panel ops-panel--right">
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
      </div>
    </div>
  );
}
