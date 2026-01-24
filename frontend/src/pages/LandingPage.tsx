/**
 * Landing Page Component.
 * 
 * Hero section with call-to-action buttons.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './LandingPage.css';

/**
 * Feature card data.
 */
const features = [
  {
    icon: '📊',
    title: 'Real-time Analytics',
    description: 'Track sales, orders, and performance metrics in real-time.',
  },
  {
    icon: '🍳',
    title: 'Kitchen Display',
    description: 'Streamline kitchen operations with digital order management.',
  },
  {
    icon: '💳',
    title: 'Seamless Payments',
    description: 'Accept multiple payment methods with ease.',
  },
  {
    icon: '🤖',
    title: 'AI-Powered Insights',
    description: 'Get intelligent recommendations to optimize your business.',
  },
];

/**
 * Landing Page.
 */
export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="landing">
      {/* Hero Section */}
      <section className="hero">
        <div className="hero-background">
          <div className="hero-gradient"></div>
          <div className="hero-pattern"></div>
        </div>
        
        <div className="hero-content container">
          <span className="hero-badge">
            ✨ Powered by AI
          </span>
          
          <h1 className="hero-title">
            Restaurant POS<br />
            <span className="hero-title-accent">Made Intelligent</span>
          </h1>
          
          <p className="hero-description">
            AI-powered restaurant POS software for seamless front-of-house 
            to back-of-house management and kitchen coordination.
          </p>
          
          <div className="hero-actions">
            {isAuthenticated ? (
              <Link to="/home" className="btn btn-primary btn-lg">
                Go to Dashboard
              </Link>
            ) : (
              <>
                <Link to="/signup" className="btn btn-primary btn-lg">
                  Get Started Free
                </Link>
                <Link to="/features" className="btn btn-outline btn-lg">
                  Learn More
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      {/* Features Preview Section */}
      <section className="features-preview">
        <div className="container">
          <h2 className="section-title">Everything you need to run your restaurant</h2>
          <p className="section-description">
            From order management to analytics, we've got you covered.
          </p>
          
          <div className="features-grid">
            {features.map((feature, index) => (
              <div key={index} className="feature-card">
                <span className="feature-icon">{feature.icon}</span>
                <h3 className="feature-title">{feature.title}</h3>
                <p className="feature-description">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta-section">
        <div className="container">
          <div className="cta-card">
            <h2 className="cta-title">Ready to transform your restaurant?</h2>
            <p className="cta-description">
              Join thousands of restaurants using Ahar.AI to streamline operations.
            </p>
            <Link to="/signup" className="btn btn-primary btn-lg">
              Start Free Trial
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="footer">
        <div className="container">
          <div className="footer-content">
            <div className="footer-brand">
              <span className="footer-logo">🍽️ Ahar.AI</span>
              <p className="footer-tagline">
                Intelligent restaurant management for the modern age.
              </p>
            </div>
            <div className="footer-links">
              <Link to="/features">Features</Link>
              <Link to="/about">About</Link>
              <Link to="/pricing">Pricing</Link>
            </div>
          </div>
          <div className="footer-bottom">
            <p>&copy; 2026 Ahar.AI. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
