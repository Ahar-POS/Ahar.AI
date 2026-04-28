import { useState, useEffect, useRef, useCallback } from 'react';
import { getUnreadCount } from '../services/notifications';
import NotificationDropdown from './NotificationDropdown';
import './NotificationBell.css';

const POLL_MS = 30_000;

export default function NotificationBell() {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  const fetchCount = useCallback(async () => {
    try {
      const n = await getUnreadCount();
      setCount(n);
    } catch {
      // silently ignore — bell just shows 0
    }
  }, []);

  useEffect(() => {
    fetchCount();
    const id = setInterval(fetchCount, POLL_MS);
    return () => clearInterval(id);
  }, [fetchCount]);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleToggle = () => setOpen((prev) => !prev);

  const handleAllRead = () => {
    setCount(0);
    setOpen(false);
  };

  return (
    <div className="notif-bell-wrap" ref={bellRef}>
      <button
        type="button"
        className={`notif-bell-btn${open ? ' notif-bell-btn--open' : ''}`}
        onClick={handleToggle}
        aria-label={`Notifications${count > 0 ? ` (${count} unread)` : ''}`}
      >
        <BellIcon />
        {count > 0 && (
          <span className="notif-bell-badge">{count > 99 ? '99+' : count}</span>
        )}
      </button>

      {open && (
        <NotificationDropdown
          onAllRead={handleAllRead}
          onCountChange={setCount}
        />
      )}
    </div>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <path
        d="M9 1.5C6.515 1.5 4.5 3.515 4.5 6v3.75L3 11.25v.75h12v-.75L13.5 9.75V6c0-2.485-2.015-4.5-4.5-4.5z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M7.5 12.75a1.5 1.5 0 003 0"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
