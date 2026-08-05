import type { AppointmentRead } from '@muyimusic/api-client'
import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useState } from 'react'

import { listMyAppointments } from '../../services/appointments'
import { readCurrentStore } from '../../store/current-store'
import { setLoginReturn } from '../../store/login-return'
import { readUserSession } from '../../store/user-session'
import '../shared/user-records.scss'

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  }).format(new Date(value))
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export default function SchedulePage() {
  const [appointments, setAppointments] = useState<AppointmentRead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const store = readCurrentStore()
  const session = readUserSession()

  async function load() {
    setCurrentTime(Date.now())
    if (!readUserSession()) {
      setAppointments([])
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const response = await listMyAppointments(
        readCurrentStore()?.id,
        'reserved',
      )
      setAppointments(
        [...response.items].sort(
          (left, right) =>
            new Date(left.starts_at).getTime() - new Date(right.starts_at).getTime(),
        ),
      )
    } catch (error) {
      setAppointments([])
      setErrorMessage(error instanceof Error ? error.message : '课表加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  useDidShow(() => {
    void load()
  })

  usePullDownRefresh(() => {
    void load().finally(() => Taro.stopPullDownRefresh())
  })

  let content: React.ReactNode
  if (!session) {
    content = (
      <RecordState mark="表" title="请先登录" copy="登录后可查看本人课程安排">
        <Button
          className="record-state-button"
          size="mini"
          onClick={() => {
            setLoginReturn('/pages/schedule/index')
            void Taro.switchTab({ url: '/pages/me/index' })
          }}
        >
          去登录
        </Button>
      </RecordState>
    )
  } else if (isLoading) {
    content = <RecordState mark="表" title="正在加载课表" copy="请稍候" />
  } else if (errorMessage) {
    content = (
      <RecordState mark="表" title="课表加载失败" copy={errorMessage}>
        <Button className="record-state-button" size="mini" onClick={() => void load()}>
          重试
        </Button>
      </RecordState>
    )
  } else if (appointments.length === 0) {
    content = (
      <RecordState mark="表" title="暂无课程安排" copy="预约成功的课程会出现在这里" />
    )
  } else {
    content = (
      <View className="record-list">
        {appointments.map((appointment) => {
          const hasEnded = new Date(appointment.ends_at).getTime() <= currentTime
          return (
            <View className="record-card record-schedule-card" key={appointment.id}>
              <View className="record-schedule-date">
                <Text>{formatDate(appointment.starts_at)}</Text>
                <Text>
                  {formatTime(appointment.starts_at)} - {formatTime(appointment.ends_at)}
                </Text>
              </View>
              <View className="record-card-header">
                <Text className="record-card-title">{appointment.course_name}</Text>
                <Text className={`record-status${hasEnded ? ' record-status--muted' : ''}`}>
                  {hasEnded ? '待门店处理' : '待上课'}
                </Text>
              </View>
              <Text className="record-card-meta">教师：{appointment.teacher_name}</Text>
              <Text className="record-card-meta">
                已锁定 1 节 · 当前可用 {appointment.entitlement_available_lessons} 节
              </Text>
            </View>
          )
        })}
      </View>
    )
  }

  return (
    <View className="record-page">
      <View className="record-heading">
        <Text className="record-title">我的课表</Text>
        <Text className="record-store">{store?.name ?? '全部门店'}</Text>
      </View>
      {content}
    </View>
  )
}

function RecordState(props: {
  mark: string
  title: string
  copy: string
  children?: React.ReactNode
}) {
  return (
    <View className="record-state">
      <View className="record-state-mark">{props.mark}</View>
      <Text className="record-state-title">{props.title}</Text>
      <Text className="record-state-copy">{props.copy}</Text>
      {props.children}
    </View>
  )
}
