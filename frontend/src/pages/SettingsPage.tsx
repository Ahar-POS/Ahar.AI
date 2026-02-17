/**
 * SettingsPage component.
 *
 * Organization settings for language, AI optimization, and role permissions.
 */

import React, { useState } from 'react';
import './SettingsPage.css';

// Language options
const LANGUAGES = [
  { id: 'en-US', label: 'English (US)' },
  { id: 'en-GB', label: 'English (UK)' },
  { id: 'es', label: 'Español' },
  { id: 'fr', label: 'Français' },
  { id: 'de', label: 'Deutsch' },
  { id: 'it', label: 'Italiano' },
];

// Timezone options
const TIMEZONES = [
  { id: 'America/New_York', label: 'America/New_York (EST)' },
  { id: 'America/Chicago', label: 'America/Chicago (CST)' },
  { id: 'America/Denver', label: 'America/Denver (MST)' },
  { id: 'America/Los_Angeles', label: 'America/Los_Angeles (PST)' },
  { id: 'Europe/London', label: 'Europe/London (GMT)' },
  { id: 'Europe/Paris', label: 'Europe/Paris (CET)' },
  { id: 'Asia/Tokyo', label: 'Asia/Tokyo (JST)' },
];

// Currency options
const CURRENCIES = [
  { id: 'USD', symbol: '$', label: 'USD' },
  { id: 'EUR', symbol: '€', label: 'EUR' },
  { id: 'GBP', symbol: '£', label: 'GBP' },
  { id: 'INR', symbol: '₹', label: 'INR' },
  { id: 'JPY', symbol: '¥', label: 'JPY' },
];

// Role definitions
const ROLES = [
  {
    id: 'waiter',
    name: 'Waiter',
    description: 'Front-of-house staff for order taking',
    tabs: ['Kitchen', 'Waiter', 'Tables', 'Menu'],
  },
  {
    id: 'chef',
    name: 'Chef',
    description: 'Kitchen staff for food preparation',
    tabs: ['Kitchen', 'Menu'],
  },
  {
    id: 'cashier',
    name: 'Cashier',
    description: 'Handles payments and reports',
    tabs: ['Kitchen', 'Reports', 'Tables'],
  },
];

/**
 * Settings page component.
 */
export default function SettingsPage() {
  // Language & Region state
  const [language, setLanguage] = useState('en-US');
  const [timezone, setTimezone] = useState('America/New_York');
  const [currency, setCurrency] = useState('USD');

  // AI Optimization state
  const [timePriority, setTimePriority] = useState(40);
  const [ingredientOverlap, setIngredientOverlap] = useState(30);
  const [stationBalance, setStationBalance] = useState(20);
  const [showAiTips, setShowAiTips] = useState(true);

  // Modal state
  const [editingRole, setEditingRole] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  return (
    <div className="settings-page">
      {/* Header */}
      <div className="settings-page-header">
        <h1 className="settings-page-title">Organization Settings</h1>
        <p className="settings-page-subtitle">
          Configure language preferences, AI optimization, and role permissions
        </p>
      </div>

      {/* Language & Region */}
      <section className="settings-section">
        <h2 className="settings-section-title">Language & Region</h2>
        <p className="settings-section-description">
          Configure default language and regional settings
        </p>

        <div className="settings-card">
          <div className="setting-row">
            <div className="setting-info">
              <span className="setting-label">Default Language</span>
              <span className="setting-value">
                {LANGUAGES.find((l) => l.id === language)?.label}
              </span>
            </div>
            <button
              type="button"
              className="setting-btn"
              onClick={() => {
                const current = LANGUAGES.findIndex((l) => l.id === language);
                const next = (current + 1) % LANGUAGES.length;
                setLanguage(LANGUAGES[next].id);
              }}
            >
              Change
            </button>
          </div>

          <div className="setting-row">
            <div className="setting-info">
              <span className="setting-label">Timezone</span>
              <span className="setting-value">
                {TIMEZONES.find((t) => t.id === timezone)?.label}
              </span>
            </div>
            <button
              type="button"
              className="setting-btn"
              onClick={() => {
                const current = TIMEZONES.findIndex((t) => t.id === timezone);
                const next = (current + 1) % TIMEZONES.length;
                setTimezone(TIMEZONES[next].id);
              }}
            >
              Change
            </button>
          </div>

          <div className="setting-row">
            <div className="setting-info">
              <span className="setting-label">Currency</span>
              <span className="setting-value">
                {CURRENCIES.find((c) => c.id === currency)?.symbol}{' '}
                {CURRENCIES.find((c) => c.id === currency)?.label}
              </span>
            </div>
            <button
              type="button"
              className="setting-btn"
              onClick={() => {
                const current = CURRENCIES.findIndex((c) => c.id === currency);
                const next = (current + 1) % CURRENCIES.length;
                setCurrency(CURRENCIES[next].id);
              }}
            >
              Change
            </button>
          </div>
        </div>
      </section>

      {/* AI Kitchen Optimization */}
      <section className="settings-section">
        <h2 className="settings-section-title">AI Kitchen Optimization</h2>
        <p className="settings-section-description">
          Fine-tune how the AI prioritizes and batches orders
        </p>

        <div className="settings-card">
          <div className="slider-setting">
            <div className="slider-header">
              <span className="slider-label">Time Priority Weight</span>
              <span className="slider-value">{timePriority}%</span>
            </div>
            <div className="slider-track-container">
              <div
                className="slider-track-fill"
                style={{ width: `${timePriority}%` }}
              />
              <input
                type="range"
                min="0"
                max="100"
                value={timePriority}
                onChange={(e) => setTimePriority(Number(e.target.value))}
                className="slider-input"
              />
            </div>
          </div>

          <div className="slider-setting">
            <div className="slider-header">
              <span className="slider-label">Ingredient Overlap Weight</span>
              <span className="slider-value">{ingredientOverlap}%</span>
            </div>
            <div className="slider-track-container">
              <div
                className="slider-track-fill"
                style={{ width: `${ingredientOverlap}%` }}
              />
              <input
                type="range"
                min="0"
                max="100"
                value={ingredientOverlap}
                onChange={(e) => setIngredientOverlap(Number(e.target.value))}
                className="slider-input"
              />
            </div>
          </div>

          <div className="slider-setting">
            <div className="slider-header">
              <span className="slider-label">Station Load Balance</span>
              <span className="slider-value">{stationBalance}%</span>
            </div>
            <div className="slider-track-container">
              <div
                className="slider-track-fill"
                style={{ width: `${stationBalance}%` }}
              />
              <input
                type="range"
                min="0"
                max="100"
                value={stationBalance}
                onChange={(e) => setStationBalance(Number(e.target.value))}
                className="slider-input"
              />
            </div>
          </div>

          <div className="toggle-setting">
            <div className="toggle-info">
              <span className="toggle-label">Show AI Tips</span>
              <span className="toggle-description">
                Display optimization suggestions
              </span>
            </div>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={showAiTips}
                onChange={(e) => setShowAiTips(e.target.checked)}
              />
              <span className="toggle-slider" />
            </label>
          </div>
        </div>
      </section>

      {/* Role Permissions */}
      <section className="settings-section">
        <h2 className="settings-section-title">Role Permissions</h2>
        <p className="settings-section-description">
          Configure which tabs each role can access
        </p>

        <div className="settings-card">
          {ROLES.map((role) => (
            <div key={role.id} className="role-row">
              <div className="role-info">
                <span className="role-name">{role.name}</span>
                <span className="role-tabs">{role.tabs.join(', ')}</span>
              </div>
              <button
                type="button"
                className="setting-btn"
                onClick={() => setEditingRole(role.id)}
              >
                Edit
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Account Management */}
      <section className="settings-section settings-section-danger">
        <h2 className="settings-section-title">Account Management</h2>

        <div className="settings-card settings-card-danger">
          <div className="danger-row">
            <div className="danger-info">
              <span className="danger-label">Delete Account</span>
              <span className="danger-description">
                Permanently delete your account and all data
              </span>
            </div>
            <button
              type="button"
              className="danger-btn"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Delete
            </button>
          </div>
        </div>
      </section>

      {/* Role Edit Modal */}
      {editingRole && (
        <RoleEditModal
          role={ROLES.find((r) => r.id === editingRole)!}
          onClose={() => setEditingRole(null)}
        />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <DeleteConfirmModal onClose={() => setShowDeleteConfirm(false)} />
      )}
    </div>
  );
}

/**
 * Role Edit Modal component.
 */
interface RoleEditModalProps {
  role: (typeof ROLES)[0];
  onClose: () => void;
}

function RoleEditModal({ role, onClose }: RoleEditModalProps) {
  const allTabs = ['Kitchen', 'Waiter', 'Tables', 'Menu', 'Staff', 'Reports', 'Analytics', 'Settings'];
  const [selectedTabs, setSelectedTabs] = useState<Set<string>>(new Set(role.tabs));

  const handleTabToggle = (tab: string) => {
    setSelectedTabs((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(tab)) {
        newSet.delete(tab);
      } else {
        newSet.add(tab);
      }
      return newSet;
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Edit {role.name} Permissions</h2>
          <button type="button" className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-description">{role.description}</p>

          <div className="tab-permissions">
            <h4 className="permissions-title">Tab Access</h4>
            <div className="permissions-grid">
              {allTabs.map((tab) => (
                <label key={tab} className="permission-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedTabs.has(tab)}
                    onChange={() => handleTabToggle(tab)}
                  />
                  <span className="checkbox-label">{tab}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Delete Confirmation Modal component.
 */
interface DeleteConfirmModalProps {
  onClose: () => void;
}

function DeleteConfirmModal({ onClose }: DeleteConfirmModalProps) {
  const [confirmText, setConfirmText] = useState('');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-danger" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Delete Account</h2>
          <button type="button" className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="modal-body">
          <div className="delete-warning">
            <span className="warning-icon">⚠️</span>
            <p>
              This action cannot be undone. All your data, including orders,
              menu items, and settings will be permanently deleted.
            </p>
          </div>

          <div className="confirm-input">
            <label>Type "DELETE" to confirm:</label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="DELETE"
            />
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            disabled={confirmText !== 'DELETE'}
            onClick={onClose}
          >
            Delete Account
          </button>
        </div>
      </div>
    </div>
  );
}
