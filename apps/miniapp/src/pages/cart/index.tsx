import { Button, Image, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { validateCoursePurchase } from '../../services/courses'
import {
  type CartItem,
  readCart,
  removeCartItem,
  updateCartItem,
} from '../../store/cart'
import { readCurrentStore } from '../../store/current-store'
import './index.scss'

function formatMoney(priceCents: number): string {
  return `¥${(priceCents / 100).toFixed(2)}`
}

export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>([])
  const [validatingSkuId, setValidatingSkuId] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const store = readCurrentStore()

  useDidShow(() => {
    setItems(store ? readCart(store.id) : [])
  })

  async function changeQuantity(item: CartItem, quantity: number) {
    if (!store || quantity < 1 || quantity > 99) {
      return
    }
    setValidatingSkuId(item.skuId)
    try {
      const validation = await validateCoursePurchase(store.id, item.productId, {
        sku_id: item.skuId,
        quantity,
      })
      setItems(
        updateCartItem(store.id, item.skuId, {
          quantity: validation.quantity,
          unitPriceCents: validation.unit_price_cents,
          validatedAt: validation.validated_at,
        }),
      )
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '数量更新失败',
        icon: 'none',
      })
    } finally {
      setValidatingSkuId(null)
    }
  }

  async function removeItem(item: CartItem) {
    if (!store) {
      return
    }
    const result = await Taro.showModal({
      title: '移除课程',
      content: `确认移除“${item.productName} · ${item.skuName}”？`,
      confirmText: '移除',
      confirmColor: '#b64031',
    })
    if (result.confirm) {
      setItems(removeCartItem(store.id, item.skuId))
    }
  }

  async function refreshPrices() {
    if (!store || items.length === 0) {
      return
    }
    setIsRefreshing(true)
    try {
      let nextItems = [...items]
      for (const item of items) {
        const validation = await validateCoursePurchase(store.id, item.productId, {
          sku_id: item.skuId,
          quantity: item.quantity,
        })
        nextItems = nextItems.map((current) =>
          current.skuId === item.skuId
            ? {
                ...current,
                productName: validation.product_name,
                skuName: validation.sku_name,
                unitPriceCents: validation.unit_price_cents,
                validatedAt: validation.validated_at,
              }
            : current,
        )
        setItems(nextItems)
        updateCartItem(store.id, item.skuId, {
          unitPriceCents: validation.unit_price_cents,
          validatedAt: validation.validated_at,
        })
      }
      await Taro.showToast({ title: '价格已更新', icon: 'success' })
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '价格更新失败',
        icon: 'none',
      })
    } finally {
      setIsRefreshing(false)
    }
  }

  const totalQuantity = items.reduce((total, item) => total + item.quantity, 0)
  const totalPrice = items.reduce(
    (total, item) => total + item.unitPriceCents * item.quantity,
    0,
  )

  return (
    <View className="cart-page">
      <View className="cart-heading">
        <View>
          <Text className="cart-title">购物车</Text>
          <Text className="cart-store">{store?.name ?? '尚未选择门店'}</Text>
        </View>
        {items.length ? <Text>{totalQuantity} 件</Text> : null}
      </View>

      {!store || items.length === 0 ? (
        <View className="cart-empty">
          <View className="cart-empty-mark">课</View>
          <Text className="cart-empty-title">购物车还是空的</Text>
          <Button
            className="cart-browse-button"
            size="mini"
            onClick={() => void Taro.switchTab({ url: '/pages/courses/index' })}
          >
            去选课程
          </Button>
        </View>
      ) : (
        <View className="cart-list">
          {items.map((item) => (
            <View className="cart-item" key={`${item.productId}:${item.skuId}`}>
              {item.coverUrl ? (
                <Image
                  className="cart-cover"
                  src={item.coverUrl}
                  mode="aspectFill"
                  onClick={() =>
                    void Taro.navigateTo({
                      url: `/pages/course-detail/index?id=${item.productId}`,
                    })
                  }
                />
              ) : (
                <View className="cart-cover cart-cover--empty">课程</View>
              )}
              <View className="cart-item-body">
                <Text className="cart-item-name">{item.productName}</Text>
                <Text className="cart-item-sku">{item.skuName}</Text>
                <View className="cart-item-bottom">
                  <Text className="cart-item-price">
                    {formatMoney(item.unitPriceCents)}
                  </Text>
                  <View className="cart-stepper">
                    <Button
                      size="mini"
                      disabled={item.quantity <= 1 || validatingSkuId === item.skuId}
                      aria-label={`减少${item.productName}数量`}
                      onClick={() => void changeQuantity(item, item.quantity - 1)}
                    >
                      −
                    </Button>
                    <Text>{item.quantity}</Text>
                    <Button
                      size="mini"
                      disabled={item.quantity >= 99 || validatingSkuId === item.skuId}
                      aria-label={`增加${item.productName}数量`}
                      onClick={() => void changeQuantity(item, item.quantity + 1)}
                    >
                      +
                    </Button>
                  </View>
                </View>
                <Button
                  className="cart-remove-button"
                  size="mini"
                  onClick={() => void removeItem(item)}
                >
                  移除
                </Button>
              </View>
            </View>
          ))}
        </View>
      )}

      {items.length ? (
        <View className="cart-summary-bar">
          <Button
            className="cart-refresh-button"
            size="mini"
            loading={isRefreshing}
            onClick={() => void refreshPrices()}
          >
            更新价格
          </Button>
          <View className="cart-total">
            <Text>合计</Text>
            <Text>{formatMoney(totalPrice)}</Text>
          </View>
          <Button
            className="cart-continue-button"
            size="mini"
            onClick={() => void Taro.switchTab({ url: '/pages/courses/index' })}
          >
            继续选课
          </Button>
        </View>
      ) : null}
    </View>
  )
}
