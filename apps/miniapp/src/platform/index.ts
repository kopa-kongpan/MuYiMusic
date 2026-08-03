import { ttAdapter } from './tt'
import type { PlatformAdapter, PlatformName } from './types'
import { weappAdapter } from './weapp'

const adapters: Record<PlatformName, PlatformAdapter> = {
  tt: ttAdapter,
  weapp: weappAdapter,
}

export function getPlatformAdapter(): PlatformAdapter {
  const environment = process.env.TARO_ENV

  if (environment !== 'weapp' && environment !== 'tt') {
    throw new Error(`Unsupported miniapp platform: ${environment ?? 'unknown'}`)
  }

  return adapters[environment]
}

export type { PlatformAdapter, PlatformName } from './types'

