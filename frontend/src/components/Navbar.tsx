/**
 * Responsive Navigation Bar Component.
 * 
 * Displays navigation links and authentication buttons.
 * Collapses to hamburger menu on mobile.
 */

import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import BackButton from './BackButton';
import './Navbar.css';

/**
 * Navigation item interface.
 */
interface NavItem {
  label: string;
  path: string;
}

/**
 * Main navigation items.
 */
const navItems: NavItem[] = [
  { label: 'Features', path: '/features' },
  { label: 'About', path: '/about' },
  { label: 'Pricing', path: '/pricing' },
];

/**
 * Navbar Component.
 */
export default function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const location = useLocation();
  const { isAuthenticated, user, logout } = useAuth();

  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  const closeMenu = () => {
    setIsMenuOpen(false);
  };

  const handleLogout = async () => {
    await logout();
    closeMenu();
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="navbar">
      <div className="navbar-container">
        {/* Mobile Back Button */}
        <BackButton className="back-button-navbar" />
        
        {/* Logo */}
        <Link to="/" className="navbar-logo" onClick={closeMenu}>
          <span className="navbar-logo-icon">🍽️</span>
          <span className="navbar-logo-text">Ahar.AI</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="navbar-links hide-mobile">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`navbar-link ${isActive(item.path) ? 'active' : ''}`}
            >
              {item.label}
            </Link>
          ))}
        </div>

        {/* Desktop Auth Buttons */}
        <div className="navbar-auth hide-mobile">
          {isAuthenticated ? (
            <>
              <span className="navbar-user">
                Hi, {user?.first_name}
              </span>
              <button onClick={handleLogout} className="btn btn-ghost">
                Sign Out
              </button>
            </>
          ) : (
            <>
              <Link to="/signin" className="btn btn-ghost">
                Sign In
              </Link>
              <Link to="/signup" className="btn btn-primary">
                Sign Up
              </Link>
            </>
          )}
        </div>

        {/* Mobile Menu Button */}
        <button
          className="navbar-menu-btn show-mobile"
          onClick={toggleMenu}
          aria-label={isMenuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={isMenuOpen}
        >
          <span className={`hamburger ${isMenuOpen ? 'open' : ''}`}>
            <span></span>
            <span></span>
            <span></span>
          </span>
        </button>
      </div>

      {/* Mobile Menu */}
      <div className={`navbar-mobile-menu ${isMenuOpen ? 'open' : ''}`}>
        <div className="navbar-mobile-links">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`navbar-mobile-link ${isActive(item.path) ? 'active' : ''}`}
              onClick={closeMenu}
            >
              {item.label}
            </Link>
          ))}
        </div>
        
        <div className="navbar-mobile-divider"></div>
        
        <div className="navbar-mobile-auth">
          {isAuthenticated ? (
            <>
              <span className="navbar-mobile-user">
                Signed in as {user?.email}
              </span>
              <button onClick={handleLogout} className="btn btn-secondary btn-full">
                Sign Out
              </button>
            </>
          ) : (
            <>
              <Link to="/signin" className="btn btn-secondary btn-full" onClick={closeMenu}>
                Sign In
              </Link>
              <Link to="/signup" className="btn btn-primary btn-full" onClick={closeMenu}>
                Sign Up
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Mobile Menu Overlay */}
      {isMenuOpen && (
        <div className="navbar-overlay" onClick={closeMenu}></div>
      )}
    </nav>
  );
}
