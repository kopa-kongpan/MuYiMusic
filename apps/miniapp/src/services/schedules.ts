import type { SchedulePublicListResponse } from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

interface ApiErrorResponse {
  message?: string
}

export interface PublicScheduleQuery {
  startsFrom: string
  startsBefore: string
}

export async function listPublicSchedules(
  storeId: string,
  query: PublicScheduleQuery,
): Promise<SchedulePublicListResponse> {
  const response = await Taro.request<
    SchedulePublicListResponse | ApiErrorResponse
  >({
    url: `${apiBaseUrl}/api/v1/app/stores/${storeId}/schedules`,
    method: 'GET',
    data: {
      starts_from: query.startsFrom,
      starts_before: query.startsBefore,
    },
  })
  if (response.statusCode < 200 || response.statusCode >= 300) {
    const error = response.data as ApiErrorResponse
    throw new Error(error.message ?? `排课加载失败（${response.statusCode}）`)
  }
  return response.data as SchedulePublicListResponse
}
