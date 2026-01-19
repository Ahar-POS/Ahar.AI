/**
 * About Page Component.
 * 
 * Placeholder page with company information.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import './PlaceholderPages.css';

/**
 * About Page.
 */
export default function AboutPage() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-content container">
        <span className="placeholder-icon">🍽️</span>
        <h1 className="placeholder-title">About Ahar.AI</h1>
        <p className="placeholder-description">
          We're on a mission to revolutionize restaurant management with artificial intelligence.
          Our platform helps restaurants streamline operations, reduce waste, and deliver 
          exceptional customer experiences.
        </p>
        
        <div className="placeholder-stats">
          <div className="placeholder-stat">
            <span className="stat-number">500+</span>
            <span className="stat-label">Restaurants</span>
          </div>
          <div className="placeholder-stat">
            <span className="stat-number">1M+</span>
            <span className="stat-label">Orders Processed</span>
          </div>
          <div className="placeholder-stat">
            <span className="stat-number">99.9%</span>
            <span className="stat-label">Uptime</span>
          </div>
        </div>

        <div className="placeholder-values">
          <h2>Our Values</h2>
          <ul>
            <li><strong>Innovation</strong> - Pushing the boundaries of what's possible</li>
            <li><strong>Reliability</strong> - Dependable systems you can count on</li>
            <li><strong>Simplicity</strong> - Powerful features, intuitive design</li>
          </ul>
        </div>

        <Link to="/signup" className="btn btn-primary btn-lg">
          Join Us Today
        </Link>
      </div>
    </div>
  );
}
