import type { PlatformAdapter, PlatformName } from './types'

function notImplemented(platform: PlatformName, capability: string): never {
  throw new Error(`${platform} platform capability is not implemented: ${capability}`)
}

export function createUnimplementedAdapter(
  name: PlatformName,
): PlatformAdapter {
  return {
    name,
    login: async () => notImplemented(name, 'login'),
    authorizePhone: async () => notImplemented(name, 'authorizePhone'),
    requestPayment: async () => notImplemented(name, 'requestPayment'),
    share: async () => notImplemented(name, 'share'),
    subscribeMessage: async () => notImplemented(name, 'subscribeMessage'),
    openCustomerService: async () =>
      notImplemented(name, 'openCustomerService'),
    getPlatformInfo: () => notImplemented(name, 'getPlatformInfo'),
  }
}

