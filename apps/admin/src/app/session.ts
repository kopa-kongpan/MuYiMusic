import type { AdminProfile, AdminTokenResponse } from '@muyimusic/api-client'

const SESSION_KEY = 'muyimusic.admin.session'

export interface AdminSession {
  accessToken: string
  admin: AdminProfile
  expiresAt: number
}

export function getAdminSession(): AdminSession | null {
  const encodedSession = window.localStorage.getItem(SESSION_KEY)
  if (!encodedSession) {
    return null
  }
  try {
    const session = JSON.parse(encodedSession) as AdminSession
    if (!session.accessToken || !session.admin?.username) {
      clearAdminSession()
      return null
    }
    if (session.expiresAt <= Date.now()) {
      clearAdminSession()
      return null
    }
    return session
  } catch {
    clearAdminSession()
    return null
  }
}

export function saveAdminSession(response: AdminTokenResponse): void {
  const session: AdminSession = {
    accessToken: response.access_token,
    admin: response.admin,
    expiresAt: Date.now() + response.expires_in * 1000,
  }
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearAdminSession(): void {
  window.localStorage.removeItem(SESSION_KEY)
}
