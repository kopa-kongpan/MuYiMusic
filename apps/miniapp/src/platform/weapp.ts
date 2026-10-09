import Taro from '@tarojs/taro'

import { createUnimplementedAdapter } from './create-unimplemented-adapter'
import type { SubscribeMessageStatus } from './types'

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
  async requestPayment(parameters: Readonly<Record<string, unknown>>) {
    const requestPayment = Taro.requestPayment as unknown as (options: {
      timeStamp: string
      nonceStr: string
      package: string
      signType: 'RSA'
      paySign: string
    }) => Promise<unknown>
    await requestPayment({
      timeStamp: String(parameters.timeStamp),
      nonceStr: String(parameters.nonceStr),
      package: String(parameters.package),
      signType: 'RSA',
      paySign: String(parameters.paySign),
    })
  },
  async subscribeMessage(templateIds: readonly string[]) {
    if (templateIds.length === 0) return {}
    const requestSubscribeMessage = Taro.requestSubscribeMessage as unknown as (
      options: { tmplIds: string[] },
    ) => Promise<Record<string, string>>
    const result = await requestSubscribeMessage({ tmplIds: [...templateIds] })
    return Object.fromEntries(
      templateIds.map((id) => [
        id,
        (result[id] === 'accept' || result[id] === 'ban'
          ? result[id]
          : 'reject') as SubscribeMessageStatus,
      ]),
    )
  },
}
