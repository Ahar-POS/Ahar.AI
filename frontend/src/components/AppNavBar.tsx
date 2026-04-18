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
  userName?: string;
  onLogout: () => void;
}

export default function AppNavBar({
  screens,
  activeScreen,
  onScreenChange,
  restaurantName: _restaurantName,
  userName,
  onLogout,
}: AppNavBarProps) {
  const initials = userName ? userName.charAt(0).toUpperCase() : 'U';

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
        {userName && <span className="app-nav-user-name">{userName}</span>}
        <NotificationBell />
        <div className="app-nav-avatar">{initials}</div>
        <button type="button" className="app-nav-logout" onClick={onLogout}>
          Logout
        </button>
      </div>
    </nav>
  );
}
