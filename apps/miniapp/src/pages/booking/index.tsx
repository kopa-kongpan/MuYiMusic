import type { SchedulePublicRead } from '@muyimusic/api-client'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useState } from 'react'

import { listPublicSchedules } from '../../services/schedules'
import { readCurrentStore } from '../../store/current-store'
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

  async function loadSchedules(date = selectedDate) {
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
      setSchedules(response.items)
    } catch (error) {
      setSchedules([])
      setErrorMessage(error instanceof Error ? error.message : '排课加载失败')
    } finally {
      setIsLoading(false)
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
          <View className="booking-state-mark">约</View>
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
              <Button className="booking-disabled-button" size="mini" disabled>
                即将开放
              </Button>
            </View>
          ))}
          <Text className="booking-footnote">预约规则确认后开放在线预约</Text>
        </View>
      ) : null}
    </View>
  )
}
