import type { components } from './generated/schema'

export type AdminLoginRequest = components['schemas']['AdminLoginRequest']
export type AdminProfile = components['schemas']['AdminProfile']
export type AdminTokenResponse = components['schemas']['AdminTokenResponse']
export type CategoryCreate = components['schemas']['CategoryCreate']
export type CategoryOrderUpdate = components['schemas']['CategoryOrderUpdate']
export type CategoryPublicRead = components['schemas']['CategoryPublicRead']
export type CategoryRead = components['schemas']['CategoryRead']
export type CategoryUpdate = components['schemas']['CategoryUpdate']
export type ContentBlockAdminListResponse =
  components['schemas']['ContentBlockAdminListResponse']
export type ContentBlockCreate = components['schemas']['ContentBlockCreate']
export type ContentBlockRead = components['schemas']['ContentBlockRead']
export type ContentBlockPublicRead = components['schemas']['ContentBlockPublicRead']
export type ContentBlockStatus = components['schemas']['ContentBlockStatus']
export type ContentBlockType = components['schemas']['ContentBlockType']
export type ContentBlockUpdate = components['schemas']['ContentBlockUpdate']
export type ContentJumpType = components['schemas']['ContentJumpType']
export type ContentOrderUpdate = components['schemas']['ContentOrderUpdate']
export type ProductAdminListResponse =
  components['schemas']['ProductAdminListResponse']
export type ProductCreate = components['schemas']['ProductCreate']
export type ProductImageRead = components['schemas']['ProductImageRead']
export type ProductPublicListItem =
  components['schemas']['ProductPublicListItem']
export type ProductPublicListResponse =
  components['schemas']['ProductPublicListResponse']
export type ProductPublicRead = components['schemas']['ProductPublicRead']
export type ProductRead = components['schemas']['ProductRead']
export type ProductSkuRead = components['schemas']['ProductSkuRead']
export type ProductSort = components['schemas']['ProductSort']
export type ProductStatus = components['schemas']['ProductStatus']
export type ProductStatusUpdate = components['schemas']['ProductStatusUpdate']
export type ProductUpdate = components['schemas']['ProductUpdate']
export type PurchaseValidationRequest =
  components['schemas']['PurchaseValidationRequest']
export type PurchaseValidationResponse =
  components['schemas']['PurchaseValidationResponse']
export type StoreAdminListResponse =
  components['schemas']['StoreAdminListResponse']
export type StoreCreate = components['schemas']['StoreCreate']
export type StorePublicListResponse =
  components['schemas']['StorePublicListResponse']
export type StorePublicRead = components['schemas']['StorePublicRead']
export type StoreRead = components['schemas']['StoreRead']
export type StoreStatus = components['schemas']['StoreStatus']
export type StoreHomeResponse = components['schemas']['StoreHomeResponse']
export type StoreUpdate = components['schemas']['StoreUpdate']
export type UploadTicketRequest = components['schemas']['UploadTicketRequest']
export type UploadTicketResponse = components['schemas']['UploadTicketResponse']

interface ApiErrorBody {
  code?: string
  message?: string
  request_id?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly requestId?: string

  constructor(status: number, body: ApiErrorBody) {
    super(body.message ?? `请求失败（${status}）`)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.requestId = body.request_id
  }
}

export interface ApiClientOptions {
  baseUrl?: string
  getAccessToken?: () => string | null
}

export interface AdminStoreQuery {
  keyword?: string
  status?: StoreStatus
  page?: number
  pageSize?: number
}

export interface PublicStoreQuery {
  keyword?: string
  latitude?: number
  longitude?: number
}

export interface AdminContentQuery {
  blockType?: ContentBlockType
  status?: ContentBlockStatus
  page?: number
  pageSize?: number
}

export interface AdminProductQuery {
  keyword?: string
  categoryId?: string
  status?: ProductStatus
  page?: number
  pageSize?: number
}

export interface PublicProductQuery {
  keyword?: string
  categoryId?: string
  sort?: ProductSort
  page?: number
  pageSize?: number
}

function appendQuery(
  path: string,
  query: Record<string, string | number | undefined>,
): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const suffix = search.toString()
  return suffix ? `${path}?${suffix}` : path
}

export function createApiClient(options: ApiClientOptions = {}) {
  const baseUrl = options.baseUrl?.replace(/\/$/, '') ?? ''

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const token = options.getAccessToken?.()
    const headers = new Headers(init?.headers)
    headers.set('Accept', 'application/json')
    if (init?.body) {
      headers.set('Content-Type', 'application/json')
    }
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    const response = await fetch(`${baseUrl}${path}`, { ...init, headers })
    const body = (await response.json()) as T | ApiErrorBody
    if (!response.ok) {
      throw new ApiError(response.status, body as ApiErrorBody)
    }
    return body as T
  }

  return {
    login(payload: AdminLoginRequest) {
      return request<AdminTokenResponse>('/api/v1/admin/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    listAdminStores(query: AdminStoreQuery = {}) {
      return request<StoreAdminListResponse>(
        appendQuery('/api/v1/admin/stores', {
          keyword: query.keyword,
          status: query.status,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    createStore(payload: StoreCreate) {
      return request<StoreRead>('/api/v1/admin/stores', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    updateStore(storeId: string, payload: StoreUpdate) {
      return request<StoreRead>(`/api/v1/admin/stores/${storeId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
    },
    listStoreContent(storeId: string, query: AdminContentQuery = {}) {
      return request<ContentBlockAdminListResponse>(
        appendQuery(`/api/v1/admin/stores/${storeId}/home-content`, {
          block_type: query.blockType,
          status: query.status,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    createStoreContent(storeId: string, payload: ContentBlockCreate) {
      return request<ContentBlockRead>(
        `/api/v1/admin/stores/${storeId}/home-content`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )
    },
    updateStoreContent(
      storeId: string,
      contentId: string,
      payload: ContentBlockUpdate,
    ) {
      return request<ContentBlockRead>(
        `/api/v1/admin/stores/${storeId}/home-content/${contentId}`,
        {
          method: 'PATCH',
          body: JSON.stringify(payload),
        },
      )
    },
    reorderStoreContent(storeId: string, payload: ContentOrderUpdate) {
      return request<ContentBlockRead[]>(
        `/api/v1/admin/stores/${storeId}/home-content/order`,
        {
          method: 'PUT',
          body: JSON.stringify(payload),
        },
      )
    },
    createUploadTicket(payload: UploadTicketRequest) {
      return request<UploadTicketResponse>('/api/v1/admin/media/upload-tickets', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    listAdminCategories(storeId: string) {
      return request<CategoryRead[]>(
        `/api/v1/admin/stores/${storeId}/categories`,
      )
    },
    createCategory(storeId: string, payload: CategoryCreate) {
      return request<CategoryRead>(
        `/api/v1/admin/stores/${storeId}/categories`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )
    },
    updateCategory(
      storeId: string,
      categoryId: string,
      payload: CategoryUpdate,
    ) {
      return request<CategoryRead>(
        `/api/v1/admin/stores/${storeId}/categories/${categoryId}`,
        {
          method: 'PATCH',
          body: JSON.stringify(payload),
        },
      )
    },
    reorderCategories(storeId: string, payload: CategoryOrderUpdate) {
      return request<CategoryRead[]>(
        `/api/v1/admin/stores/${storeId}/categories/order`,
        {
          method: 'PUT',
          body: JSON.stringify(payload),
        },
      )
    },
    listAdminProducts(storeId: string, query: AdminProductQuery = {}) {
      return request<ProductAdminListResponse>(
        appendQuery(`/api/v1/admin/stores/${storeId}/products`, {
          keyword: query.keyword,
          category_id: query.categoryId,
          status: query.status,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    getAdminProduct(storeId: string, productId: string) {
      return request<ProductRead>(
        `/api/v1/admin/stores/${storeId}/products/${productId}`,
      )
    },
    createProduct(storeId: string, payload: ProductCreate) {
      return request<ProductRead>(
        `/api/v1/admin/stores/${storeId}/products`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )
    },
    updateProduct(storeId: string, productId: string, payload: ProductUpdate) {
      return request<ProductRead>(
        `/api/v1/admin/stores/${storeId}/products/${productId}`,
        {
          method: 'PATCH',
          body: JSON.stringify(payload),
        },
      )
    },
    changeProductStatus(
      storeId: string,
      productId: string,
      payload: ProductStatusUpdate,
    ) {
      return request<ProductRead>(
        `/api/v1/admin/stores/${storeId}/products/${productId}/status`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )
    },
    listPublicStores(query: PublicStoreQuery = {}) {
      return request<StorePublicListResponse>(
        appendQuery('/api/v1/app/stores', {
          keyword: query.keyword,
          latitude: query.latitude,
          longitude: query.longitude,
        }),
      )
    },
    getStoreHome(storeId: string) {
      return request<StoreHomeResponse>(`/api/v1/app/stores/${storeId}/home`)
    },
    listPublicCategories(storeId: string) {
      return request<CategoryPublicRead[]>(
        `/api/v1/app/stores/${storeId}/categories`,
      )
    },
    listPublicProducts(storeId: string, query: PublicProductQuery = {}) {
      return request<ProductPublicListResponse>(
        appendQuery(`/api/v1/app/stores/${storeId}/products`, {
          keyword: query.keyword,
          category_id: query.categoryId,
          sort: query.sort,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    getPublicProduct(storeId: string, productId: string) {
      return request<ProductPublicRead>(
        `/api/v1/app/stores/${storeId}/products/${productId}`,
      )
    },
    validatePurchase(
      storeId: string,
      productId: string,
      payload: PurchaseValidationRequest,
    ) {
      return request<PurchaseValidationResponse>(
        `/api/v1/app/stores/${storeId}/products/${productId}/purchase-validation`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )
    },
  }
}
