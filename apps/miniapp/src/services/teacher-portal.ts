import type { AppointmentListResponse, AppointmentRead } from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

import type { NotificationListResponse } from './notifications'
import { clearUserSession, readUserSession } from '../store/user-session'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

export interface TeacherIdentity {
  teacher_id: string
  store_id: string
  teacher_name: string
  provider: string
}

async function request<T>(
  path: string,
  method: 'GET' | 'POST' = 'GET',
  data?: Record<string, unknown>,
  idempotencyKey?: string,
): Promise<T> {
  const session = readUserSession()
  if (!session) throw new Error('请先登录')
  const response = await Taro.request<T | { message?: string }>({
    url: `${apiBaseUrl}${path}`,
    method,
    data,
    header: {
      Authorization: `Bearer ${session.accessToken}`,
      ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
    },
  })
  if (response.statusCode < 200 || response.statusCode >= 300) {
    if (response.statusCode === 401) clearUserSession()
    throw new Error((response.data as { message?: string }).message ?? '教师操作失败')
  }
  return response.data as T
}

export function bindTeacher(code: string): Promise<TeacherIdentity> {
  return request('/api/v1/app/teacher/bind', 'POST', {
    code,
    provider: 'weapp',
  })
}

export async function listTeacherIdentities(): Promise<TeacherIdentity[]> {
  return (await request<{ items: TeacherIdentity[] }>('/api/v1/app/teacher/identities')).items
}

export function listTeacherAppointments(
  teacherId: string,
  startsFrom: string,
  startsBefore: string,
): Promise<AppointmentListResponse> {
  return request(`/api/v1/app/teacher/${teacherId}/appointments`, 'GET', {
    starts_from: startsFrom,
    starts_before: startsBefore,
    page: 1,
    page_size: 100,
  })
}

export function listTeacherNotifications(
  teacherId: string,
): Promise<NotificationListResponse> {
  return request(`/api/v1/app/teacher/${teacherId}/notifications?page=1&page_size=100`)
}

export function cancelTeacherAppointment(
  teacherId: string,
  appointmentId: string,
  reason: string,
): Promise<AppointmentRead> {
  return request(
    `/api/v1/app/teacher/${teacherId}/appointments/${appointmentId}/cancel`,
    'POST',
    { reason },
    `teacher-cancel-${appointmentId}-${Date.now()}`,
  )
}
