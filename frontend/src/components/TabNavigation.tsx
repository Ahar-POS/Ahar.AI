/**
 * Tab navigation component for authenticated pages.
 */

import React from 'react';
import './TabNavigation.css';

export interface TabItem {
  id: string;
  label: string;
  shortLabel?: string;
}

interface TabNavigationProps {
  tabs: TabItem[];
  activeTabId: string;
  onTabChange: (tabId: string) => void;
}

/**
 * Render responsive tab navigation (desktop top tabs, mobile bottom tabs).
 */
export default function TabNavigation({
  tabs,
  activeTabId,
  onTabChange,
}: TabNavigationProps) {
  return (
    <div className="tab-navigation">
      <div className="tab-navigation-desktop" role="tablist" aria-label="Primary">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={tab.id === activeTabId}
            aria-controls={`tab-panel-${tab.id}`}
            tabIndex={tab.id === activeTabId ? 0 : -1}
            className={`tab-navigation-item ${tab.id === activeTabId ? 'active' : ''}`}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="tab-navigation-mobile" role="tablist" aria-label="Primary">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}-mobile`}
            aria-selected={tab.id === activeTabId}
            aria-controls={`tab-panel-${tab.id}`}
            tabIndex={tab.id === activeTabId ? 0 : -1}
            className={`tab-navigation-item ${tab.id === activeTabId ? 'active' : ''}`}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.shortLabel ?? tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
