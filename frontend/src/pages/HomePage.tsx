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
import './HomePage.css';

interface TabDefinition extends TabItem {
  roles?: UserRole[];
}

const TAB_DEFINITIONS: TabDefinition[] = [
  { id: 'kitchen', label: 'Kitchen' },
  { id: 'waiter', label: 'Waiter' },
  { id: 'tables', label: 'Tables' },
  { id: 'menu', label: 'Menu' },
  { id: 'staff', label: 'Staff' },
  { id: 'reports', label: 'Reports' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'settings', label: 'Settings' },
];

const RESTAURANT_NAME = "Lexi's Gourmet Sandwiches";

/**
 * Home page component for authenticated users.
 */
export default function HomePage() {
  const { user } = useAuth();
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
      setActiveTabId(visibleTabs[0].id);
    }
  }, [activeTabId, visibleTabs]);

  const activeTab =
    visibleTabs.find((tab) => tab.id === activeTabId) ?? visibleTabs[0];

  return (
    <div className="home-page">
      <header className="home-header">
        <div className="home-header-container">
          <div className="home-brand">
            <span className="home-brand-icon" aria-hidden="true">🍽️</span>
            <div>
              <h1 className="home-restaurant-name">{RESTAURANT_NAME}</h1>
              <p className="home-restaurant-role">{formatRoleLabel(user?.role)}</p>
            </div>
          </div>

          {/* Header actions can be added here if needed */}
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
    case 'reports':
    case 'analytics':
    case 'settings':
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
