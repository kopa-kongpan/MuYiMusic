import type { components } from './generated/schema'

export type AdminRoleRead = components['schemas']['AdminRoleRead']
export type AdminStoreOption = components['schemas']['AdminStoreOption']
export type AdminUserCreate = components['schemas']['AdminUserCreate']
export type AdminUserListResponse =
  components['schemas']['AdminUserListResponse']
export type AdminUserOptionsResponse =
  components['schemas']['AdminUserOptionsResponse']
export type AdminUserPasswordReset =
  components['schemas']['AdminUserPasswordReset']
export type AdminUserRead = components['schemas']['AdminUserRead']
export type AdminUserUpdate = components['schemas']['AdminUserUpdate']
export type AdminLoginRequest = components['schemas']['AdminLoginRequest']
export type AdminProfile = components['schemas']['AdminProfile']
export type AdminTokenResponse = components['schemas']['AdminTokenResponse']
export type AppointmentAdminCancelRequest =
  components['schemas']['AppointmentAdminCancelRequest']
export type AppointmentCancelRequest =
  components['schemas']['AppointmentCancelRequest']
export type AppointmentCreate = components['schemas']['AppointmentCreate']
export type AppointmentListResponse =
  components['schemas']['AppointmentListResponse']
export type AppointmentRead = components['schemas']['AppointmentRead']
export type AppointmentStatus = components['schemas']['AppointmentStatus']
export type ConsumptionCreateRequest =
  components['schemas']['ConsumptionCreateRequest']
export type ConsumptionReverseRequest =
  components['schemas']['ConsumptionReverseRequest']
export type ScheduleCreate = components['schemas']['ScheduleCreate']
export type ScheduleListResponse = components['schemas']['ScheduleListResponse']
export type SchedulePublicListResponse =
  components['schemas']['SchedulePublicListResponse']
export type SchedulePublicRead = components['schemas']['SchedulePublicRead']
export type ScheduleRead = components['schemas']['ScheduleRead']
export type ScheduleStatus = components['schemas']['ScheduleStatus']
export type ScheduleStatusUpdate =
  components['schemas']['ScheduleStatusUpdate']
export type ScheduleUpdate = components['schemas']['ScheduleUpdate']
export type CourseEntitlementListResponse =
  components['schemas']['CourseEntitlementListResponse']
export type CourseEntitlementRead =
  components['schemas']['CourseEntitlementRead']
export type EntitlementStatus = components['schemas']['EntitlementStatus']
export type IdentityProvider = components['schemas']['IdentityProvider']
export type OrderListResponse = components['schemas']['OrderListResponse']
export type OrderRead = components['schemas']['OrderRead']
export type OrderStatus = components['schemas']['OrderStatus']
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
export type TeacherCreate = components['schemas']['TeacherCreate']
export type TeacherListResponse = components['schemas']['TeacherListResponse']
export type TeacherRead = components['schemas']['TeacherRead']
export type TeacherUpdate = components['schemas']['TeacherUpdate']
export type UploadTicketRequest = components['schemas']['UploadTicketRequest']
export type UploadTicketResponse = components['schemas']['UploadTicketResponse']
export type UserAdminListResponse =
  components['schemas']['UserAdminListResponse']
export type UserAdminRead = components['schemas']['UserAdminRead']
export type UserLoginRequest = components['schemas']['UserLoginRequest']
export type UserProfile = components['schemas']['UserProfile']
export type UserProfileUpdate = components['schemas']['UserProfileUpdate']
export type UserStatus = components['schemas']['UserStatus']
export type UserTokenResponse = components['schemas']['UserTokenResponse']

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

export interface UserOrderQuery {
  storeId?: string
  status?: OrderStatus
  page?: number
  pageSize?: number
}

export interface UserEntitlementQuery {
  storeId?: string
  status?: EntitlementStatus
  page?: number
  pageSize?: number
}

export interface AdminUserQuery {
  keyword?: string
  page?: number
  pageSize?: number
}

export interface AdminAccountQuery {
  keyword?: string
  isActive?: boolean
  page?: number
  pageSize?: number
}

export interface AdminTeacherQuery {
  keyword?: string
  isActive?: boolean
  page?: number
  pageSize?: number
}

export interface ScheduleQueryWindow {
  startsFrom: string
  startsBefore: string
}

export interface AdminScheduleQuery extends ScheduleQueryWindow {
  teacherId?: string
  status?: ScheduleStatus
  page?: number
  pageSize?: number
}

export interface UserAppointmentQuery {
  storeId?: string
  status?: AppointmentStatus
  page?: number
  pageSize?: number
}

export interface AdminAppointmentQuery extends ScheduleQueryWindow {
  status?: AppointmentStatus
  keyword?: string
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
    loginUser(payload: UserLoginRequest) {
      return request<UserTokenResponse>('/api/v1/app/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    getUserProfile() {
      return request<UserProfile>('/api/v1/app/me')
    },
    updateUserProfile(payload: UserProfileUpdate) {
      return request<UserProfile>('/api/v1/app/me', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
    },
    listMyOrders(query: UserOrderQuery = {}) {
      return request<OrderListResponse>(
        appendQuery('/api/v1/app/me/orders', {
          store_id: query.storeId,
          status: query.status,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    listMyCourseEntitlements(query: UserEntitlementQuery = {}) {
      return request<CourseEntitlementListResponse>(
        appendQuery('/api/v1/app/me/course-entitlements', {
          store_id: query.storeId,
          status: query.status,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    createAppointment(
      scheduleId: string,
      payload: AppointmentCreate,
      idempotencyKey: string,
    ) {
      return request<AppointmentRead>(
        `/api/v1/app/schedules/${scheduleId}/appointments`,
        {
          method: 'POST',
          headers: { 'Idempotency-Key': idempotencyKey },
          body: JSON.stringify(payload),
        },
      )
    },
    listMyAppointments(query: UserAppointmentQuery = {}) {
      return request<AppointmentListResponse>(
        appendQuery('/api/v1/app/me/appointments', {
          store_id: query.storeId,
          status: query.status,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    cancelMyAppointment(
      appointmentId: string,
      payload: AppointmentCancelRequest,
      idempotencyKey: string,
    ) {
      return request<AppointmentRead>(
        `/api/v1/app/me/appointments/${appointmentId}/cancel`,
        {
          method: 'POST',
          headers: { 'Idempotency-Key': idempotencyKey },
          body: JSON.stringify(payload),
        },
      )
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
    listAdminAccounts(query: AdminAccountQuery = {}) {
      return request<AdminUserListResponse>(
        appendQuery('/api/v1/admin/admin-users', {
          keyword: query.keyword,
          is_active:
            query.isActive === undefined ? undefined : String(query.isActive),
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    getAdminUserOptions() {
      return request<AdminUserOptionsResponse>('/api/v1/admin/admin-users/options')
    },
    createAdminUser(payload: AdminUserCreate) {
      return request<AdminUserRead>('/api/v1/admin/admin-users', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    updateAdminUser(adminUserId: string, payload: AdminUserUpdate) {
      return request<AdminUserRead>(
        `/api/v1/admin/admin-users/${adminUserId}`,
        {
          method: 'PATCH',
          body: JSON.stringify(payload),
        },
      )
    },
    resetAdminUserPassword(
      adminUserId: string,
      payload: AdminUserPasswordReset,
    ) {
      return request<AdminUserRead>(
        `/api/v1/admin/admin-users/${adminUserId}/reset-password`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
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
    listAdminTeachers(storeId: string, query: AdminTeacherQuery = {}) {
      return request<TeacherListResponse>(
        appendQuery(`/api/v1/admin/stores/${storeId}/teachers`, {
          keyword: query.keyword,
          is_active:
            query.isActive === undefined ? undefined : String(query.isActive),
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    createTeacher(storeId: string, payload: TeacherCreate) {
      return request<TeacherRead>(
        `/api/v1/admin/stores/${storeId}/teachers`,
        { method: 'POST', body: JSON.stringify(payload) },
      )
    },
    updateTeacher(
      storeId: string,
      teacherId: string,
      payload: TeacherUpdate,
    ) {
      return request<TeacherRead>(
        `/api/v1/admin/stores/${storeId}/teachers/${teacherId}`,
        { method: 'PATCH', body: JSON.stringify(payload) },
      )
    },
    listAdminSchedules(storeId: string, query: AdminScheduleQuery) {
      return request<ScheduleListResponse>(
        appendQuery(`/api/v1/admin/stores/${storeId}/schedules`, {
          starts_from: query.startsFrom,
          starts_before: query.startsBefore,
          teacher_id: query.teacherId,
          status: query.status,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    listAdminAppointments(storeId: string, query: AdminAppointmentQuery) {
      return request<AppointmentListResponse>(
        appendQuery(`/api/v1/admin/stores/${storeId}/appointments`, {
          starts_from: query.startsFrom,
          starts_before: query.startsBefore,
          status: query.status,
          keyword: query.keyword,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    cancelAdminAppointment(
      storeId: string,
      appointmentId: string,
      payload: AppointmentAdminCancelRequest,
      idempotencyKey: string,
    ) {
      return request<AppointmentRead>(
        `/api/v1/admin/stores/${storeId}/appointments/${appointmentId}/cancel`,
        {
          method: 'POST',
          headers: { 'Idempotency-Key': idempotencyKey },
          body: JSON.stringify(payload),
        },
      )
    },
    consumeAppointment(
      storeId: string,
      appointmentId: string,
      payload: ConsumptionCreateRequest,
      idempotencyKey: string,
    ) {
      return request<AppointmentRead>(
        `/api/v1/admin/stores/${storeId}/appointments/${appointmentId}/consume`,
        {
          method: 'POST',
          headers: { 'Idempotency-Key': idempotencyKey },
          body: JSON.stringify(payload),
        },
      )
    },
    markAppointmentNoShow(
      storeId: string,
      appointmentId: string,
      payload: ConsumptionCreateRequest,
      idempotencyKey: string,
    ) {
      return request<AppointmentRead>(
        `/api/v1/admin/stores/${storeId}/appointments/${appointmentId}/no-show`,
        {
          method: 'POST',
          headers: { 'Idempotency-Key': idempotencyKey },
          body: JSON.stringify(payload),
        },
      )
    },
    reverseConsumption(
      storeId: string,
      consumptionId: string,
      payload: ConsumptionReverseRequest,
      idempotencyKey: string,
    ) {
      return request<AppointmentRead>(
        `/api/v1/admin/stores/${storeId}/consumptions/${consumptionId}/reverse`,
        {
          method: 'POST',
          headers: { 'Idempotency-Key': idempotencyKey },
          body: JSON.stringify(payload),
        },
      )
    },
    createSchedule(storeId: string, payload: ScheduleCreate) {
      return request<ScheduleRead>(
        `/api/v1/admin/stores/${storeId}/schedules`,
        { method: 'POST', body: JSON.stringify(payload) },
      )
    },
    updateSchedule(
      storeId: string,
      scheduleId: string,
      payload: ScheduleUpdate,
    ) {
      return request<ScheduleRead>(
        `/api/v1/admin/stores/${storeId}/schedules/${scheduleId}`,
        { method: 'PATCH', body: JSON.stringify(payload) },
      )
    },
    changeScheduleStatus(
      storeId: string,
      scheduleId: string,
      payload: ScheduleStatusUpdate,
    ) {
      return request<ScheduleRead>(
        `/api/v1/admin/stores/${storeId}/schedules/${scheduleId}/status`,
        { method: 'POST', body: JSON.stringify(payload) },
      )
    },
    listAdminUsers(storeId: string, query: AdminUserQuery = {}) {
      return request<UserAdminListResponse>(
        appendQuery(`/api/v1/admin/stores/${storeId}/users`, {
          keyword: query.keyword,
          page: query.page,
          page_size: query.pageSize,
        }),
      )
    },
    listAdminUserOrders(
      storeId: string,
      userId: string,
      query: Omit<UserOrderQuery, 'storeId'> = {},
    ) {
      return request<OrderListResponse>(
        appendQuery(
          `/api/v1/admin/stores/${storeId}/users/${userId}/orders`,
          {
            status: query.status,
            page: query.page,
            page_size: query.pageSize,
          },
        ),
      )
    },
    listAdminUserCourseEntitlements(
      storeId: string,
      userId: string,
      query: Omit<UserEntitlementQuery, 'storeId'> = {},
    ) {
      return request<CourseEntitlementListResponse>(
        appendQuery(
          `/api/v1/admin/stores/${storeId}/users/${userId}/course-entitlements`,
          {
            status: query.status,
            page: query.page,
            page_size: query.pageSize,
          },
        ),
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
    listPublicSchedules(storeId: string, query: ScheduleQueryWindow) {
      return request<SchedulePublicListResponse>(
        appendQuery(`/api/v1/app/stores/${storeId}/schedules`, {
          starts_from: query.startsFrom,
          starts_before: query.startsBefore,
        }),
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
