import type { UserTokenResponse } from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

const USER_SESSION_KEY = 'muyimusic.user.session'

export interface UserSession {
  accessToken: string
  expiresAt: number
  user: UserTokenResponse['user']
}

export function readUserSession(): UserSession | null {
  try {
    const session = Taro.getStorageSync<UserSession | null>(USER_SESSION_KEY)
    if (!session?.accessToken || !session.user?.id || session.expiresAt <= Date.now()) {
      clearUserSession()
      return null
    }
    return session
  } catch {
    return null
  }
}

export function saveUserSession(response: UserTokenResponse): UserSession {
  const session: UserSession = {
    accessToken: response.access_token,
    expiresAt: Date.now() + response.expires_in * 1000,
    user: response.user,
  }
  Taro.setStorageSync(USER_SESSION_KEY, session)
  return session
}

export function clearUserSession(): void {
  Taro.removeStorageSync(USER_SESSION_KEY)
}
