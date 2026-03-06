/**
 * Home page — 4-screen AI-first layout.
 *
 * Admin users see all 4 screens with AppNavBar.
 * Staff users see Operations Floor only (minimal header, no nav).
 */

import React, { useState, useMemo, lazy, Suspense } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ScreenId, SCREEN_DEFINITIONS } from '../types/navigation';
import AppNavBar from '../components/AppNavBar';
import './HomePage.css';

const CommandCenterScreen = lazy(() => import('./screens/CommandCenterScreen'));
const OperationsFloorScreen = lazy(() => import('./screens/OperationsFloorScreen'));
const InsightsPage = lazy(() => import('./InsightsPage'));
const SettingsScreen = lazy(() => import('./screens/SettingsScreen'));

const RESTAURANT_NAME = "Lexi's Gourmet Sandwiches";

export default function HomePage() {
  const { user, logout } = useAuth();
  const isStaff = user?.role === 'staff';

  const [activeScreen, setActiveScreen] = useState<ScreenId>(
    isStaff ? 'operations' : 'command-center'
  );

  const visibleScreens = useMemo(() => {
    if (isStaff) return SCREEN_DEFINITIONS.filter((s) => !s.adminOnly);
    return SCREEN_DEFINITIONS;
  }, [isStaff]);

  const handleLogout = async () => {
    await logout();
  };

  /* Staff: Operations only, minimal header */
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
            <OperationsFloorScreen />
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
        onScreenChange={setActiveScreen}
        restaurantName={RESTAURANT_NAME}
        userName={user?.first_name}
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
    case 'operations':
      return <OperationsFloorScreen />;
    case 'intelligence':
      return <InsightsPage />;
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
