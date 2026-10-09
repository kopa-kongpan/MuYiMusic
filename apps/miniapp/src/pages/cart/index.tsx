import { Button, Image, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { getPlatformAdapter } from '../../platform'
import { validateCoursePurchase } from '../../services/courses'
import {
  createOrder,
  createWechatPayment,
  queryWechatPayment,
} from '../../services/payments'
import { loginCurrentUser } from '../../services/user'
import {
  type CartItem,
  checkoutIdempotencyKey,
  clearCart,
  readCart,
  removeCartItem,
  updateCartItem,
} from '../../store/cart'
import { readCurrentStore } from '../../store/current-store'
import { readUserSession } from '../../store/user-session'
import './index.scss'

function formatMoney(priceCents: number): string {
  return `¥${(priceCents / 100).toFixed(2)}`
}

export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>([])
  const [validatingSkuId, setValidatingSkuId] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isPaying, setIsPaying] = useState(false)
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

  async function pay() {
    if (!store || items.length === 0 || isPaying) return
    const adapter = getPlatformAdapter()
    if (adapter.name !== 'weapp') {
      await Taro.showToast({ title: '请在微信小程序中完成支付', icon: 'none' })
      return
    }
    setIsPaying(true)
    try {
      if (!readUserSession()) await loginCurrentUser()
      const order = await createOrder(
        {
          store_id: store.id,
          items: items.map((item) => ({
            product_id: item.productId,
            sku_id: item.skuId,
            quantity: item.quantity,
          })),
        },
        checkoutIdempotencyKey(store.id, items),
      )
      const payment = await createWechatPayment(order.id)
      await adapter.requestPayment(payment)
      let confirmed = false
      for (let attempt = 0; attempt < 6; attempt += 1) {
        if (attempt > 0) {
          await new Promise((resolve) => setTimeout(resolve, 1000))
        }
        const result = await queryWechatPayment(order.id)
        if (result.order_status === 'confirmed') {
          confirmed = true
          break
        }
      }
      if (confirmed) {
        clearCart(store.id)
        setItems([])
        await Taro.showToast({ title: '支付成功', icon: 'success' })
        await Taro.navigateTo({ url: '/pages/my-orders/index' })
      } else {
        await Taro.showModal({
          title: '支付结果确认中',
          content: '微信支付结果尚在同步，请稍后到“我的订单”查看。',
          showCancel: false,
        })
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : String(error ?? '支付失败')
      await Taro.showToast({
        title: message.includes('cancel') ? '已取消支付' : message,
        icon: 'none',
        duration: 3000,
      })
    } finally {
      setIsPaying(false)
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
            className="cart-pay-button"
            size="mini"
            loading={isPaying}
            disabled={isPaying}
            onClick={() => void pay()}
          >
            立即支付
          </Button>
        </View>
      ) : null}
    </View>
  )
}
