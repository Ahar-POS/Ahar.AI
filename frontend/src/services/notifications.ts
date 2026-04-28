import api from './api';

export interface AppNotification {
  notification_id: string;
  type: string;
  title: string;
  message: string;
  severity: 'info' | 'warning' | 'high';
  target_roles: string[];
  metadata: Record<string, unknown>;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationsPage {
  items: AppNotification[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export async function getUnreadCount(): Promise<number> {
  const res = await api.get<{ success: boolean; data: { count: number } }>(
    '/notifications/unread-count'
  );
  return res.data.data?.count ?? 0;
}

export async function getNotifications(
  page = 1,
  limit = 20,
  unreadOnly = false
): Promise<NotificationsPage> {
  const res = await api.get('/notifications', {
    params: { page, limit, unread_only: unreadOnly },
  });
  const d = res.data;
  return {
    items: d.data ?? [],
    total: d.pagination?.total ?? 0,
    page: d.pagination?.page ?? page,
    limit: d.pagination?.limit ?? limit,
    total_pages: d.pagination?.total_pages ?? 1,
  };
}

export async function markRead(notificationId: string): Promise<void> {
  await api.put(`/notifications/${notificationId}/read`);
}

export async function markAllRead(): Promise<void> {
  await api.put('/notifications/mark-all-read');
}
