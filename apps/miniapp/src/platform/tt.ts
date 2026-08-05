import Taro from '@tarojs/taro'

import { createUnimplementedAdapter } from './create-unimplemented-adapter'

const fallback = createUnimplementedAdapter('tt')

export const ttAdapter = {
  ...fallback,
  async login() {
    const result = await Taro.login()
    if (!result.code) {
      throw new Error('抖音登录未返回有效凭证')
    }
    return { code: result.code }
  },
}
