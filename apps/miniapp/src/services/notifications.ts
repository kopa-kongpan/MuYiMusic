import Taro from '@tarojs/taro'

import { clearUserSession, readUserSession } from '../store/user-session'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

export interface NotificationRead {
  id: string
  kind: string
  title: string
  content: string
  appointment_id?: string
  page_path?: string
  read_at?: string
  created_at: string
}

export interface NotificationListResponse {
  items: NotificationRead[]
  total: number
  unread_count: number
}

async function request<T>(
  path: string,
  method: 'GET' | 'POST' | 'PUT' = 'GET',
  data?: Record<string, unknown>,
): Promise<T> {
  const session = readUserSession()
  if (!session) throw new Error('请先登录')
  const response = await Taro.request<T | { message?: string }>({
    url: `${apiBaseUrl}${path}`,
    method,
    header: { Authorization: `Bearer ${session.accessToken}` },
    data,
  })
  if (response.statusCode < 200 || response.statusCode >= 300) {
    if (response.statusCode === 401) clearUserSession()
    throw new Error((response.data as { message?: string }).message ?? '消息操作失败')
  }
  return response.data as T
}

export function updateNotificationSubscription(
  provider: 'weapp' | 'tt',
  templateKey: string,
  status: 'accept' | 'reject' | 'ban',
): Promise<void> {
  return request('/api/v1/app/me/notifications/subscription', 'PUT', {
    provider,
    template_key: templateKey,
    status,
  })
}

export function listNotifications(): Promise<NotificationListResponse> {
  return request('/api/v1/app/me/notifications?page=1&page_size=100')
}

export function markNotificationRead(id: string): Promise<NotificationRead> {
  return request(`/api/v1/app/me/notifications/${id}/read`, 'POST')
}

export function markAllNotificationsRead(): Promise<void> {
  return request('/api/v1/app/me/notifications/read-all', 'POST')
}
