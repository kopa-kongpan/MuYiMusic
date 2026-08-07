import type { EntitlementVideoChapterRead } from '@muyimusic/api-client'
import { Button, Text, View, Video } from '@tarojs/components'
import Taro, { useLoad, useRouter } from '@tarojs/taro'
import { useState } from 'react'

import { listMyCourseEntitlements } from '../../services/user'
import { readCurrentStore } from '../../store/current-store'
import { setLoginReturn } from '../../store/login-return'
import { readUserSession } from '../../store/user-session'
import './index.scss'

function formatDuration(seconds: number | null): string {
  if (!seconds) {
    return '时长未知'
  }
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes}分${rest}秒` : `${minutes}分钟`
}

export default function VideoPlayerPage() {
  const router = useRouter()
  const session = readUserSession()
  const [chapters, setChapters] = useState<EntitlementVideoChapterRead[]>([])
  const [courseName, setCourseName] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function load() {
    const entitlementId = router.params.entitlementId
    const requestedIndex = Number(router.params.index ?? 0)
    const store = readCurrentStore()
    if (!session) {
      setIsLoading(false)
      setErrorMessage('请先登录')
      return
    }
    if (!entitlementId) {
      setErrorMessage('课程参数无效')
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const response = await listMyCourseEntitlements(store?.id)
      const entitlement = response.items.find((item) => item.id === entitlementId)
      if (!entitlement) {
        throw new Error('课程权益不存在或已失效')
      }
      const active = entitlement.video_chapters ?? []
      if (!active.length) {
        throw new Error('该课程暂无可用章节')
      }
      setChapters(active)
      setCourseName(entitlement.course_name)
      setCurrentIndex(Math.min(Math.max(0, requestedIndex), active.length - 1))
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '章节加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  useLoad(() => {
    void load()
  })

  if (!session) {
    return (
      <View className="player-state">
        <Text className="player-state-title">请先登录</Text>
        <Text className="player-state-copy">登录后可观看已购视频课程</Text>
        <Button
          className="player-state-button"
          size="mini"
          onClick={() => {
            setLoginReturn('/pages/my-courses/index')
            void Taro.switchTab({ url: '/pages/me/index' })
          }}
        >
          去登录
        </Button>
      </View>
    )
  }

  if (isLoading) {
    return (
      <View className="player-state">
        <Text className="player-state-title">正在加载章节</Text>
        <Text className="player-state-copy">请稍候</Text>
      </View>
    )
  }

  if (errorMessage || !chapters.length) {
    return (
      <View className="player-state">
        <Text className="player-state-title">视频暂不可观看</Text>
        <Text className="player-state-copy">{errorMessage ?? '章节不存在'}</Text>
        <Button className="player-state-button" size="mini" onClick={() => void load()}>
          重试
        </Button>
      </View>
    )
  }

  const current = chapters[currentIndex]!

  return (
    <View className="player-page">
      {current.video_url ? (
        <Video
          className="player-video"
          src={current.video_url}
          controls
          autoplay
          showCenterPlayBtn
          enableProgressGesture
          title={current.title}
        />
      ) : (
        <View className="player-video player-video--empty">
          <Text>视频地址暂不可用</Text>
        </View>
      )}
      <View className="player-info">
        <Text className="player-course">{courseName}</Text>
        <Text className="player-current">
          第 {currentIndex + 1} 章 · {current.title}
        </Text>
      </View>
      <View className="player-chapters">
        <Text className="player-chapters-title">章节列表</Text>
        {chapters.map((chapter, index) => (
          <View
            className={`player-chapter${index === currentIndex ? ' player-chapter--active' : ''}`}
            key={chapter.id}
            onClick={() => setCurrentIndex(index)}
          >
            <Text className="player-chapter-index">{index + 1}</Text>
            <Text className="player-chapter-title">{chapter.title}</Text>
            <Text className="player-chapter-duration">
              {formatDuration(chapter.duration_seconds)}
            </Text>
          </View>
        ))}
      </View>
    </View>
  )
}
