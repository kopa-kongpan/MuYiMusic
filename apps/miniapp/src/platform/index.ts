import { h5Adapter } from './h5'
import { ttAdapter } from './tt'
import type { PlatformAdapter, PlatformName } from './types'
import { weappAdapter } from './weapp'

const adapters: Record<PlatformName, PlatformAdapter> = {
  h5: h5Adapter,
  tt: ttAdapter,
  weapp: weappAdapter,
}

export function getPlatformAdapter(): PlatformAdapter {
  const environment = process.env.TARO_ENV

  if (environment !== 'weapp' && environment !== 'tt' && environment !== 'h5') {
    throw new Error(`Unsupported miniapp platform: ${environment ?? 'unknown'}`)
  }

  return adapters[environment]
}

export type { PlatformAdapter, PlatformName } from './types'
