import type {
  OrderCreate,
  OrderPaymentStatusResponse,
  OrderRead,
  WechatPaymentParameters,
} from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

import { clearUserSession, readUserSession } from '../store/user-session'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

interface ApiErrorResponse {
  message?: string
  detail?: string | Array<{ msg?: string }>
}

function apiErrorMessage(error: ApiErrorResponse): string | undefined {
  if (error.message) return error.message
  if (typeof error.detail === 'string') return error.detail
  if (Array.isArray(error.detail)) {
    return error.detail.map((item) => item.msg).filter(Boolean).join('；')
  }
  return undefined
}

function requireSuccess<T>(
  statusCode: number,
  data: T | ApiErrorResponse,
  fallback: string,
): T {
  if (statusCode < 200 || statusCode >= 300) {
    if (statusCode === 401) clearUserSession()
    const error = data as ApiErrorResponse
    throw new Error(apiErrorMessage(error) ?? `${fallback}（${statusCode}）`)
  }
  return data as T
}

function authorizationHeader(): Record<string, string> {
  const session = readUserSession()
  if (!session) throw new Error('请先登录')
  return { Authorization: `Bearer ${session.accessToken}` }
}

export async function createOrder(
  payload: OrderCreate,
  idempotencyKey: string,
): Promise<OrderRead> {
  const response = await Taro.request<OrderRead | ApiErrorResponse>({
    url: `${apiBaseUrl}/api/v1/app/orders`,
    method: 'POST',
    header: {
      ...authorizationHeader(),
      'Idempotency-Key': idempotencyKey,
    },
    data: payload,
  })
  return requireSuccess(response.statusCode, response.data, '创建订单失败')
}

export async function createWechatPayment(
  orderId: string,
): Promise<WechatPaymentParameters> {
  const response = await Taro.request<
    WechatPaymentParameters | ApiErrorResponse
  >({
    url: `${apiBaseUrl}/api/v1/app/orders/${orderId}/payments/wechat`,
    method: 'POST',
    header: authorizationHeader(),
  })
  return requireSuccess(response.statusCode, response.data, '创建微信支付失败')
}

export async function queryWechatPayment(
  orderId: string,
): Promise<OrderPaymentStatusResponse> {
  const response = await Taro.request<
    OrderPaymentStatusResponse | ApiErrorResponse
  >({
    url: `${apiBaseUrl}/api/v1/app/orders/${orderId}/payments/wechat/query`,
    method: 'POST',
    header: authorizationHeader(),
  })
  return requireSuccess(response.statusCode, response.data, '支付结果确认失败')
}
