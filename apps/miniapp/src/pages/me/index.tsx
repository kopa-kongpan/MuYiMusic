import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { loginCurrentUser } from '../../services/user'
import { listNotifications } from '../../services/notifications'
import { consumeLoginReturn } from '../../store/login-return'
import { readCurrentStore } from '../../store/current-store'
import {
  clearUserSession,
  readUserSession,
  type UserSession,
} from '../../store/user-session'
import './index.scss'

const entries = [
  { mark: '单', title: '我的订单', url: '/pages/my-orders/index' },
  { mark: '课', title: '我的课程', url: '/pages/my-courses/index' },
  { mark: '表', title: '我的课表', url: '/pages/schedule/index' },
  { mark: '约', title: '我的预约', url: '/pages/my-bookings/index' },
  { mark: '信', title: '我的消息', url: '/pages/notifications/index' },
  { mark: '师', title: '教师工作台', url: '/pages/teacher-portal/index' },
]

export default function MePage() {
  const [session, setSession] = useState<UserSession | null>(null)
  const [isLoggingIn, setIsLoggingIn] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const store = readCurrentStore()

  useDidShow(() => {
    const current = readUserSession()
    setSession(current)
    if (current) {
      void listNotifications()
        .then((result) => setUnreadCount(result.unread_count))
        .catch(() => setUnreadCount(0))
    } else {
      setUnreadCount(0)
    }
  })

  async function login() {
    setIsLoggingIn(true)
    try {
      const nextSession = await loginCurrentUser()
      setSession(nextSession)
      await Taro.showToast({ title: '登录成功', icon: 'success' })
      const returnUrl = consumeLoginReturn()
      if (returnUrl) {
        await Taro.navigateTo({ url: returnUrl })
      }
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '登录失败',
        icon: 'none',
      })
    } finally {
      setIsLoggingIn(false)
    }
  }

  async function logout() {
    const result = await Taro.showModal({
      title: '退出登录',
      content: '退出后仍会保留当前门店和购物车。',
      confirmText: '退出',
    })
    if (result.confirm) {
      clearUserSession()
      setSession(null)
    }
  }

  return (
    <View className="me-page">
      <View className="me-heading">
        <View>
          <Text className="me-title">我的</Text>
          <Text className="me-store">{store?.name ?? '尚未选择门店'}</Text>
        </View>
        <Button
          className="me-store-button"
          size="mini"
          onClick={() => void Taro.navigateTo({ url: '/pages/index/index' })}
        >
          {store ? '切换门店' : '选择门店'}
        </Button>
      </View>

      {session ? (
        <>
          <View className="me-profile-card">
            <View className="me-avatar" aria-hidden="true">
              {session.user.nickname.slice(0, 1)}
            </View>
            <View className="me-profile-copy">
              <Text className="me-profile-name">{session.user.nickname}</Text>
              <Text className="me-profile-meta">
                {session.user.phone ?? '尚未绑定手机号'}
              </Text>
            </View>
            <Button className="me-logout" size="mini" onClick={() => void logout()}>
              退出
            </Button>
          </View>

          <View className="me-entry-grid">
            {entries.map((entry) => (
              <View
                className="me-entry"
                key={entry.url}
                hoverClass="me-entry--pressed"
                onClick={() => void Taro.navigateTo({ url: entry.url })}
              >
                <View className="me-entry-mark">{entry.mark}</View>
                <Text>{entry.title}</Text>
                {entry.url === '/pages/notifications/index' && unreadCount > 0 ? (
                  <Text className="me-entry-badge">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </Text>
                ) : null}
              </View>
            ))}
          </View>

          <View className="me-readonly-note">
            预约成功后会锁定一节可用课时，课程结束并确认到课或缺席后扣减。
          </View>
        </>
      ) : (
        <View className="me-login-card">
          <View className="me-login-mark">我</View>
          <Text className="me-login-title">登录后查看学习记录</Text>
          <Text className="me-login-copy">订单与课程权益仅对本人可见</Text>
          <Button
            className="me-login-button"
            loading={isLoggingIn}
            disabled={isLoggingIn}
            onClick={() => void login()}
          >
            登录
          </Button>
        </View>
      )}
    </View>
  )
}
