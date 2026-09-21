import type { SchedulePublicRead } from '@muyimusic/api-client'
import { Button, Image, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useRef, useState } from 'react'

import { appIcons } from '../../assets/icons'
import { createAppointment } from '../../services/appointments'
import { updateNotificationSubscription } from '../../services/notifications'
import { getPlatformAdapter } from '../../platform'
import { listPublicSchedules } from '../../services/schedules'
import { loginCurrentUser } from '../../services/user'
import { readCurrentStore } from '../../store/current-store'
import { readUserSession } from '../../store/user-session'
import './index.scss'

interface DateOption {
  value: string
  weekday: string
  label: string
}

function toDateValue(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function createDateOptions(): DateOption[] {
  const formatter = new Intl.DateTimeFormat('zh-CN', { weekday: 'short' })
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date()
    date.setHours(0, 0, 0, 0)
    date.setDate(date.getDate() + index)
    return {
      value: toDateValue(date),
      weekday: index === 0 ? '今天' : index === 1 ? '明天' : formatter.format(date),
      label: `${date.getMonth() + 1}/${date.getDate()}`,
    }
  })
}

function dayWindow(value: string): { startsFrom: string; startsBefore: string } {
  const startsFrom = new Date(`${value}T00:00:00`)
  const startsBefore = new Date(startsFrom)
  startsBefore.setDate(startsBefore.getDate() + 1)
  return {
    startsFrom: startsFrom.toISOString(),
    startsBefore: startsBefore.toISOString(),
  }
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export default function BookingPage() {
  const dateOptions = createDateOptions()
  const [selectedDate, setSelectedDate] = useState(dateOptions[0]!.value)
  const [schedules, setSchedules] = useState<SchedulePublicRead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [bookingScheduleId, setBookingScheduleId] = useState<string | null>(null)
  const requestSequence = useRef(0)

  async function loadSchedules(date = selectedDate) {
    const sequence = ++requestSequence.current
    const currentStore = readCurrentStore()
    if (!currentStore) {
      setSchedules([])
      setErrorMessage('请先选择门店')
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const response = await listPublicSchedules(currentStore.id, dayWindow(date))
      if (sequence !== requestSequence.current) return
      setSchedules(response.items)
    } catch (error) {
      if (sequence !== requestSequence.current) return
      setSchedules([])
      setErrorMessage(error instanceof Error ? error.message : '排课加载失败')
    } finally {
      if (sequence === requestSequence.current) setIsLoading(false)
    }
  }

  async function book(schedule: SchedulePublicRead) {
    setBookingScheduleId(schedule.id)
    try {
      if (!readUserSession()) {
        await loginCurrentUser()
      }
      let notificationSubscriptionFailed = false
      try {
        const adapter = getPlatformAdapter()
        if (adapter.name === 'weapp') {
          const templates = [
            [
              MUYIMUSIC_WECHAT_TEMPLATE_STUDENT_CANCELLED,
              'student_appointment_cancelled',
            ],
            [
              MUYIMUSIC_WECHAT_TEMPLATE_NEXT_DAY_REMINDER,
              'appointment_next_day_reminder',
            ],
          ].filter(([id]) => Boolean(id))
          if (templates.length > 0) {
            const result = await adapter.subscribeMessage(
              templates.map(([id]) => id!),
            )
            await Promise.all(
              templates.map(([id, key]) =>
                updateNotificationSubscription('weapp', key!, result[id!]!),
              ),
            )
          }
        }
      } catch {
        notificationSubscriptionFailed = true
      }
      await createAppointment(schedule.id)
      await Taro.showToast({
        title: notificationSubscriptionFailed ? '预约成功，微信通知未开启' : '预约成功',
        icon: notificationSubscriptionFailed ? 'none' : 'success',
      })
      await loadSchedules()
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '预约失败',
        icon: 'none',
      })
    } finally {
      setBookingScheduleId(null)
    }
  }

  useDidShow(() => {
    void loadSchedules()
  })

  usePullDownRefresh(() => {
    void loadSchedules().finally(() => Taro.stopPullDownRefresh())
  })

  const store = readCurrentStore()
  return (
    <View className="booking-page">
      <View className="booking-header">
        <View>
          <Text className="booking-title">预约</Text>
          <Text className="booking-store">{store?.name ?? '尚未选择门店'}</Text>
        </View>
        <Button
          className="booking-store-button"
          size="mini"
          onClick={() => void Taro.navigateTo({ url: '/pages/index/index' })}
        >
          切换门店
        </Button>
      </View>

      <ScrollView className="booking-date-scroll" scrollX enhanced showScrollbar={false}>
        <View className="booking-date-tabs">
          {dateOptions.map((option) => (
            <View
              className={`booking-date${selectedDate === option.value ? ' booking-date--active' : ''}`}
              key={option.value}
              onClick={() => {
                setSelectedDate(option.value)
                void loadSchedules(option.value)
              }}
            >
              <Text>{option.weekday}</Text>
              <Text>{option.label}</Text>
            </View>
          ))}
        </View>
      </ScrollView>

      <View className="booking-summary">
        <Text>可约时段</Text>
        <Text>{isLoading ? '加载中' : `${schedules.length} 节`}</Text>
      </View>

      {isLoading ? (
        <View className="booking-list">
          {[0, 1, 2].map((item) => (
            <View className="booking-skeleton" key={item}>
              <View />
              <View>
                <View />
                <View />
                <View />
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {!isLoading && errorMessage ? (
        <View className="booking-state booking-state--error">
          <Text className="booking-state-title">暂时无法加载排课</Text>
          <Text className="booking-state-copy">{errorMessage}</Text>
          <View className="booking-state-actions">
            <Button
              className="booking-retry-button"
              size="mini"
              onClick={() => void loadSchedules()}
            >
              重试
            </Button>
            {!store ? (
              <Button
                className="booking-select-store-button"
                size="mini"
                onClick={() => void Taro.navigateTo({ url: '/pages/index/index' })}
              >
                选择门店
              </Button>
            ) : null}
          </View>
        </View>
      ) : null}

      {!isLoading && !errorMessage && schedules.length === 0 ? (
        <View className="booking-state">
          <Image className="booking-state-mark" src={appIcons.schedule} mode="aspectFill" />
          <Text className="booking-state-title">当天暂无可约时段</Text>
          <Text className="booking-state-copy">请选择其他日期，或等待门店开放新排课</Text>
        </View>
      ) : null}

      {!isLoading && !errorMessage && schedules.length ? (
        <View className="booking-list">
          {schedules.map((schedule) => (
            <View className="booking-card" key={schedule.id}>
              <View className="booking-time">
                <Text>{formatTime(schedule.starts_at)}</Text>
                <Text>{formatTime(schedule.ends_at)}</Text>
              </View>
              <View className="booking-card-body">
                <Text className="booking-course-name">{schedule.course_name}</Text>
                <Text className="booking-teacher">教师 · {schedule.teacher_name}</Text>
                <Text className="booking-capacity">
                  剩余 {schedule.available_slots} / {schedule.capacity} 个名额
                </Text>
              </View>
              <Button
                className="booking-action-button"
                size="mini"
                disabled={!schedule.is_booking_open || bookingScheduleId !== null}
                loading={bookingScheduleId === schedule.id}
                onClick={() => void book(schedule)}
              >
                {schedule.available_slots === 0
                  ? '已满员'
                  : schedule.is_booking_open
                    ? readUserSession()
                      ? '预约'
                      : '登录预约'
                    : '已截止'}
              </Button>
            </View>
          ))}
          <Text className="booking-footnote">
            开课前 2 小时停止预约；预约后锁定 1 节课时，取消后自动释放
          </Text>
        </View>
      ) : null}
    </View>
  )
}
