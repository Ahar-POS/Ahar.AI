/**
 * Pricing Page Component.
 * 
 * Placeholder page with pricing information.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import './PlaceholderPages.css';

/**
 * Pricing Page.
 */
export default function PricingPage() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-content container">
        <span className="placeholder-icon">💎</span>
        <h1 className="placeholder-title">Simple, Transparent Pricing</h1>
        <p className="placeholder-description">
          Start free, upgrade as you grow. No hidden fees, no surprises.
        </p>
        
        <div className="pricing-cards">
          <div className="pricing-card">
            <div className="pricing-header">
              <h3>Starter</h3>
              <div className="pricing-price">
                <span className="price-amount">Free</span>
              </div>
            </div>
            <ul className="pricing-features">
              <li>✓ Up to 50 orders/day</li>
              <li>✓ Basic analytics</li>
              <li>✓ 1 user account</li>
              <li>✓ Email support</li>
            </ul>
            <Link to="/signup" className="btn btn-secondary btn-full">
              Get Started
            </Link>
          </div>

          <div className="pricing-card featured">
            <div className="pricing-badge">Popular</div>
            <div className="pricing-header">
              <h3>Professional</h3>
              <div className="pricing-price">
                <span className="price-amount">$49</span>
                <span className="price-period">/month</span>
              </div>
            </div>
            <ul className="pricing-features">
              <li>✓ Unlimited orders</li>
              <li>✓ Advanced analytics</li>
              <li>✓ Up to 10 users</li>
              <li>✓ Kitchen display</li>
              <li>✓ Priority support</li>
            </ul>
            <Link to="/signup" className="btn btn-primary btn-full">
              Start Free Trial
            </Link>
          </div>

          <div className="pricing-card">
            <div className="pricing-header">
              <h3>Enterprise</h3>
              <div className="pricing-price">
                <span className="price-amount">Custom</span>
              </div>
            </div>
            <ul className="pricing-features">
              <li>✓ Everything in Pro</li>
              <li>✓ Multi-location</li>
              <li>✓ Unlimited users</li>
              <li>✓ Custom integrations</li>
              <li>✓ Dedicated support</li>
            </ul>
            <Link to="/about" className="btn btn-secondary btn-full">
              Contact Sales
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
