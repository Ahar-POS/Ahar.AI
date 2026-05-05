import { useRef, useEffect, useState } from 'react';
import { ScreenId, ScreenDefinition } from '../types/navigation';
import AharIcon from './AharIcon';
import NotificationBell from './NotificationBell';
import './AppNavBar.css';

interface AppNavBarProps {
  screens: ScreenDefinition[];
  activeScreen: ScreenId;
  onScreenChange: (id: ScreenId) => void;
  restaurantName: string;
  onLogout: () => void;
}

function KitchenIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M17 21a1 1 0 0 0 1-1v-5.35c0-.457.316-.844.727-1.041a4 4 0 0 0-2.134-7.589c-.06 0-.12.004-.179.011a5.5 5.5 0 0 0-10.828 0c-.06-.007-.12-.011-.18-.011a4 4 0 0 0-2.134 7.589c.411.197.727.584.727 1.041V20a1 1 0 0 0 1 1Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M6 17h12"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 5.33333C6.52624 5.33333 5.33333 6.52624 5.33333 8C5.33333 9.47376 6.52624 10.6667 8 10.6667C9.47376 10.6667 10.6667 9.47376 10.6667 8C10.6667 6.52624 9.47376 5.33333 8 5.33333Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12.9333 9.11333C12.9772 8.74619 13 8.37525 13 8C13 7.62475 12.9772 7.25381 12.9333 6.88667L14.4 5.76667L13.1333 3.56667L11.4133 4.26C11.0267 3.96667 10.6067 3.72667 10.1533 3.54L9.89333 1.71333H7.35333L7.09333 3.54C6.64 3.72667 6.22 3.96667 5.83333 4.26L4.11333 3.56667L2.84667 5.76667L4.31333 6.88667C4.26941 7.25381 4.24667 7.62475 4.24667 8C4.24667 8.37525 4.26941 8.74619 4.31333 9.11333L2.84667 10.2333L4.11333 12.4333L5.83333 11.74C6.22 12.0333 6.64 12.2733 7.09333 12.46L7.35333 14.2867H9.89333L10.1533 12.46C10.6067 12.2733 11.0267 12.0333 11.4133 11.74L13.1333 12.4333L14.4 10.2333L12.9333 9.11333Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function AppNavBar({
  screens,
  activeScreen,
  onScreenChange,
  restaurantName: _restaurantName,
  onLogout,
}: AppNavBarProps) {
  const initials = 'U';

  const navRef = useRef<HTMLDivElement>(null);
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 0, opacity: 0 });

  useEffect(() => {
    const updatePill = () => {
      if (navRef.current) {
        const activeEl = navRef.current.querySelector('.app-nav-pill--active') as HTMLElement;
        if (activeEl) {
          setPillStyle({
            left: activeEl.offsetLeft,
            width: activeEl.offsetWidth,
            opacity: 1
          });
        } else {
          setPillStyle(prev => ({ ...prev, opacity: 0 }));
        }
      }
    };

    updatePill();

    window.addEventListener('resize', updatePill);
    return () => window.removeEventListener('resize', updatePill);
  }, [activeScreen, screens]);

  return (
    <nav className="app-nav">
      <div className="app-nav-brand">
        <AharIcon size={24} className="app-nav-icon" />
        <span className="app-nav-name">Ahar</span>
      </div>

      <div className="app-nav-pills" ref={navRef}>
        <div
          className="app-nav-pill-highlight"
          style={{
            left: pillStyle.left,
            width: pillStyle.width,
            opacity: pillStyle.opacity
          }}
        />
        {screens.map((screen) => (
          <button
            key={screen.id}
            type="button"
            className={`app-nav-pill${activeScreen === screen.id ? ' app-nav-pill--active' : ''}`}
            onClick={() => onScreenChange(screen.id)}
          >
            {screen.label}
          </button>
        ))}
      </div>

      <div className="app-nav-user">
        <button
          type="button"
          className={`app-nav-tool-btn${activeScreen === 'outlet' ? ' app-nav-tool-btn--active' : ''}`}
          onClick={() => onScreenChange('outlet')}
          aria-label="Outlet"
          title="Outlet"
        >
          <KitchenIcon />
        </button>
        <NotificationBell />
        <button
          type="button"
          className={`app-nav-tool-btn${activeScreen === 'settings' ? ' app-nav-tool-btn--active' : ''}`}
          onClick={() => onScreenChange('settings')}
          aria-label="Settings"
          title="Settings"
        >
          <SettingsIcon />
        </button>
        <div className="app-nav-avatar">{initials}</div>
        <button type="button" className="app-nav-logout" onClick={onLogout}>
          Logout
        </button>
      </div>
    </nav>
  );
}
