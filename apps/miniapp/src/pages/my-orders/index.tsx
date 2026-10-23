import type { OrderRead, OrderStatus } from '@muyimusic/api-client'
import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import AppIcon from '../../components/AppIcon'
import { listMyOrders } from '../../services/user'
import { readCurrentStore } from '../../store/current-store'
import { readUserSession } from '../../store/user-session'
import '../shared/user-records.scss'

const statusLabels: Record<OrderStatus, string> = {
  pending: '待确认',
  confirmed: '已确认',
  cancelled: '已取消',
}

function formatMoney(value: number): string {
  return `¥${(value / 100).toFixed(2)}`
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function MyOrdersPage() {
  const [orders, setOrders] = useState<OrderRead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const store = readCurrentStore()
  const session = readUserSession()

  async function load() {
    if (!session) {
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const response = await listMyOrders(store?.id)
      setOrders(response.items)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '订单加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  useDidShow(() => {
    void load()
  })

  return (
    <View className="record-page">
      <View className="record-heading">
        <Text className="record-title">我的订单</Text>
        <Text className="record-store">{store?.name ?? '全部门店'}</Text>
      </View>

      {!session ? (
        <RecordState title="请先登录" copy="登录后可查看本人订单">
          <Button
            className="record-state-button"
            size="mini"
            onClick={() => void Taro.switchTab({ url: '/pages/me/index' })}
          >
            去登录
          </Button>
        </RecordState>
      ) : isLoading ? (
        <RecordState title="正在加载订单" copy="请稍候" />
      ) : errorMessage ? (
        <RecordState title="订单加载失败" copy={errorMessage}>
          <Button
            className="record-state-button"
            size="mini"
            onClick={() => void load()}
          >
            重试
          </Button>
        </RecordState>
      ) : orders.length === 0 ? (
        <RecordState
          title="暂无订单"
          copy="当前门店还没有可展示的订单"
        />
      ) : (
        <View className="record-list">
          {orders.map((order) => (
            <View className="record-card" key={order.id}>
              <View className="record-card-header">
                <Text className="record-card-title">{order.order_no}</Text>
                <Text
                  className={`record-status${order.status === 'confirmed' ? '' : ' record-status--muted'}`}
                >
                  {statusLabels[order.status]}
                </Text>
              </View>
              <Text className="record-card-meta">
                {order.store_name} · {formatTime(order.created_at)}
              </Text>
              <View className="record-lines">
                {order.items.map((item) => (
                  <View className="record-line" key={item.id}>
                    <Text className="record-line-title">
                      {item.product_name}
                    </Text>
                    <Text className="record-line-meta">
                      {item.sku_name} · {item.lesson_count} 课时 ×{' '}
                      {item.quantity}
                    </Text>
                  </View>
                ))}
              </View>
              <View className="record-card-footer">
                <Text>
                  共{' '}
                  {order.items.reduce(
                    (total, item) => total + item.quantity,
                    0,
                  )}{' '}
                  件
                </Text>
                <Text className="record-card-price">
                  {formatMoney(order.total_amount_cents)}
                </Text>
              </View>
              <View className="record-card-actions">
                <Button
                  className="record-secondary-button"
                  size="mini"
                  onClick={() =>
                    void Taro.navigateTo({
                      url: `/pages/order-detail/index?order_no=${encodeURIComponent(order.order_no)}`,
                    })
                  }
                >
                  查看订单
                </Button>
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  )
}

function RecordState(props: {
  title: string
  copy: string
  children?: React.ReactNode
}) {
  return (
    <View className="record-state">
      <AppIcon className="record-state-mark" name="orders" />
      <Text className="record-state-title">{props.title}</Text>
      <Text className="record-state-copy">{props.copy}</Text>
      {props.children}
    </View>
  )
}
