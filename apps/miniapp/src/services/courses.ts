import type {
  CategoryPublicRead,
  ProductPublicListResponse,
  ProductPublicRead,
  ProductSort,
  PurchaseValidationRequest,
  PurchaseValidationResponse,
} from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

const apiBaseUrl = MUYIMUSIC_API_BASE_URL.replace(/\/$/, '')

interface ApiErrorResponse {
  message?: string
}

export interface PublicProductQuery {
  keyword?: string
  categoryId?: string
  sort?: ProductSort
  page?: number
  pageSize?: number
}

function requireSuccess<T>(
  statusCode: number,
  data: T | ApiErrorResponse,
  fallback: string,
): T {
  if (statusCode < 200 || statusCode >= 300) {
    const error = data as ApiErrorResponse
    throw new Error(error.message ?? `${fallback}（${statusCode}）`)
  }
  return data as T
}

export async function listCourseCategories(
  storeId: string,
): Promise<CategoryPublicRead[]> {
  const response = await Taro.request<CategoryPublicRead[] | ApiErrorResponse>({
    url: `${apiBaseUrl}/api/v1/app/stores/${storeId}/categories`,
    method: 'GET',
  })
  return requireSuccess(response.statusCode, response.data, '分类加载失败')
}

export async function listCourseProducts(
  storeId: string,
  query: PublicProductQuery,
): Promise<ProductPublicListResponse> {
  const response = await Taro.request<
    ProductPublicListResponse | ApiErrorResponse
  >({
    url: `${apiBaseUrl}/api/v1/app/stores/${storeId}/products`,
    method: 'GET',
    data: {
      ...(query.keyword ? { keyword: query.keyword } : {}),
      ...(query.categoryId ? { category_id: query.categoryId } : {}),
      sort: query.sort ?? 'comprehensive',
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20,
    },
  })
  return requireSuccess(response.statusCode, response.data, '课程加载失败')
}

export async function getCourseProduct(
  storeId: string,
  productId: string,
): Promise<ProductPublicRead> {
  const response = await Taro.request<ProductPublicRead | ApiErrorResponse>({
    url: `${apiBaseUrl}/api/v1/app/stores/${storeId}/products/${productId}`,
    method: 'GET',
  })
  return requireSuccess(response.statusCode, response.data, '课程详情加载失败')
}

export async function validateCoursePurchase(
  storeId: string,
  productId: string,
  payload: PurchaseValidationRequest,
): Promise<PurchaseValidationResponse> {
  const response = await Taro.request<
    PurchaseValidationResponse | ApiErrorResponse
  >({
    url: `${apiBaseUrl}/api/v1/app/stores/${storeId}/products/${productId}/purchase-validation`,
    method: 'POST',
    data: payload,
  })
  return requireSuccess(response.statusCode, response.data, '课程价格校验失败')
}
