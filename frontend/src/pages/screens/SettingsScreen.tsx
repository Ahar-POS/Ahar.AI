/**
 * Settings Screen — sidebar navigation with embedded existing page components.
 */

import { useState } from 'react';
import MenuPage from '../MenuPage';
import StaffPage from '../StaffPage';
import { InventoryTab } from '../../components/InventoryTab';
import { FinancialSettingsTab } from '../../components/FinancialSettingsTab';
import SettingsPage from '../SettingsPage';
import './SettingsScreen.css';

type SettingsItem =
  | 'menu'
  | 'staff'
  | 'inventory'
  | 'financial'
  | 'general'
  | 'security'
  | 'notifications'
  | 'ai-settings';

interface SettingsNavItem {
  id: SettingsItem;
  label: string;
}

const MANAGEMENT_ITEMS: SettingsNavItem[] = [
  { id: 'menu', label: 'Menu' },
  { id: 'staff', label: 'Staff' },
  { id: 'inventory', label: 'Inventory' },
];

const PREFERENCES_ITEMS: SettingsNavItem[] = [
  { id: 'financial', label: 'Financial Settings' },
  { id: 'general', label: 'General' },
  { id: 'security', label: 'Security' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'ai-settings', label: 'AI Settings' },
];

export default function SettingsScreen() {
  const [active, setActive] = useState<SettingsItem>('menu');

  return (
    <div className="settings-screen">
      {/* Sidebar */}
      <aside className="settings-sidebar">
        <div className="settings-sidebar-group">
          <div className="settings-sidebar-group-title">Management</div>
          {MANAGEMENT_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`settings-sidebar-item${active === item.id ? ' settings-sidebar-item--active' : ''}`}
              onClick={() => setActive(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="settings-sidebar-group">
          <div className="settings-sidebar-group-title">Preferences</div>
          {PREFERENCES_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`settings-sidebar-item${active === item.id ? ' settings-sidebar-item--active' : ''}`}
              onClick={() => setActive(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </aside>

      {/* Content */}
      <div className="settings-content">
        {renderSettingsContent(active)}
      </div>
    </div>
  );
}

function renderSettingsContent(id: SettingsItem) {
  switch (id) {
    case 'menu':
      return <MenuPage />;
    case 'staff':
      return <StaffPage />;
    case 'inventory':
      return <InventoryTab />;
    case 'financial':
      return <FinancialSettingsTab />;
    case 'general':
    case 'security':
    case 'notifications':
    case 'ai-settings':
      return <SettingsPage />;
  }
}
