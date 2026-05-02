/**
 * Home page — 4-screen AI-first layout.
 *
 * Admin users see all 4 screens with AppNavBar.
 * Staff users see Outlet Floor only (minimal header, no nav).
 */

import React, { useState, useMemo, lazy, Suspense, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { ScreenId, SCREEN_DEFINITIONS } from '../types/navigation';
import AppNavBar from '../components/AppNavBar';
import OwnerDashboard from '../components/OwnerDashboard';
import './HomePage.css';

const CommandCenterScreen = lazy(() => import('./screens/CommandCenterScreen'));
const OutletFloorScreen = lazy(() => import('./screens/OutletFloorScreen'));
const IntelligenceHubScreen = lazy(() => import('./screens/IntelligenceHubScreen'));
const InventoryScreen = lazy(() => import('./screens/InventoryScreen'));
const SettingsScreen = lazy(() => import('./screens/SettingsScreen'));

const RESTAURANT_NAME = "Lexi's Gourmet Sandwiches";

export default function HomePage() {
  const { user, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const isStaff = user?.role === 'staff';

  // Get initial screen from URL or default based on role
  const initialScreen = useMemo(() => {
    const screenParam = searchParams.get('screen') as ScreenId;
    
    // Special case for settings which is not in SCREEN_DEFINITIONS pills but is a valid screen
    if (screenParam === 'settings') return 'settings';

    if (screenParam && SCREEN_DEFINITIONS.some(s => s.id === screenParam)) {
      // Check if user has access to this screen
      const screenDef = SCREEN_DEFINITIONS.find(s => s.id === screenParam);
      if (!isStaff || (screenDef && !screenDef.adminOnly)) {
        return screenParam;
      }
    }
    return isStaff ? 'outlet' : 'command-center';
  }, [searchParams, isStaff]);

  const [activeScreen, setActiveScreen] = useState<ScreenId>(initialScreen);

  // Sync state with URL when it changes
  useEffect(() => {
    if (activeScreen !== initialScreen) {
      setActiveScreen(initialScreen);
    }
  }, [initialScreen, activeScreen]);

  const handleScreenChange = (id: ScreenId) => {
    setActiveScreen(id);
    setSearchParams({ screen: id }, { replace: true });
  };

  const visibleScreens = useMemo(() => {
    if (isStaff) return SCREEN_DEFINITIONS.filter((s) => !s.adminOnly);
    return SCREEN_DEFINITIONS;
  }, [isStaff]);

  const handleLogout = async () => {
    await logout();
  };

  /* Staff: Outlet only, minimal header */
  if (isStaff) {
    return (
      <div className="home-page home-page--immersive">
        <header className="home-staff-header">
          <div className="home-staff-brand">
            <span aria-hidden="true">🍽️</span>
            <span>{RESTAURANT_NAME}</span>
          </div>
          <button type="button" className="btn btn-ghost" onClick={handleLogout}>
            Logout
          </button>
        </header>
        <main className="home-screen">
          <Suspense fallback={<ScreenLoader />}>
            <OutletFloorScreen />
          </Suspense>
        </main>
      </div>
    );
  }

  /* Admin: full 4-screen layout */
  return (
    <div className="home-page home-page--immersive">
      <AppNavBar
        screens={visibleScreens}
        activeScreen={activeScreen}
        onScreenChange={handleScreenChange}
        restaurantName={RESTAURANT_NAME}
        onLogout={handleLogout}
      />
      <main className="home-screen">
        <Suspense fallback={<ScreenLoader />}>
          {renderScreen(activeScreen)}
        </Suspense>
      </main>
    </div>
  );
}

function renderScreen(id: ScreenId): React.ReactNode {
  switch (id) {
    case 'command-center':
      return <CommandCenterScreen />;
    case 'dashboard':
      return <OwnerDashboard />;
    case 'outlet':
      return <OutletFloorScreen />;
    case 'intelligence':
      return <IntelligenceHubScreen />;
    case 'inventory':
      return <InventoryScreen />;
    case 'settings':
      return <SettingsScreen />;
  }
}

function ScreenLoader() {
  return (
    <div className="home-screen-loader">
      <div className="spinner spinner-lg" />
    </div>
  );
}
