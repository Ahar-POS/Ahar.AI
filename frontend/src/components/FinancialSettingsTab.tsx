/**
 * Financial Settings Tab
 *
 * Configuration interface for P&L calculation parameters including:
 * - Platform commission rates
 * - Role salaries
 * - OPEX budgets
 * - Depreciation and tax rates
 */

import { useState, useEffect } from 'react';
import { settingsService } from '../services/settings';
import type { RestaurantSettings } from '../types/settings';
import './FinancialSettingsTab.css';

export function FinancialSettingsTab() {
  const [settings, setSettings] = useState<RestaurantSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await settingsService.getSettings();
      if (response.data) {
        setSettings(response.data);
      } else {
        // Initialize if no settings exist
        const initResponse = await settingsService.initializeSettings();
        setSettings(initResponse.data);
      }
    } catch (error: any) {
      setMessage({ type: 'error', text: `Failed to load settings: ${error.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;

    try {
      setSaving(true);
      setMessage(null);

      await settingsService.updateSettings({
        platform_settings: settings.platform_settings,
        role_salaries: settings.role_salaries,
        pf_esic_settings: settings.pf_esic_settings,
        overtime_settings: settings.overtime_settings,
        occupancy_costs: settings.occupancy_costs,
        technology_costs: settings.technology_costs,
        marketing_budgets: settings.marketing_budgets,
        general_admin_costs: settings.general_admin_costs,
        depreciation_amortization: settings.depreciation_amortization,
        finance_costs: settings.finance_costs,
        tax_settings: settings.tax_settings,
      });

      setMessage({ type: 'success', text: 'Settings saved successfully!' });

      // Clear message after 3 seconds
      setTimeout(() => setMessage(null), 3000);
    } catch (error: any) {
      setMessage({ type: 'error', text: `Failed to save: ${error.message}` });
    } finally {
      setSaving(false);
    }
  };

  const formatCurrency = (paise: number) => (paise / 100).toFixed(2);
  const parseCurrency = (rupees: string) => Math.round(parseFloat(rupees || '0') * 100);

  if (loading) {
    return <div className="financial-settings-loading">Loading settings...</div>;
  }

  if (!settings) {
    return <div className="financial-settings-error">Failed to load settings</div>;
  }

  return (
    <div className="financial-settings">
      <div className="financial-settings-header">
        <h2>Financial Settings</h2>
        <p>Configure parameters for P&L calculation. All monetary values are monthly unless specified.</p>
      </div>

      {message && (
        <div className={`financial-settings-message financial-settings-message--${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="financial-settings-content">
        {/* Platform Settings */}
        <section className="financial-settings-section">
          <h3>Platform & Tax Rates</h3>
          <div className="financial-settings-grid">
            <div className="financial-settings-field">
              <label>Zomato Commission (%)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={(settings.platform_settings.zomato_commission_rate * 100).toFixed(2)}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    platform_settings: {
                      ...settings.platform_settings,
                      zomato_commission_rate: parseFloat(e.target.value) / 100,
                    },
                  })
                }
              />
            </div>
            <div className="financial-settings-field">
              <label>Swiggy Commission (%)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={(settings.platform_settings.swiggy_commission_rate * 100).toFixed(2)}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    platform_settings: {
                      ...settings.platform_settings,
                      swiggy_commission_rate: parseFloat(e.target.value) / 100,
                    },
                  })
                }
              />
            </div>
            <div className="financial-settings-field">
              <label>GST Rate (%)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={(settings.platform_settings.gst_rate * 100).toFixed(2)}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    platform_settings: {
                      ...settings.platform_settings,
                      gst_rate: parseFloat(e.target.value) / 100,
                    },
                  })
                }
              />
            </div>
            <div className="financial-settings-field">
              <label>Cancellation Rate (%)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={(settings.platform_settings.cancellation_rate * 100).toFixed(2)}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    platform_settings: {
                      ...settings.platform_settings,
                      cancellation_rate: parseFloat(e.target.value) / 100,
                    },
                  })
                }
              />
            </div>
          </div>
        </section>

        {/* Role Salaries */}
        <section className="financial-settings-section">
          <h3>Role Salaries (Monthly)</h3>
          <div className="financial-settings-grid">
            {Object.entries(settings.role_salaries).map(([role, salary]) => (
              <div key={role} className="financial-settings-field">
                <label>{role.replace('_', ' ').charAt(0).toUpperCase() + role.slice(1)}</label>
                <div className="financial-settings-input-group">
                  <span className="financial-settings-currency">₹</span>
                  <input
                    type="number"
                    step="1000"
                    min="0"
                    value={formatCurrency(salary)}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        role_salaries: {
                          ...settings.role_salaries,
                          [role]: parseCurrency(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Occupancy Costs */}
        <section className="financial-settings-section">
          <h3>Occupancy & Utilities (Monthly)</h3>
          <div className="financial-settings-grid">
            {Object.entries(settings.occupancy_costs).map(([key, cost]) => (
              <div key={key} className="financial-settings-field">
                <label>{key.replace('_', ' ').charAt(0).toUpperCase() + key.slice(1)}</label>
                <div className="financial-settings-input-group">
                  <span className="financial-settings-currency">₹</span>
                  <input
                    type="number"
                    step="100"
                    min="0"
                    value={formatCurrency(cost)}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        occupancy_costs: {
                          ...settings.occupancy_costs,
                          [key]: parseCurrency(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Technology Costs */}
        <section className="financial-settings-section">
          <h3>Technology & Software (Monthly)</h3>
          <div className="financial-settings-grid">
            {Object.entries(settings.technology_costs).map(([key, cost]) => (
              <div key={key} className="financial-settings-field">
                <label>{key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')}</label>
                <div className="financial-settings-input-group">
                  <span className="financial-settings-currency">₹</span>
                  <input
                    type="number"
                    step="100"
                    min="0"
                    value={formatCurrency(cost)}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        technology_costs: {
                          ...settings.technology_costs,
                          [key]: parseCurrency(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Marketing Budgets */}
        <section className="financial-settings-section">
          <h3>Marketing & Sales (Monthly)</h3>
          <div className="financial-settings-grid">
            {Object.entries(settings.marketing_budgets).map(([key, budget]) => (
              <div key={key} className="financial-settings-field">
                <label>{key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')}</label>
                <div className="financial-settings-input-group">
                  <span className="financial-settings-currency">₹</span>
                  <input
                    type="number"
                    step="100"
                    min="0"
                    value={formatCurrency(budget)}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        marketing_budgets: {
                          ...settings.marketing_budgets,
                          [key]: parseCurrency(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* General & Admin Costs */}
        <section className="financial-settings-section">
          <h3>General & Administrative (Monthly)</h3>
          <div className="financial-settings-grid">
            {Object.entries(settings.general_admin_costs).map(([key, cost]) => (
              <div key={key} className="financial-settings-field">
                <label>{key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')}</label>
                <div className="financial-settings-input-group">
                  <span className="financial-settings-currency">₹</span>
                  <input
                    type="number"
                    step="100"
                    min="0"
                    value={formatCurrency(cost)}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        general_admin_costs: {
                          ...settings.general_admin_costs,
                          [key]: parseCurrency(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Depreciation & Amortization */}
        <section className="financial-settings-section">
          <h3>Depreciation & Amortization (Monthly)</h3>
          <div className="financial-settings-grid">
            {Object.entries(settings.depreciation_amortization).map(([key, amount]) => (
              <div key={key} className="financial-settings-field">
                <label>{key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')}</label>
                <div className="financial-settings-input-group">
                  <span className="financial-settings-currency">₹</span>
                  <input
                    type="number"
                    step="100"
                    min="0"
                    value={formatCurrency(amount)}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        depreciation_amortization: {
                          ...settings.depreciation_amortization,
                          [key]: parseCurrency(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Finance Costs */}
        <section className="financial-settings-section">
          <h3>Finance Costs (Monthly)</h3>
          <div className="financial-settings-grid">
            {Object.entries(settings.finance_costs).map(([key, cost]) => (
              <div key={key} className="financial-settings-field">
                <label>{key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')}</label>
                <div className="financial-settings-input-group">
                  <span className="financial-settings-currency">₹</span>
                  <input
                    type="number"
                    step="100"
                    min="0"
                    value={formatCurrency(cost)}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        finance_costs: {
                          ...settings.finance_costs,
                          [key]: parseCurrency(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Tax Settings */}
        <section className="financial-settings-section">
          <h3>Tax Settings</h3>
          <div className="financial-settings-grid">
            <div className="financial-settings-field">
              <label>Presumptive Tax Rate (%)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={(settings.tax_settings.presumptive_tax_rate * 100).toFixed(2)}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    tax_settings: {
                      ...settings.tax_settings,
                      presumptive_tax_rate: parseFloat(e.target.value) / 100,
                    },
                  })
                }
              />
            </div>
          </div>
        </section>
      </div>

      <div className="financial-settings-footer">
        <button
          className="financial-settings-save-btn"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}
