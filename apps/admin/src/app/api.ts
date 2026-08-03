import { createApiClient } from '@muyimusic/api-client'

import { getAdminSession } from './session'

export const apiClient = createApiClient({
  getAccessToken: () => getAdminSession()?.accessToken ?? null,
})
