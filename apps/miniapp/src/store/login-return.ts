import Taro from '@tarojs/taro'

const LOGIN_RETURN_KEY = 'muyimusic.login.return'

export function setLoginReturn(url: string): void {
  Taro.setStorageSync(LOGIN_RETURN_KEY, url)
}

export function consumeLoginReturn(): string | null {
  const url = Taro.getStorageSync<string>(LOGIN_RETURN_KEY)
  Taro.removeStorageSync(LOGIN_RETURN_KEY)
  return typeof url === 'string' && url.startsWith('/') ? url : null
}
