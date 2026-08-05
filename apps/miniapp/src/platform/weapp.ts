import Taro from '@tarojs/taro'

import { createUnimplementedAdapter } from './create-unimplemented-adapter'

const fallback = createUnimplementedAdapter('weapp')

export const weappAdapter = {
  ...fallback,
  async login() {
    const result = await Taro.login()
    if (!result.code) {
      throw new Error('微信登录未返回有效凭证')
    }
    return { code: result.code }
  },
}
