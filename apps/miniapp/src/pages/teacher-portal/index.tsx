import { Button, Input, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useState } from 'react'

import type { AppointmentRead } from '@muyimusic/api-client'
import type { NotificationRead } from '../../services/notifications'
import { updateNotificationSubscription } from '../../services/notifications'
import { getPlatformAdapter } from '../../platform'
import {
  bindTeacher,
  cancelTeacherAppointment,
  listTeacherAppointments,
  listTeacherIdentities,
  listTeacherNotifications,
  type TeacherIdentity,
} from '../../services/teacher-portal'
import { readUserSession } from '../../store/user-session'
import '../shared/user-records.scss'
import './index.scss'

function todayWindow(): { startsFrom: string; startsBefore: string } {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  const end = new Date(start)
  end.setDate(end.getDate() + 1)
  return { startsFrom: start.toISOString(), startsBefore: end.toISOString() }
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export default function TeacherPortalPage() {
  const [identities, setIdentities] = useState<TeacherIdentity[]>([])
  const [selected, setSelected] = useState<TeacherIdentity | null>(null)
  const [appointments, setAppointments] = useState<AppointmentRead[]>([])
  const [notifications, setNotifications] = useState<NotificationRead[]>([])
  const [bindCode, setBindCode] = useState('')
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load(preferred?: TeacherIdentity) {
    if (!readUserSession()) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const nextIdentities = await listTeacherIdentities()
      const identity =
        preferred ??
        nextIdentities.find((item) => item.teacher_id === selected?.teacher_id) ??
        nextIdentities[0] ??
        null
      setIdentities(nextIdentities)
      setSelected(identity)
      if (!identity) {
        setAppointments([])
        setNotifications([])
        return
      }
      const window = todayWindow()
      const [appointmentResult, notificationResult] = await Promise.all([
        listTeacherAppointments(identity.teacher_id, window.startsFrom, window.startsBefore),
        listTeacherNotifications(identity.teacher_id),
      ])
      setAppointments(appointmentResult.items)
      setNotifications(notificationResult.items)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '教师工作台加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function submitBind() {
    if (bindCode.trim().length < 8) {
      await Taro.showToast({ title: '请输入有效绑定码', icon: 'none' })
      return
    }
    setWorking(true)
    try {
      const identity = await bindTeacher(bindCode.trim())
      setBindCode('')
      await Taro.showToast({ title: '教师身份绑定成功', icon: 'success' })
      await load(identity)
    } catch (reason) {
      await Taro.showToast({
        title: reason instanceof Error ? reason.message : '绑定失败',
        icon: 'none',
      })
    } finally {
      setWorking(false)
    }
  }

  async function cancel(item: AppointmentRead) {
    if (!selected) return
    const result = await Taro.showModal({
      title: '取消学员预约',
      content: `${item.user_nickname} · ${item.course_name}。取消后会通知学员并释放课时。`,
      confirmText: '确认取消',
      confirmColor: '#b64031',
    })
    if (!result.confirm) return
    setWorking(true)
    try {
      await cancelTeacherAppointment(
        selected.teacher_id,
        item.id,
        '教师取消课程',
      )
      await Taro.showToast({ title: '预约已取消', icon: 'success' })
      await load()
    } catch (reason) {
      await Taro.showToast({
        title: reason instanceof Error ? reason.message : '取消失败',
        icon: 'none',
      })
    } finally {
      setWorking(false)
    }
  }

  async function enableWechatNotifications() {
    const adapter = getPlatformAdapter()
    if (adapter.name !== 'weapp') {
      await Taro.showToast({ title: '请在微信小程序中开启', icon: 'none' })
      return
    }
    const templates = [
      [
        MUYIMUSIC_WECHAT_TEMPLATE_TEACHER_NEW_APPOINTMENT,
        'teacher_new_appointment',
      ],
      [
        MUYIMUSIC_WECHAT_TEMPLATE_TEACHER_CANCELLED,
        'teacher_appointment_cancelled',
      ],
    ].filter(([id]) => Boolean(id))
    if (templates.length === 0) {
      await Taro.showToast({ title: '微信通知模板尚未配置', icon: 'none' })
      return
    }
    try {
      const result = await adapter.subscribeMessage(
        templates.map(([id]) => id!),
      )
      await Promise.all(
        templates.map(([id, key]) =>
          updateNotificationSubscription('weapp', key!, result[id!]!),
        ),
      )
      await Taro.showToast({ title: '通知设置已更新', icon: 'success' })
    } catch (reason) {
      await Taro.showToast({
        title: reason instanceof Error ? reason.message : '通知设置失败',
        icon: 'none',
      })
    }
  }

  useDidShow(() => void load())
  usePullDownRefresh(() => void load().finally(() => Taro.stopPullDownRefresh()))

  if (!readUserSession()) {
    return <State title="请先登录" copy="登录后可绑定并使用教师工作台" />
  }

  if (loading) return <State title="正在加载教师工作台" copy="请稍候" />

  return (
    <View className="teacher-page">
      <View className="teacher-heading">
        <View>
          <Text className="teacher-title">教师工作台</Text>
          <Text className="teacher-subtitle">
            {selected?.teacher_name ?? '尚未绑定教师身份'}
          </Text>
        </View>
      </View>

      {error ? <State title="工作台加载失败" copy={error} /> : null}

      {!error && identities.length === 0 ? (
        <View className="teacher-bind">
          <Text className="teacher-section-title">绑定教师身份</Text>
          <Input
            className="teacher-bind-input"
            maxlength={32}
            placeholder="输入后台生成的绑定码"
            value={bindCode}
            onInput={(event) => setBindCode(event.detail.value)}
          />
          <Button
            className="teacher-primary-button"
            loading={working}
            disabled={working}
            onClick={() => void submitBind()}
          >
            确认绑定
          </Button>
        </View>
      ) : null}

      {!error && identities.length > 1 ? (
        <View className="teacher-identities">
          {identities.map((identity) => (
            <Button
              className={
                identity.teacher_id === selected?.teacher_id
                  ? 'teacher-identity teacher-identity--active'
                  : 'teacher-identity'
              }
              key={identity.teacher_id}
              size="mini"
              onClick={() => void load(identity)}
            >
              {identity.teacher_name}
            </Button>
          ))}
        </View>
      ) : null}

      {selected ? (
        <>
          <Button
            className="teacher-notification-button"
            size="mini"
            onClick={() => void enableWechatNotifications()}
          >
            开启微信通知
          </Button>
          <View className="teacher-section-heading">
            <Text className="teacher-section-title">今日预约</Text>
            <Text>{appointments.length} 人</Text>
          </View>
          <View className="teacher-list">
            {appointments.length === 0 ? (
              <Text className="teacher-empty">今日暂无预约</Text>
            ) : (
              appointments.map((item) => (
                <View className="teacher-item" key={item.id}>
                  <View className="teacher-item-heading">
                    <Text className="teacher-item-title">{item.course_name}</Text>
                    <Text className="teacher-item-time">
                      {formatTime(item.starts_at)}
                    </Text>
                  </View>
                  <Text className="teacher-item-meta">
                    {item.user_nickname} · {item.appointment_no}
                  </Text>
                  {item.status === 'reserved' ? (
                    <Button
                      className="teacher-cancel-button"
                      size="mini"
                      disabled={working}
                      onClick={() => void cancel(item)}
                    >
                      取消预约
                    </Button>
                  ) : null}
                </View>
              ))
            )}
          </View>

          <View className="teacher-section-heading">
            <Text className="teacher-section-title">教师消息</Text>
            <Text>{notifications.filter((item) => !item.read_at).length} 条未读</Text>
          </View>
          <View className="teacher-list">
            {notifications.length === 0 ? (
              <Text className="teacher-empty">暂无教师消息</Text>
            ) : (
              notifications.slice(0, 20).map((item) => (
                <View className="teacher-item" key={item.id}>
                  <Text className="teacher-item-title">{item.title}</Text>
                  <Text className="teacher-item-meta">{item.content}</Text>
                </View>
              ))
            )}
          </View>
        </>
      ) : null}
    </View>
  )
}

function State({ title, copy }: { title: string; copy: string }) {
  return (
    <View className="record-page">
      <View className="record-state">
        <View className="record-state-mark">师</View>
        <Text className="record-state-title">{title}</Text>
        <Text className="record-state-copy">{copy}</Text>
      </View>
    </View>
  )
}
