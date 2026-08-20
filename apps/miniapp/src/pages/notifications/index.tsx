import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useState } from 'react'

import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationRead,
} from '../../services/notifications'
import { setLoginReturn } from '../../store/login-return'
import { readUserSession } from '../../store/user-session'
import '../shared/user-records.scss'
import './index.scss'

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationRead[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const session = readUserSession()

  async function load() {
    if (!readUserSession()) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await listNotifications()
      setItems(response.items)
      setUnreadCount(response.unread_count)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '消息加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function open(item: NotificationRead) {
    if (!item.read_at) {
      await markNotificationRead(item.id)
      setItems((current) =>
        current.map((value) =>
          value.id === item.id ? { ...value, read_at: new Date().toISOString() } : value,
        ),
      )
      setUnreadCount((count) => Math.max(0, count - 1))
    }
    if (item.page_path) await Taro.navigateTo({ url: `/${item.page_path}` })
  }

  async function readAll() {
    await markAllNotificationsRead()
    const readAt = new Date().toISOString()
    setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at ?? readAt })))
    setUnreadCount(0)
  }

  useDidShow(() => void load())
  usePullDownRefresh(() => void load().finally(() => Taro.stopPullDownRefresh()))

  if (!session) {
    return (
      <View className="record-page">
        <View className="record-state">
          <View className="record-state-mark">信</View>
          <Text className="record-state-title">请先登录</Text>
          <Text className="record-state-copy">登录后可查看课程通知</Text>
          <Button
            className="record-state-button"
            size="mini"
            onClick={() => {
              setLoginReturn('/pages/notifications/index')
              void Taro.switchTab({ url: '/pages/me/index' })
            }}
          >
            去登录
          </Button>
        </View>
      </View>
    )
  }

  return (
    <View className="record-page">
      <View className="notification-heading">
        <View>
          <Text className="record-title">我的消息</Text>
          <Text className="record-store">{unreadCount} 条未读</Text>
        </View>
        {unreadCount > 0 ? (
          <Button className="notification-read-all" size="mini" onClick={() => void readAll()}>
            全部已读
          </Button>
        ) : null}
      </View>
      {loading ? <MessageState title="正在加载消息" /> : null}
      {error ? <MessageState title="消息加载失败" copy={error} /> : null}
      {!loading && !error && items.length === 0 ? <MessageState title="暂无消息" copy="课程动态会出现在这里" /> : null}
      {!loading && !error && items.length > 0 ? (
        <View className="notification-list">
          {items.map((item) => (
            <View
              className={`notification-item${item.read_at ? '' : ' notification-item--unread'}`}
              key={item.id}
              hoverClass="notification-item--pressed"
              onClick={() => void open(item)}
            >
              <View className="notification-item-heading">
                <Text className="notification-item-title">{item.title}</Text>
                <Text className="notification-item-time">{formatTime(item.created_at)}</Text>
              </View>
              <Text className="notification-item-content">{item.content}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  )
}

function MessageState({ title, copy = '请稍候' }: { title: string; copy?: string }) {
  return (
    <View className="record-state">
      <View className="record-state-mark">信</View>
      <Text className="record-state-title">{title}</Text>
      <Text className="record-state-copy">{copy}</Text>
    </View>
  )
}
