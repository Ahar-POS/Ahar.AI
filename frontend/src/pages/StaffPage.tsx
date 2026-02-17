/**
 * StaffPage component.
 *
 * Admin-only page for managing staff accounts: create new staff users and
 * view/remove existing staff (same restaurant). Staff users inherit the
 * admin's restaurant and are assigned the "staff" role on the backend.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User } from '../types/auth';
import { createStaffUser, listStaffUsers, deleteStaffUser } from '../services/staff';
import { PasswordValidation, validatePassword } from '../types/auth';
import './SettingsPage.css';
import './StaffPage.css';

interface StaffFormState {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
}

/** Format ISO date for table display. */
function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

/**
 * Staff management page component.
 */
export default function StaffPage() {
  const { user } = useAuth();
  const [formData, setFormData] = useState<StaffFormState>({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [staffList, setStaffList] = useState<User[]>([]);
  const [loadingStaff, setLoadingStaff] = useState(true);
  const [removeConfirm, setRemoveConfirm] = useState<{ user: User } | null>(null);
  const [removing, setRemoving] = useState(false);

  const passwordValidation: PasswordValidation = useMemo(
    () => validatePassword(formData.password),
    [formData.password],
  );

  const loadStaff = useCallback(async () => {
    try {
      setLoadingStaff(true);
      const list = await listStaffUsers();
      setStaffList(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load staff list');
    } finally {
      setLoadingStaff(false);
    }
  }, []);

  useEffect(() => {
    loadStaff();
  }, [loadStaff]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
    setError(null);
    setSuccessMessage(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!passwordValidation.isValid) {
      setError('Please enter a valid password for the staff user.');
      return;
    }

    setSubmitting(true);
    try {
      await createStaffUser({
        email: formData.email,
        password: formData.password,
        first_name: formData.firstName,
        last_name: formData.lastName,
      });

      setSuccessMessage('Staff user created successfully.');
      setFormData({
        firstName: '',
        lastName: '',
        email: '',
        password: '',
      });
      await loadStaff();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to create staff user. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveClick = (staffUser: User) => {
    setRemoveConfirm({ user: staffUser });
  };

  const handleRemoveConfirm = async () => {
    if (!removeConfirm) return;
    setRemoving(true);
    setError(null);
    try {
      await deleteStaffUser(removeConfirm.user.id);
      setRemoveConfirm(null);
      await loadStaff();
      setSuccessMessage('Staff user removed successfully.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove staff user');
    } finally {
      setRemoving(false);
    }
  };

  const handleRemoveCancel = () => {
    if (!removing) setRemoveConfirm(null);
  };

  return (
    <div className="settings-page">
      <div className="settings-page-header">
        <div>
          <h1 className="settings-page-title">Staff Management</h1>
          <p className="settings-page-subtitle">
            Create staff accounts that can access Menu, Kitchen, Waiter, and Tables.
          </p>
        </div>

        <div className="settings-page-header-badge">
          <span className="settings-page-header-role">
            {user?.role === 'admin' ? 'Admin only' : 'Staff'}
          </span>
        </div>
      </div>

      <div className="settings-page-content">
        <section className="settings-section">
          <div className="settings-section-header">
            <h2 className="settings-section-title">Create Staff User</h2>
            <p className="settings-section-description">
              Staff users will inherit your restaurant and have limited access to
              operational screens only.
            </p>
          </div>

          <form className="settings-form" onSubmit={handleSubmit}>
            {error && (
              <div className="settings-alert settings-alert-error">
                <p>{error}</p>
              </div>
            )}

            {successMessage && (
              <div className="settings-alert settings-alert-success">
                <p>{successMessage}</p>
              </div>
            )}

            <div className="settings-form-row">
              <div className="settings-form-group">
                <label htmlFor="firstName" className="settings-form-label">
                  First Name
                </label>
                <input
                  id="firstName"
                  name="firstName"
                  type="text"
                  className="settings-form-input"
                  placeholder="Jane"
                  value={formData.firstName}
                  onChange={handleChange}
                  required
                  disabled={submitting}
                  autoComplete="given-name"
                />
              </div>

              <div className="settings-form-group">
                <label htmlFor="lastName" className="settings-form-label">
                  Last Name
                </label>
                <input
                  id="lastName"
                  name="lastName"
                  type="text"
                  className="settings-form-input"
                  placeholder="Doe"
                  value={formData.lastName}
                  onChange={handleChange}
                  required
                  disabled={submitting}
                  autoComplete="family-name"
                />
              </div>
            </div>

            <div className="settings-form-group">
              <label htmlFor="email" className="settings-form-label">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                className="settings-form-input"
                placeholder="staff@example.com"
                value={formData.email}
                onChange={handleChange}
                required
                disabled={submitting}
                autoComplete="email"
              />
            </div>

            <div className="settings-form-group">
              <label htmlFor="password" className="settings-form-label">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                className={`settings-form-input ${
                  formData.password && !passwordValidation.isValid ? 'error' : ''
                }`}
                placeholder="••••••••"
                value={formData.password}
                onChange={handleChange}
                required
                disabled={submitting}
                autoComplete="new-password"
              />

              {formData.password && (
                <div className="password-requirements">
                  <div
                    className={`requirement ${
                      passwordValidation.hasMinLength ? 'valid' : ''
                    }`}
                  >
                    <span className="requirement-icon">
                      {passwordValidation.hasMinLength ? '✓' : '○'}
                    </span>
                    At least 6 characters
                  </div>
                  <div
                    className={`requirement ${
                      passwordValidation.hasLetter ? 'valid' : ''
                    }`}
                  >
                    <span className="requirement-icon">
                      {passwordValidation.hasLetter ? '✓' : '○'}
                    </span>
                    Contains a letter
                  </div>
                  <div
                    className={`requirement ${
                      passwordValidation.hasNumber ? 'valid' : ''
                    }`}
                  >
                    <span className="requirement-icon">
                      {passwordValidation.hasNumber ? '✓' : '○'}
                    </span>
                    Contains a number
                  </div>
                </div>
              )}
            </div>

            <div className="settings-form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting || !passwordValidation.isValid}
              >
                {submitting ? 'Creating...' : 'Create Staff User'}
              </button>
            </div>
          </form>
        </section>

        <section className="settings-section staff-table-section">
          <div className="settings-section-header">
            <h2 className="settings-section-title">Staff List</h2>
            <p className="settings-section-description">
              Staff users for your restaurant. Removing a user permanently deletes their account.
            </p>
          </div>

          {loadingStaff ? (
            <div className="staff-table-loading">
              <div className="spinner" />
              <p>Loading staff...</p>
            </div>
          ) : staffList.length === 0 ? (
            <div className="staff-table-empty">
              <p>No staff users yet. Create one above.</p>
            </div>
          ) : (
            <div className="staff-table-card">
              <table className="staff-table" role="grid" aria-label="Staff users">
                <thead>
                  <tr>
                    <th scope="col">Email</th>
                    <th scope="col">First Name</th>
                    <th scope="col">Last Name</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {staffList.map((staffUser) => (
                    <tr key={staffUser.id}>
                      <td>{staffUser.email}</td>
                      <td>{staffUser.first_name}</td>
                      <td>{staffUser.last_name}</td>
                      <td>
                        <span className={`staff-status staff-status-${staffUser.status}`}>
                          {staffUser.status}
                        </span>
                      </td>
                      <td>{formatDate(staffUser.created_at)}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary staff-remove-btn"
                          onClick={() => handleRemoveClick(staffUser)}
                          disabled={removing}
                          aria-label={`Remove ${staffUser.email}`}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {removeConfirm && (
        <div
          className="modal-overlay"
          onClick={handleRemoveCancel}
          role="dialog"
          aria-modal="true"
          aria-labelledby="remove-staff-title"
        >
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 id="remove-staff-title">Remove Staff User</h2>
              <button
                type="button"
                className="modal-close"
                onClick={handleRemoveCancel}
                aria-label="Close"
                disabled={removing}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <p className="staff-remove-confirm-text">
                Are you sure you want to permanently remove{' '}
                <strong>{removeConfirm.user.email}</strong>? This cannot be undone
                and they will no longer be able to log in.
              </p>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleRemoveCancel}
                disabled={removing}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleRemoveConfirm}
                disabled={removing}
              >
                {removing ? 'Removing...' : 'Remove'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

