/**
 * Sign Up Page Component.
 * 
 * Registration form for new users.
 */

import React, { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { validatePassword, PasswordValidation } from '../types/auth';
import BackButton from '../components/BackButton';
import './AuthPages.css';

/**
 * Sign Up Page.
 */
export default function SignUpPage() {
  const navigate = useNavigate();
  const { register, isLoading } = useAuth();
  
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
  });
  const [error, setError] = useState('');

  const passwordValidation: PasswordValidation = useMemo(
    () => validatePassword(formData.password),
    [formData.password]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!passwordValidation.isValid) {
      setError('Please enter a valid password');
      return;
    }

    try {
      await register({
        email: formData.email,
        password: formData.password,
        first_name: formData.firstName,
        last_name: formData.lastName,
      });
      navigate('/home');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    }
  };

  return (
    <div className="auth-page">
      {/* Mobile Back Button */}
      <BackButton className="back-button-auth" />
      
      <div className="auth-container">
        <div className="auth-card">
          {/* Header */}
          <div className="auth-header">
            <Link to="/" className="auth-logo">
              🍽️
            </Link>
            <h1 className="auth-title">Create your account</h1>
            <p className="auth-subtitle">Start your free trial today</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="auth-form">
            {error && (
              <div className="auth-error">
                {error}
              </div>
            )}

            <div className="form-row-split">
              <div className="form-group">
                <label htmlFor="firstName" className="form-label">
                  First Name
                </label>
                <input
                  type="text"
                  id="firstName"
                  name="firstName"
                  value={formData.firstName}
                  onChange={handleChange}
                  placeholder="John"
                  className="form-input"
                  required
                  autoComplete="given-name"
                  disabled={isLoading}
                />
              </div>

              <div className="form-group">
                <label htmlFor="lastName" className="form-label">
                  Last Name
                </label>
                <input
                  type="text"
                  id="lastName"
                  name="lastName"
                  value={formData.lastName}
                  onChange={handleChange}
                  placeholder="Doe"
                  className="form-input"
                  required
                  autoComplete="family-name"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="email" className="form-label">
                Email
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="you@example.com"
                className="form-input"
                required
                autoComplete="email"
                disabled={isLoading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password" className="form-label">
                Password
              </label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="••••••••"
                className={`form-input ${formData.password && !passwordValidation.isValid ? 'error' : ''}`}
                required
                autoComplete="new-password"
                disabled={isLoading}
              />
              
              {/* Password Strength Indicator */}
              {formData.password && (
                <div className="password-requirements">
                  <div className={`requirement ${passwordValidation.hasMinLength ? 'valid' : ''}`}>
                    <span className="requirement-icon">
                      {passwordValidation.hasMinLength ? '✓' : '○'}
                    </span>
                    At least 6 characters
                  </div>
                  <div className={`requirement ${passwordValidation.hasLetter ? 'valid' : ''}`}>
                    <span className="requirement-icon">
                      {passwordValidation.hasLetter ? '✓' : '○'}
                    </span>
                    Contains a letter
                  </div>
                  <div className={`requirement ${passwordValidation.hasNumber ? 'valid' : ''}`}>
                    <span className="requirement-icon">
                      {passwordValidation.hasNumber ? '✓' : '○'}
                    </span>
                    Contains a number
                  </div>
                </div>
              )}
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={isLoading || !passwordValidation.isValid}
            >
              {isLoading ? (
                <span className="spinner"></span>
              ) : (
                'Create Account'
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="auth-footer">
            <p>
              Already have an account?{' '}
              <Link to="/signin" className="link">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
