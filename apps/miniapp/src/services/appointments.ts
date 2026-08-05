import type {
  AppointmentListResponse,
  AppointmentRead,
  AppointmentStatus,
} from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

import { clearUserSession, readUserSession } from '../store/user-session'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

interface ApiErrorResponse {
  message?: string
}

function operationKey(prefix: string, resourceId: string): string {
  return `${prefix}-${resourceId}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

async function authenticatedRequest<T>(
  path: string,
  options: {
    method?: 'GET' | 'POST'
    data?: Record<string, unknown>
    idempotencyKey?: string
  },
  fallback: string,
): Promise<T> {
  const session = readUserSession()
  if (!session) throw new Error('请先登录')
  const response = await Taro.request<T | ApiErrorResponse>({
    url: `${apiBaseUrl}${path}`,
    method: options.method ?? 'GET',
    header: {
      Authorization: `Bearer ${session.accessToken}`,
      ...(options.idempotencyKey
        ? { 'Idempotency-Key': options.idempotencyKey }
        : {}),
    },
    data: options.data,
  })
  if (response.statusCode < 200 || response.statusCode >= 300) {
    if (response.statusCode === 401) clearUserSession()
    const error = response.data as ApiErrorResponse
    throw new Error(error.message ?? `${fallback}（${response.statusCode}）`)
  }
  return response.data as T
}

export function createAppointment(scheduleId: string): Promise<AppointmentRead> {
  return authenticatedRequest(
    `/api/v1/app/schedules/${scheduleId}/appointments`,
    {
      method: 'POST',
      data: {},
      idempotencyKey: operationKey('booking', scheduleId),
    },
    '预约失败',
  )
}

export function listMyAppointments(
  storeId?: string,
  status?: AppointmentStatus,
): Promise<AppointmentListResponse> {
  return authenticatedRequest(
    '/api/v1/app/me/appointments',
    {
      data: {
        store_id: storeId,
        status,
        page: 1,
        page_size: 100,
      },
    },
    '预约记录加载失败',
  )
}

export function cancelMyAppointment(
  appointmentId: string,
  reason?: string,
): Promise<AppointmentRead> {
  return authenticatedRequest(
    `/api/v1/app/me/appointments/${appointmentId}/cancel`,
    {
      method: 'POST',
      data: { reason },
      idempotencyKey: operationKey('cancel', appointmentId),
    },
    '取消预约失败',
  )
}
