import { useState, useEffect, useCallback } from 'react';
import {
  AppNotification,
  getNotifications,
  markRead,
  markAllRead,
} from '../services/notifications';
import './NotificationDropdown.css';

interface Props {
  onAllRead: () => void;
  onCountChange: (n: number) => void;
}

export default function NotificationDropdown({ onAllRead, onCountChange }: Props) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await getNotifications(1, 20);
      setItems(page.items);
      const unread = page.items.filter((n) => !n.is_read).length;
      onCountChange(unread);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

  useEffect(() => { load(); }, [load]);

  const handleMarkRead = async (id: string) => {
    await markRead(id);
    setItems((prev) =>
      prev.map((n) => (n.notification_id === id ? { ...n, is_read: true } : n))
    );
    onCountChange(items.filter((n) => !n.is_read && n.notification_id !== id).length);
  };

  const handleMarkAll = async () => {
    await markAllRead();
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    onAllRead();
  };

  const unreadCount = items.filter((n) => !n.is_read).length;

  return (
    <div className="notif-dropdown">
      <div className="notif-dropdown-header">
        <span className="notif-dropdown-title">Notifications</span>
        {unreadCount > 0 && (
          <button className="notif-mark-all-btn" onClick={handleMarkAll}>
            Mark all read
          </button>
        )}
      </div>

      <div className="notif-dropdown-list">
        {loading ? (
          <div className="notif-dropdown-empty">Loading…</div>
        ) : items.length === 0 ? (
          <div className="notif-dropdown-empty">No notifications</div>
        ) : (
          items.map((n) => (
            <NotifItem key={n.notification_id} item={n} onRead={handleMarkRead} />
          ))
        )}
      </div>
    </div>
  );
}

function NotifItem({
  item,
  onRead,
}: {
  item: AppNotification;
  onRead: (id: string) => void;
}) {
  const age = formatAge(item.created_at);

  return (
    <div
      className={`notif-item notif-item--${item.severity}${item.is_read ? ' notif-item--read' : ''}`}
      onClick={() => !item.is_read && onRead(item.notification_id)}
      role={item.is_read ? undefined : 'button'}
      tabIndex={item.is_read ? undefined : 0}
      onKeyDown={(e) => e.key === 'Enter' && !item.is_read && onRead(item.notification_id)}
    >
      <div className="notif-item-severity-bar" />
      <div className="notif-item-body">
        <div className="notif-item-title">{item.title}</div>
        <div className="notif-item-message">{item.message}</div>
        <div className="notif-item-age">{age}</div>
      </div>
      {!item.is_read && <div className="notif-item-dot" />}
    </div>
  );
}

function formatAge(iso: string): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
