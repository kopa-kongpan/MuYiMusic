import type { FranchisePagePublicRead } from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

export async function getFranchisePage(storeId: string): Promise<FranchisePagePublicRead> {
  const response = await Taro.request<FranchisePagePublicRead | { message?: string }>({
    url: `${apiBaseUrl}/api/v1/app/stores/${storeId}/franchise`,
    method: 'GET',
  })
  if (response.statusCode < 200 || response.statusCode >= 300) {
    const error = response.data as { message?: string }
    throw new Error(error.message ?? '加盟合作页面暂未发布')
  }
  return response.data as FranchisePagePublicRead
}
