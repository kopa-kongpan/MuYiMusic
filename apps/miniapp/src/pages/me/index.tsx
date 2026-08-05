import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { loginCurrentUser } from '../../services/user'
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
]

export default function MePage() {
  const [session, setSession] = useState<UserSession | null>(null)
  const [isLoggingIn, setIsLoggingIn] = useState(false)
  const store = readCurrentStore()

  useDidShow(() => {
    setSession(readUserSession())
  })

  async function login() {
    setIsLoggingIn(true)
    try {
      const nextSession = await loginCurrentUser()
      setSession(nextSession)
      await Taro.showToast({ title: '登录成功', icon: 'success' })
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
              </View>
            ))}
          </View>

          <View className="me-readonly-note">
            当前仅展示订单与课程权益，不提供在线支付、退款或课时调整。
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
