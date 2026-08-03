import type { StorePublicRead } from '@muyimusic/api-client'
import Taro from '@tarojs/taro'

const CURRENT_STORE_KEY = 'muyimusic.current-store'

export function readCurrentStore(): StorePublicRead | null {
  try {
    const store = Taro.getStorageSync<StorePublicRead | null>(CURRENT_STORE_KEY)
    return store?.id ? store : null
  } catch {
    return null
  }
}

export function saveCurrentStore(store: StorePublicRead): void {
  Taro.setStorageSync(CURRENT_STORE_KEY, store)
}
