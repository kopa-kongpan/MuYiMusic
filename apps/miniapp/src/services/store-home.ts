import type { StoreHomeResponse } from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

interface ApiErrorResponse {
  message?: string
}

export async function getStoreHome(storeId: string): Promise<StoreHomeResponse> {
  const response = await Taro.request<StoreHomeResponse | ApiErrorResponse>({
    url: `${apiBaseUrl}/api/v1/app/stores/${storeId}/home`,
    method: 'GET',
  })
  if (response.statusCode < 200 || response.statusCode >= 300) {
    const error = response.data as ApiErrorResponse
    throw new Error(error.message ?? `门店首页加载失败（${response.statusCode}）`)
  }
  return response.data as StoreHomeResponse
}
