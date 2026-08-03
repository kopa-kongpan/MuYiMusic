import type { StorePublicListResponse } from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

export interface PublicStoreQuery {
  keyword?: string
  latitude?: number
  longitude?: number
}

interface ApiErrorResponse {
  message?: string
}

export async function listPublicStores(
  query: PublicStoreQuery,
): Promise<StorePublicListResponse> {
  const data: PublicStoreQuery = {}
  if (query.keyword) {
    data.keyword = query.keyword
  }
  if (query.latitude !== undefined && query.longitude !== undefined) {
    data.latitude = query.latitude
    data.longitude = query.longitude
  }
  const response = await Taro.request<StorePublicListResponse | ApiErrorResponse>({
    url: `${apiBaseUrl}/api/v1/app/stores`,
    method: 'GET',
    data,
  })
  if (response.statusCode < 200 || response.statusCode >= 300) {
    const error = response.data as ApiErrorResponse
    throw new Error(error.message ?? `门店加载失败（${response.statusCode}）`)
  }
  return response.data as StorePublicListResponse
}
