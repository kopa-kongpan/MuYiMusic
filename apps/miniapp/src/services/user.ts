import type {
  CourseEntitlementListResponse,
  OrderListResponse,
  UserTokenResponse,
} from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

import { getPlatformAdapter } from '../platform'
import {
  clearUserSession,
  readUserSession,
  saveUserSession,
  type UserSession,
} from '../store/user-session'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

interface ApiErrorResponse {
  message?: string
}

function requireSuccess<T>(
  statusCode: number,
  data: T | ApiErrorResponse,
  fallback: string,
): T {
  if (statusCode < 200 || statusCode >= 300) {
    if (statusCode === 401) {
      clearUserSession()
    }
    const error = data as ApiErrorResponse
    throw new Error(error.message ?? `${fallback}（${statusCode}）`)
  }
  return data as T
}

export async function loginCurrentUser(): Promise<UserSession> {
  const adapter = getPlatformAdapter()
  const loginResult = await adapter.login()
  const response = await Taro.request<UserTokenResponse | ApiErrorResponse>({
    url: `${apiBaseUrl}/api/v1/app/auth/login`,
    method: 'POST',
    data: {
      provider: adapter.name,
      code: loginResult.code,
    },
  })
  return saveUserSession(
    requireSuccess(response.statusCode, response.data, '登录失败'),
  )
}

async function authenticatedGet<T>(
  path: string,
  data: Record<string, string | number | undefined>,
  fallback: string,
): Promise<T> {
  const session = readUserSession()
  if (!session) {
    throw new Error('请先登录')
  }
  const response = await Taro.request<T | ApiErrorResponse>({
    url: `${apiBaseUrl}${path}`,
    method: 'GET',
    header: { Authorization: `Bearer ${session.accessToken}` },
    data,
  })
  return requireSuccess(response.statusCode, response.data, fallback)
}

export function listMyOrders(storeId?: string): Promise<OrderListResponse> {
  return authenticatedGet(
    '/api/v1/app/me/orders',
    { store_id: storeId, page: 1, page_size: 100 },
    '订单加载失败',
  )
}

export function listMyCourseEntitlements(
  storeId?: string,
): Promise<CourseEntitlementListResponse> {
  return authenticatedGet(
    '/api/v1/app/me/course-entitlements',
    { store_id: storeId, page: 1, page_size: 100 },
    '课程权益加载失败',
  )
}
