import type { OrderDetailRead } from '@muyimusic/api-client'
import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { useState } from 'react'

import AppIcon from '../../components/AppIcon'
import { getPlatformAdapter } from '../../platform'
import { getMyOrder, loginCurrentUser } from '../../services/user'
import { setLoginReturn } from '../../store/login-return'
import { readUserSession } from '../../store/user-session'
import '../shared/user-records.scss'
import './index.scss'

function orderStatus(order: OrderDetailRead): string {
  if (order.payment_status === 'refunded') return '已退款'
  if (order.payment_status === 'succeeded') return '已支付'
  if (order.status === 'confirmed') return '已确认'
  if (order.status === 'cancelled') return '已取消'
  if (order.payment_status === 'closed') return '支付已关闭'
  if (order.payment_status === 'failed') return '支付失败'
  return '待支付'
}

function formatTime(value: string): string {
  const date = new Date(value)
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export default function OrderDetailPage() {
  const router = useRouter()
  const orderNumber = (router.params.order_no ?? '').trim()
  const [order, setOrder] = useState<OrderDetailRead | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [needsLogin, setNeedsLogin] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function load() {
    setIsLoading(true)
    setErrorMessage(null)
    setOrder(null)
    setNeedsLogin(false)
    try {
      if (!orderNumber || orderNumber.length > 64) {
        throw new Error('订单链接无效，请从“我的订单”进入')
      }
      if (!readUserSession()) {
        if (getPlatformAdapter().name !== 'weapp') {
          setNeedsLogin(true)
          return
        }
        // 微信订单中心冷启动时恢复本人身份，不要求填写头像、昵称或手机号。
        await loginCurrentUser()
      }
      setOrder(await getMyOrder(orderNumber))
    } catch (error) {
      setNeedsLogin(!readUserSession())
      setErrorMessage(error instanceof Error ? error.message : '订单加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  useDidShow(() => {
    void load()
  })

  function goToLogin() {
    setLoginReturn(
      `/pages/order-detail/index?order_no=${encodeURIComponent(orderNumber)}`,
    )
    void Taro.switchTab({ url: '/pages/me/index' })
  }

  async function contactStore() {
    if (!order) return
    try {
      await Taro.makePhoneCall({ phoneNumber: order.store_phone })
    } catch {
      await Taro.showToast({ title: '拨号未完成，可稍后重试', icon: 'none' })
    }
  }

  return (
    <View className="record-page">
      <View className="record-heading">
        <Text className="record-title">订单详情</Text>
        <Text className="record-store">
          {order?.store_name ?? '查看订单与售后服务'}
        </Text>
      </View>
      {isLoading ? (
        <View className="record-state">
          <AppIcon name="orders" className="record-state-mark" />
          <Text>正在加载订单…</Text>
        </View>
      ) : !order ? (
        <View className="record-state">
          <AppIcon name="orders" className="record-state-mark" />
          <Text className="record-state-title">
            {needsLogin ? '登录后查看本人订单' : '订单暂不可用'}
          </Text>
          <Text className="record-state-copy">
            {errorMessage ?? '请登录后继续查看'}
          </Text>
          <Button className="record-state-button" onClick={() => void load()}>
            重试
          </Button>
          {needsLogin ? (
            <Button className="record-secondary-button" onClick={goToLogin}>
              去登录
            </Button>
          ) : null}
        </View>
      ) : (
        <View className="record-list">
          <View className="record-card">
            <View className="record-card-header">
              <Text className="record-card-title">{orderStatus(order)}</Text>
              <Text className="record-card-price">
                ¥{(order.total_amount_cents / 100).toFixed(2)}
              </Text>
            </View>
            <Text className="order-detail-number">
              订单号：{order.order_no}
            </Text>
            <Text className="record-card-meta">
              下单时间：{formatTime(order.created_at)}
            </Text>
            {order.paid_at ? (
              <Text className="record-card-meta">
                支付时间：{formatTime(order.paid_at)}
              </Text>
            ) : null}
            <View className="record-lines">
              {order.items.map((item) => (
                <View className="record-line" key={item.id}>
                  <Text className="record-line-title">{item.product_name}</Text>
                  <Text className="record-line-meta">
                    {item.sku_name} · {item.lesson_count} 课时 × {item.quantity}
                  </Text>
                  <Text className="record-line-meta">
                    ¥{(item.total_amount_cents / 100).toFixed(2)}
                  </Text>
                </View>
              ))}
            </View>
            <View className="record-card-actions">
              <Button
                className="record-secondary-button"
                onClick={() => void load()}
              >
                刷新状态
              </Button>
            </View>
          </View>
          <View className="record-card">
            <Text className="record-line-title">售后服务</Text>
            <Text className="record-card-notice">
              退课、退款或课时问题，请联系订单所属门店，并提供上方订单号。
            </Text>
            <Text className="record-card-meta">
              {order.store_name} · {order.store_phone}
            </Text>
            <View className="record-card-actions">
              <Button
                className="record-state-button"
                onClick={() => void contactStore()}
              >
                联系门店
              </Button>
            </View>
          </View>
        </View>
      )}
    </View>
  )
}
