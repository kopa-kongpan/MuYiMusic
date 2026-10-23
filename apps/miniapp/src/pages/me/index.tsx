import { Button, Image, Text, View } from '@tarojs/components'
import type { ButtonProps } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { appIcons } from '../../assets/icons'
import AppIcon from '../../components/AppIcon'
import { bindCurrentUserPhone, loginCurrentUser } from '../../services/user'
import { listNotifications } from '../../services/notifications'
import { consumeLoginReturn } from '../../store/login-return'
import { readCurrentStore } from '../../store/current-store'
import {
  clearUserSession,
  readUserSession,
  type UserSession,
} from '../../store/user-session'
import './index.scss'

interface MeEntry {
  title: string
  url: string
  icon: string
}

const entries: MeEntry[] = [
  { title: '我的订单', url: '/pages/my-orders/index', icon: appIcons.orders },
  { title: '我的课程', url: '/pages/my-courses/index', icon: appIcons.headphones },
  { title: '我的课表', url: '/pages/schedule/index', icon: appIcons.myCourses },
  { title: '我的预约', url: '/pages/my-bookings/index', icon: appIcons.bookings },
  { title: '我的消息', url: '/pages/notifications/index', icon: appIcons.notifications },
  { title: '教师工作台', url: '/pages/teacher-portal/index', icon: appIcons.teacher },
]

export default function MePage() {
  const [session, setSession] = useState<UserSession | null>(null)
  const [isLoggingIn, setIsLoggingIn] = useState(false)
  const [isBindingPhone, setIsBindingPhone] = useState(false)
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
      await Taro.showToast({ title: '登录成功', icon: 'success', image: appIcons.check })
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

  async function bindPhone(
    event: Parameters<NonNullable<ButtonProps['onGetPhoneNumber']>>[0],
  ) {
    const code = event.detail.code
    if (!code) {
      await Taro.showToast({
        title: event.detail.errMsg.includes('deny')
          ? '你已取消手机号授权'
          : '未获得手机号授权凭证',
        icon: 'none',
      })
      return
    }
    setIsBindingPhone(true)
    try {
      const nextSession = await bindCurrentUserPhone(code)
      setSession(nextSession)
      await Taro.showToast({ title: '手机号绑定成功', icon: 'success', image: appIcons.check })
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '手机号绑定失败',
        icon: 'none',
      })
    } finally {
      setIsBindingPhone(false)
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
            <AppIcon className="me-avatar" name="profile" />
            <View className="me-profile-copy">
              <Text className="me-profile-name">{session.user.nickname}</Text>
              <View className="me-profile-meta-row">
                <Text className="me-profile-meta">
                  {session.user.phone ?? '尚未绑定手机号'}
                </Text>
                {!session.user.phone && process.env.TARO_ENV === 'weapp' ? (
                  <Button
                    className="me-phone-button"
                    size="mini"
                    openType="getPhoneNumber"
                    loading={isBindingPhone}
                    disabled={isBindingPhone}
                    onGetPhoneNumber={(event) => void bindPhone(event)}
                  >
                    绑定手机号
                  </Button>
                ) : null}
              </View>
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
                <Image className="me-entry-icon" src={entry.icon} mode="scaleToFill" aria-hidden="true" />
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
          <Image className="me-login-mark" src={appIcons.profile} mode="aspectFill" />
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
