/**
 * Main Application Component.
 * 
 * Defines routes and application structure.
 */

import { Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import PublicRoute from './components/PublicRoute';
import LandingPage from './pages/LandingPage';
import SignInPage from './pages/SignInPage';
import SignUpPage from './pages/SignUpPage';
import FeaturesPage from './pages/FeaturesPage';
import AboutPage from './pages/AboutPage';
import PricingPage from './pages/PricingPage';
import HomePage from './pages/HomePage';
import FinancialDashboard from './pages/FinancialDashboard';

/**
 * Main App Component.
 */
function App() {
  return (
    <AuthProvider>
      <div className="app">
        <Routes>
          {/* Auth pages - no navbar */}
          <Route
            path="/signin"
            element={(
              <PublicRoute>
                <SignInPage />
              </PublicRoute>
            )}
          />
          <Route
            path="/signup"
            element={(
              <PublicRoute>
                <SignUpPage />
              </PublicRoute>
            )}
          />
          
          {/* Authenticated home */}
          <Route
            path="/home"
            element={(
              <ProtectedRoute>
                <HomePage />
              </ProtectedRoute>
            )}
          />

          {/* Financial Dashboard */}
          <Route
            path="/financial"
            element={(
              <ProtectedRoute>
                <FinancialDashboard />
              </ProtectedRoute>
            )}
          />

          {/* Public pages with navbar */}
          <Route
            path="/*"
            element={(
              <PublicRoute>
                <MainLayout />
              </PublicRoute>
            )}
          />
        </Routes>
      </div>
    </AuthProvider>
  );
}

/**
 * Main Layout with Navbar.
 */
function MainLayout() {
  return (
    <>
      <Navbar />
      <main className="page">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/features" element={<FeaturesPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          {/* 404 - redirect to home for now */}
          <Route path="*" element={<LandingPage />} />
        </Routes>
      </main>
    </>
  );
}

export default App;
