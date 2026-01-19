/**
 * Back Button Component.
 * 
 * Industry-standard back navigation button for mobile viewports.
 * Uses browser history to navigate to the previous page.
 */

import { useNavigate, useLocation } from 'react-router-dom';
import './BackButton.css';

/**
 * Props for BackButton component.
 */
interface BackButtonProps {
  /** Additional CSS class for positioning variants */
  className?: string;
}

/**
 * BackButton Component.
 * 
 * Displays a back arrow that navigates to the previous page.
 * Only visible on mobile viewports and when there's history to go back to.
 */
export default function BackButton({ className = '' }: BackButtonProps) {
  const navigate = useNavigate();
  const location = useLocation();

  // Check if there's history to go back to
  // location.key is "default" when there's no history (initial page load)
  const canGoBack = location.key !== 'default';

  // Don't render if we're on home page or no history
  if (location.pathname === '/' || !canGoBack) {
    return null;
  }

  const handleBack = () => {
    navigate(-1);
  };

  return (
    <button
      className={`back-button ${className}`}
      onClick={handleBack}
      aria-label="Go back to previous page"
      type="button"
    >
      <svg
        className="back-button-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M15 18l-6-6 6-6" />
      </svg>
    </button>
  );
}
