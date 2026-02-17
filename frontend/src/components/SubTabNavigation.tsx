/**
 * SubTabNavigation component.
 *
 * Reusable secondary tab navigation for pages with sub-sections.
 */

import React from 'react';
import './SubTabNavigation.css';

export interface SubTab {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

interface SubTabNavigationProps {
  tabs: SubTab[];
  activeTabId: string;
  onTabChange: (tabId: string) => void;
}

/**
 * Render secondary tab navigation.
 */
export default function SubTabNavigation({
  tabs,
  activeTabId,
  onTabChange,
}: SubTabNavigationProps) {
  return (
    <div className="sub-tab-navigation">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`sub-tab-item ${tab.id === activeTabId ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.icon && <span className="sub-tab-icon">{tab.icon}</span>}
          {tab.label}
        </button>
      ))}
    </div>
  );
}
