import Taro from '@tarojs/taro'

import { createUnimplementedAdapter } from './create-unimplemented-adapter'

const LOCAL_DEVICE_KEY = 'muyimusic.h5.local-device'
const fallback = createUnimplementedAdapter('h5')

function localDeviceCode(): string {
  const current = Taro.getStorageSync<string>(LOCAL_DEVICE_KEY)
  if (current && current.length >= 20) {
    return current
  }
  const next = `h5-${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
  Taro.setStorageSync(LOCAL_DEVICE_KEY, next)
  return next
}

export const h5Adapter = {
  ...fallback,
  async login() {
    return { code: localDeviceCode() }
  },
}
