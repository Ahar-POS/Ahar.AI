/**
 * Authenticated home page with role-aware tabs.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types/auth';
import TabNavigation, { TabItem } from '../components/TabNavigation';
import TablesPage from './TablesPage';
import MenuPage from './MenuPage';
import WaiterPage from './WaiterPage';
import KitchenPage from './KitchenPage';
import ReportsPage from './ReportsPage';
import AnalyticsPage from './AnalyticsPage';
import ChatbotPage from './ChatbotPage';
import SettingsPage from './SettingsPage';
import StaffPage from './StaffPage';
import { InventoryTab } from '../components/InventoryTab';
import { FinancialTab } from '../components/FinancialTab';
import InsightsPage from './InsightsPage';
import ApprovalsPage from './ApprovalsPage';
import './HomePage.css';

interface TabDefinition extends TabItem {
  roles?: UserRole[];
}

const TAB_DEFINITIONS: TabDefinition[] = [
  // Operational tabs accessible to both admin and staff users
  { id: 'kitchen', label: 'Kitchen', roles: ['admin', 'staff'] },
  { id: 'waiter', label: 'Waiter', roles: ['admin', 'staff'] },
  { id: 'tables', label: 'Tables', roles: ['admin', 'staff'] },
  { id: 'menu', label: 'Menu', roles: ['admin', 'staff'] },
  // Admin-only tabs
  { id: 'staff', label: 'Staff', roles: ['admin'] },
  { id: 'inventory', label: 'Inventory', roles: ['admin'] },
  { id: 'approvals', label: 'Approvals', roles: ['admin'] },
  { id: 'financial', label: 'Financial', roles: ['admin'] },
  { id: 'insights', label: 'Insights', roles: ['admin'] },
  { id: 'reports', label: 'Reports', roles: ['admin'] },
  { id: 'analytics', label: 'Analytics', roles: ['admin'] },
  { id: 'chatbot', label: 'Chatbot', roles: ['admin'] },
  { id: 'settings', label: 'Settings', roles: ['admin'] },
];

const RESTAURANT_NAME = "Lexi's Gourmet Sandwiches";

/**
 * Home page component for authenticated users.
 */
export default function HomePage() {
  const { user, logout } = useAuth();
  const [activeTabId, setActiveTabId] = useState('menu');

  const visibleTabs = useMemo(() => {
    const userRole = user?.role;
    return TAB_DEFINITIONS.filter((tab) => hasTabAccess(tab, userRole));
  }, [user?.role]);

  useEffect(() => {
    if (visibleTabs.length === 0) {
      return;
    }

    const hasActiveTab = visibleTabs.some((tab) => tab.id === activeTabId);
    if (!hasActiveTab) {
      // Prefer Menu as the default tab when available, otherwise fall back
      // to the first visible tab. This ensures staff are redirected to Menu
      // when trying to access admin-only tabs.
      const menuTab = visibleTabs.find((tab) => tab.id === 'menu');
      setActiveTabId(menuTab?.id ?? visibleTabs[0].id);
    }
  }, [activeTabId, visibleTabs]);

  const activeTab =
    visibleTabs.find((tab) => tab.id === activeTabId) ?? visibleTabs[0];

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className={`home-page${activeTab?.id === 'chatbot' ? ' home-page--immersive' : ''}`}>
      <header className="home-header">
        <div className="home-header-container">
          <div className="home-brand">
            <span className="home-brand-icon" aria-hidden="true">🍽️</span>
            <div>
              <h1 className="home-restaurant-name">{RESTAURANT_NAME}</h1>
              <p className="home-restaurant-role">{formatRoleLabel(user?.role)}</p>
            </div>
          </div>

          <div className="home-header-actions">
            {user && (
              <span className="home-restaurant-role">
                Signed in as {user.first_name}
              </span>
            )}
            <button
              type="button"
              className="btn btn-ghost"
              onClick={handleLogout}
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="home-tabs">
        <TabNavigation
          tabs={visibleTabs}
          activeTabId={activeTab?.id ?? 'menu'}
          onTabChange={setActiveTabId}
        />
      </div>

      <main className="home-content">
        <section
          id={`tab-panel-${activeTab?.id ?? 'menu'}`}
          role="tabpanel"
          aria-labelledby={`tab-${activeTab?.id ?? 'menu'}`}
          className="home-panel"
        >
          {renderTabContent(activeTab?.id)}
        </section>
      </main>
    </div>
  );
}

/**
 * Placeholder permission check for future role-based access.
 */
function hasTabAccess(tab: TabDefinition, role?: UserRole): boolean {
  if (!role) {
    return true;
  }

  if (!tab.roles || tab.roles.length === 0) {
    return true;
  }

  return tab.roles.includes(role);
}

/**
 * Format role labels for display.
 */
function formatRoleLabel(role?: UserRole): string {
  if (!role) {
    return 'Admin';
  }

  return role.charAt(0).toUpperCase() + role.slice(1);
}

/**
 * Render content for the active tab.
 */
function renderTabContent(tabId?: string): React.ReactNode {
  switch (tabId) {
    case 'tables':
      return <TablesPage />;
    case 'menu':
      return <MenuPage />;
    case 'waiter':
      return <WaiterPage />;
    case 'kitchen':
      return <KitchenPage />;
    case 'staff':
      return <StaffPage />;
    case 'inventory':
      return <InventoryTab />;
    case 'approvals':
      return <ApprovalsPage />;
    case 'financial':
      return <FinancialTab />;
    case 'insights':
      return <InsightsPage />;
    case 'reports':
      return <ReportsPage />;
    case 'analytics':
      return <AnalyticsPage />;
    case 'chatbot':
      return <ChatbotPage />;
    case 'settings':
      return <SettingsPage />;
    default:
      return (
        <div className="home-panel-card">
          <h2 className="home-panel-title">
            {tabId ? tabId.charAt(0).toUpperCase() + tabId.slice(1) : 'Menu'}
          </h2>
          <p className="home-panel-description">Coming Soon</p>
        </div>
      );
  }
}
