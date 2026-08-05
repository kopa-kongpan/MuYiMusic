import type {
  AppointmentRead,
  AppointmentStatus,
} from '@muyimusic/api-client'
import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useState } from 'react'

import {
  cancelMyAppointment,
  listMyAppointments,
} from '../../services/appointments'
import { readCurrentStore } from '../../store/current-store'
import { setLoginReturn } from '../../store/login-return'
import { readUserSession } from '../../store/user-session'
import '../shared/user-records.scss'

const statusLabels: Record<AppointmentStatus, string> = {
  reserved: '已预约',
  cancelled: '已取消',
  completed: '已消课',
  no_show: '缺席扣课',
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export default function MyBookingsPage() {
  const [appointments, setAppointments] = useState<AppointmentRead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [cancellingId, setCancellingId] = useState<string | null>(null)
  const store = readCurrentStore()
  const session = readUserSession()

  async function load() {
    if (!readUserSession()) {
      setAppointments([])
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const response = await listMyAppointments(readCurrentStore()?.id)
      setAppointments(response.items)
    } catch (error) {
      setAppointments([])
      setErrorMessage(error instanceof Error ? error.message : '预约记录加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  async function cancel(appointment: AppointmentRead) {
    const result = await Taro.showModal({
      title: '取消预约',
      content: `${appointment.course_name} · ${formatDateTime(appointment.starts_at)}。取消后名额和锁定课时会立即释放。`,
      confirmText: '确认取消',
      confirmColor: '#b64031',
    })
    if (!result.confirm) return
    setCancellingId(appointment.id)
    try {
      await cancelMyAppointment(appointment.id)
      await Taro.showToast({ title: '已取消预约', icon: 'success' })
      await load()
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '取消预约失败',
        icon: 'none',
      })
    } finally {
      setCancellingId(null)
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
      <RecordState mark="约" title="请先登录" copy="登录后可查看并管理本人预约">
        <Button
          className="record-state-button"
          size="mini"
          onClick={() => {
            setLoginReturn('/pages/my-bookings/index')
            void Taro.switchTab({ url: '/pages/me/index' })
          }}
        >
          去登录
        </Button>
      </RecordState>
    )
  } else if (isLoading) {
    content = <RecordState mark="约" title="正在加载预约" copy="请稍候" />
  } else if (errorMessage) {
    content = (
      <RecordState mark="约" title="预约加载失败" copy={errorMessage}>
        <Button className="record-state-button" size="mini" onClick={() => void load()}>
          重试
        </Button>
      </RecordState>
    )
  } else if (appointments.length === 0) {
    content = (
      <RecordState mark="约" title="暂无预约" copy="可在预约页选择合适的课程时段" />
    )
  } else {
    content = (
      <View className="record-list">
        {appointments.map((appointment) => (
          <View className="record-card" key={appointment.id}>
            <View className="record-card-header">
              <Text className="record-card-title">{appointment.course_name}</Text>
              <Text
                className={`record-status${appointment.status === 'reserved' ? '' : ' record-status--muted'}`}
              >
                {statusLabels[appointment.status]}
              </Text>
            </View>
            <Text className="record-card-meta">
              {formatDateTime(appointment.starts_at)} · {appointment.teacher_name}
            </Text>
            <Text className="record-card-meta">
              预约号：{appointment.appointment_no}
            </Text>
            <View className="record-course-progress">
              <Text>权益可用 / 锁定</Text>
              <Text>
                {appointment.entitlement_available_lessons} /{' '}
                {appointment.entitlement_reserved_lessons}
              </Text>
            </View>
            {appointment.cancellation_reason ? (
              <Text className="record-card-notice">
                取消原因：{appointment.cancellation_reason}
              </Text>
            ) : null}
            {appointment.can_user_cancel ? (
              <View className="record-card-actions">
                <Button
                  className="record-secondary-button record-secondary-button--danger"
                  size="mini"
                  loading={cancellingId === appointment.id}
                  disabled={cancellingId !== null}
                  onClick={() => void cancel(appointment)}
                >
                  取消预约
                </Button>
              </View>
            ) : null}
          </View>
        ))}
      </View>
    )
  }

  return (
    <View className="record-page">
      <View className="record-heading">
        <Text className="record-title">我的预约</Text>
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
