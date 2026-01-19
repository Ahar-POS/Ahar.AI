/**
 * Features Page Component.
 * 
 * Placeholder page showing upcoming features.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import './PlaceholderPages.css';

/**
 * Features Page.
 */
export default function FeaturesPage() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-content container">
        <span className="placeholder-icon">🚀</span>
        <h1 className="placeholder-title">Features</h1>
        <p className="placeholder-description">
          We're building powerful features to help you manage your restaurant efficiently.
          Check back soon for detailed information about our capabilities.
        </p>
        
        <div className="placeholder-features">
          <div className="placeholder-feature">
            <span className="placeholder-feature-icon">📊</span>
            <h3>Real-time Analytics</h3>
            <p>Coming soon</p>
          </div>
          <div className="placeholder-feature">
            <span className="placeholder-feature-icon">🍳</span>
            <h3>Kitchen Display System</h3>
            <p>Coming soon</p>
          </div>
          <div className="placeholder-feature">
            <span className="placeholder-feature-icon">💳</span>
            <h3>Payment Processing</h3>
            <p>Coming soon</p>
          </div>
          <div className="placeholder-feature">
            <span className="placeholder-feature-icon">📱</span>
            <h3>Mobile Ordering</h3>
            <p>Coming soon</p>
          </div>
        </div>

        <Link to="/signup" className="btn btn-primary btn-lg">
          Get Started
        </Link>
      </div>
    </div>
  );
}
