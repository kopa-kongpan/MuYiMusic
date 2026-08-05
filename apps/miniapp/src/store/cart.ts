import Taro from '@tarojs/taro'

const CART_KEY_PREFIX = 'muyimusic.cart.'

export interface CartItem {
  productId: string
  productName: string
  skuId: string
  skuName: string
  quantity: number
  unitPriceCents: number
  coverUrl: string | null
  validatedAt: string
}

function cartKey(storeId: string): string {
  return `${CART_KEY_PREFIX}${storeId}`
}

export function readCart(storeId: string): CartItem[] {
  try {
    const items = Taro.getStorageSync<CartItem[] | null>(cartKey(storeId))
    return Array.isArray(items) ? items : []
  } catch {
    return []
  }
}

export function saveCart(storeId: string, items: CartItem[]): void {
  Taro.setStorageSync(cartKey(storeId), items)
}

export function addCartItem(storeId: string, item: CartItem): CartItem[] {
  const items = readCart(storeId)
  const existing = items.find(
    (current) =>
      current.productId === item.productId && current.skuId === item.skuId,
  )
  if (existing) {
    existing.quantity = Math.min(99, existing.quantity + item.quantity)
    existing.unitPriceCents = item.unitPriceCents
    existing.productName = item.productName
    existing.skuName = item.skuName
    existing.coverUrl = item.coverUrl
    existing.validatedAt = item.validatedAt
  } else {
    items.push(item)
  }
  saveCart(storeId, items)
  return items
}

export function updateCartItem(
  storeId: string,
  skuId: string,
  updates: Partial<Pick<CartItem, 'quantity' | 'unitPriceCents' | 'validatedAt'>>,
): CartItem[] {
  const items = readCart(storeId).map((item) =>
    item.skuId === skuId ? { ...item, ...updates } : item,
  )
  saveCart(storeId, items)
  return items
}

export function removeCartItem(storeId: string, skuId: string): CartItem[] {
  const items = readCart(storeId).filter((item) => item.skuId !== skuId)
  saveCart(storeId, items)
  return items
}

export function cartQuantity(storeId: string): number {
  return readCart(storeId).reduce((total, item) => total + item.quantity, 0)
}
