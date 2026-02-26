import { ScreenId, ScreenDefinition } from '../types/navigation';
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
  restaurantName,
  userName,
  onLogout,
}: AppNavBarProps) {
  const initials = userName ? userName.charAt(0).toUpperCase() : 'U';

  return (
    <nav className="app-nav">
      <div className="app-nav-brand">
        <span className="app-nav-icon" aria-hidden="true">🍽️</span>
        <span className="app-nav-name">{restaurantName}</span>
      </div>

      <div className="app-nav-pills">
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
        <div className="app-nav-avatar">{initials}</div>
        <button type="button" className="app-nav-logout" onClick={onLogout}>
          Logout
        </button>
      </div>
    </nav>
  );
}
