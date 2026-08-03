import type { components } from './generated/schema'

export type AdminLoginRequest = components['schemas']['AdminLoginRequest']
export type AdminProfile = components['schemas']['AdminProfile']
export type AdminTokenResponse = components['schemas']['AdminTokenResponse']
export type StoreAdminListResponse =
  components['schemas']['StoreAdminListResponse']
export type StoreCreate = components['schemas']['StoreCreate']
export type StorePublicListResponse =
  components['schemas']['StorePublicListResponse']
export type StorePublicRead = components['schemas']['StorePublicRead']
export type StoreRead = components['schemas']['StoreRead']
export type StoreStatus = components['schemas']['StoreStatus']
export type StoreUpdate = components['schemas']['StoreUpdate']

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
    listPublicStores(query: PublicStoreQuery = {}) {
      return request<StorePublicListResponse>(
        appendQuery('/api/v1/app/stores', {
          keyword: query.keyword,
          latitude: query.latitude,
          longitude: query.longitude,
        }),
      )
    },
  }
}
