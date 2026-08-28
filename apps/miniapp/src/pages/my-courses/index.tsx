import type { CourseEntitlementRead, EntitlementStatus } from '@muyimusic/api-client'
import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { listMyCourseEntitlements } from '../../services/user'
import { readCurrentStore } from '../../store/current-store'
import { setLoginReturn } from '../../store/login-return'
import { readUserSession } from '../../store/user-session'
import '../shared/user-records.scss'

const statusLabels: Record<EntitlementStatus, string> = {
  active: '生效中',
  exhausted: '已用完',
  expired: '已过期',
}

function formatDate(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(
        new Date(value),
      )
    : '长期有效'
}

function formatDuration(seconds: number | null): string {
  if (!seconds) {
    return '时长未知'
  }
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes}分${rest}秒` : `${minutes}分钟`
}

function openChapter(entitlementId: string, index: number) {
  void Taro.navigateTo({
    url: `/pages/video-player/index?entitlementId=${entitlementId}&index=${index}`,
  })
}

export default function MyCoursesPage() {
  const [courses, setCourses] = useState<CourseEntitlementRead[]>([])
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
      const response = await listMyCourseEntitlements(store?.id)
      setCourses(response.items)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '课程权益加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  useDidShow(() => {
    void load()
  })

  let content: React.ReactNode
  if (!session) {
    content = (
      <RecordState mark="课" title="请先登录" copy="登录后可查看本人课程权益">
        <Button
          className="record-state-button"
          size="mini"
          onClick={() => {
            setLoginReturn('/pages/my-courses/index')
            void Taro.switchTab({ url: '/pages/me/index' })
          }}
        >
          去登录
        </Button>
      </RecordState>
    )
  } else if (isLoading) {
    content = <RecordState mark="课" title="正在加载课程" copy="请稍候" />
  } else if (errorMessage) {
    content = (
      <RecordState mark="课" title="课程加载失败" copy={errorMessage}>
        <Button className="record-state-button" size="mini" onClick={() => void load()}>
          重试
        </Button>
      </RecordState>
    )
  } else if (courses.length === 0) {
    content = (
      <RecordState mark="课" title="暂无课程" copy="当前门店还没有可展示的课程权益" />
    )
  } else {
    content = (
      <View className="record-list">
        {courses.map((course) => (
          <View className="record-card" key={course.id}>
            <View className="record-card-header">
              <Text className="record-card-title">{course.course_name}</Text>
              <Text
                className={`record-status${course.status === 'active' ? '' : ' record-status--muted'}`}
              >
                {statusLabels[course.status]}
              </Text>
            </View>
            <Text className="record-card-meta">{course.store_name}</Text>
            <View className="record-course-progress">
              <Text>可用 / 锁定 / 总剩余</Text>
              <Text>
                {course.available_lessons} / {course.reserved_lessons} /{' '}
                {course.remaining_lessons}
              </Text>
            </View>
            {(course.video_chapters?.length ?? 0) > 0 ? (
              <View className="record-course-chapters">
                <Text className="record-course-chapters-heading">
                  配套视频 · 共 {course.video_chapters?.length ?? 0} 个课时
                </Text>
                {(course.video_chapters ?? []).map((chapter, index) => (
                  <View
                    className="record-chapter"
                    key={chapter.id}
                    onClick={() => openChapter(course.id, index)}
                  >
                    <Text className="record-chapter-index">{index + 1}</Text>
                    <Text className="record-chapter-title">
                      {chapter.video_course_name} · 第 {chapter.lesson_number} 课时 ·{' '}
                      {chapter.title}
                    </Text>
                    <Text className="record-chapter-duration">
                      {formatDuration(chapter.duration_seconds)}
                    </Text>
                  </View>
                ))}
              </View>
            ) : null}
            <Text className="record-card-meta">
              有效期：{formatDate(course.valid_from)} 至 {formatDate(course.expires_at)}
            </Text>
          </View>
        ))}
      </View>
    )
  }

  return (
    <View className="record-page">
      <View className="record-heading">
        <Text className="record-title">我的课程</Text>
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
