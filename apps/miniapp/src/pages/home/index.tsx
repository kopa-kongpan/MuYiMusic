import type { ContentBlockPublicRead, StoreHomeResponse } from '@muyimusic/api-client'
import { Button, Image, Text, Video, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useRef, useState } from 'react'

import { getStoreHome } from '../../services/store-home'
import { readCurrentStore, saveCurrentStore } from '../../store/current-store'
import './index.scss'

const tabPages = new Set([
  '/pages/home/index',
  '/pages/courses/index',
  '/pages/booking/index',
  '/pages/me/index',
])

export default function StoreHomePage() {
  const [home, setHome] = useState<StoreHomeResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [failedMediaIds, setFailedMediaIds] = useState<Set<string>>(new Set())
  const requestSequence = useRef(0)

  async function loadHome() {
    const sequence = ++requestSequence.current
    const currentStore = readCurrentStore()
    if (!currentStore) {
      setHome(null)
      setErrorMessage('请先选择门店')
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const response = await getStoreHome(currentStore.id)
      if (sequence !== requestSequence.current) return
      saveCurrentStore(response.store)
      setHome(response)
      setFailedMediaIds(new Set())
    } catch (error) {
      if (sequence !== requestSequence.current) return
      setErrorMessage(error instanceof Error ? error.message : '门店首页加载失败')
    } finally {
      if (sequence === requestSequence.current) setIsLoading(false)
    }
  }

  useDidShow(() => {
    void loadHome()
  })

  usePullDownRefresh(() => {
    void loadHome().finally(() => Taro.stopPullDownRefresh())
  })

  function markMediaFailed(contentId: string) {
    setFailedMediaIds((current) => new Set(current).add(contentId))
  }

  async function openTarget(content: ContentBlockPublicRead) {
    if (content.jump_type === 'none' || !content.jump_target) {
      return
    }
    try {
      if (content.jump_type === 'web_url') {
        await Taro.navigateTo({
          url: `/pages/webview/index?url=${encodeURIComponent(content.jump_target)}`,
        })
        return
      }
      if (tabPages.has(content.jump_target)) {
        await Taro.switchTab({ url: content.jump_target })
        return
      }
      await Taro.navigateTo({ url: content.jump_target })
    } catch {
      await Taro.showToast({ title: '目标暂不可用', icon: 'none' })
    }
  }

  const shortcuts =
    home?.content_blocks.filter((content) => content.block_type === 'shortcut') ?? []
  const mediaBlocks =
    home?.content_blocks.filter((content) => content.block_type !== 'shortcut') ?? []

  return (
    <View className="home-page">
      <View className="home-topbar">
        <View className="home-brand">
          <View className="home-brand-mark">M</View>
          <Text>慕义音乐</Text>
        </View>
        <Button
          className="change-store-button"
          size="mini"
          onClick={() => void Taro.navigateTo({ url: '/pages/index/index' })}
        >
          切换门店
        </Button>
      </View>

      {home ? (
        <View className="store-identity-band">
          <Text className="home-store-name">{home.store.name}</Text>
          <Text className="home-store-address">
            {home.store.city}
            {home.store.district} {home.store.address}
          </Text>
          <Button
            className="store-phone-button"
            size="mini"
            onClick={() =>
              void Taro.makePhoneCall({ phoneNumber: home.store.phone })
            }
          >
            联系门店
          </Button>
        </View>
      ) : null}

      {isLoading ? (
        <View className="home-state">
          <View className="home-loading-media" />
          <View className="home-loading-line" />
          <Text>首页加载中</Text>
        </View>
      ) : null}

      {!isLoading && errorMessage ? (
        <View className="home-state home-state--error">
          <Text className="home-state-title">暂时无法打开门店首页</Text>
          <Text className="home-state-copy">{errorMessage}</Text>
          <View className="home-state-actions">
            <Button className="home-secondary-button" size="mini" onClick={() => void loadHome()}>
              重试
            </Button>
            <Button
              className="home-primary-button"
              size="mini"
              onClick={() => void Taro.navigateTo({ url: '/pages/index/index' })}
            >
              选择门店
            </Button>
          </View>
        </View>
      ) : null}

      {!isLoading && !errorMessage && home ? (
        <>
          {shortcuts.length ? (
            <View className="shortcut-section">
              <View className="home-section-heading">
                <Text>快捷入口</Text>
                <Text>{shortcuts.length} 项</Text>
              </View>
              <View className="shortcut-grid">
                {shortcuts.map((content) => (
                  <View
                    className="shortcut-item"
                    key={content.id}
                    hoverClass="shortcut-item--pressed"
                    onClick={() => void openTarget(content)}
                  >
                    {content.media_url && !failedMediaIds.has(content.id) ? (
                      <Image
                        className="shortcut-image"
                        src={content.media_url}
                        mode="aspectFill"
                        onError={() => markMediaFailed(content.id)}
                      />
                    ) : (
                      <View className="shortcut-symbol">
                        {content.title.slice(0, 1)}
                      </View>
                    )}
                    <Text>{content.title}</Text>
                  </View>
                ))}
              </View>
            </View>
          ) : null}

          <View className="media-section">
            <View className="home-section-heading">
              <Text>门店动态</Text>
              <Text>{mediaBlocks.length} 条</Text>
            </View>
            {mediaBlocks.length === 0 ? (
              <View className="home-empty-state">
                <Text className="home-state-title">暂无展示内容</Text>
                <Text className="home-state-copy">门店内容更新后将在这里展示</Text>
              </View>
            ) : (
              <View className="media-stream">
                {mediaBlocks.map((content) => {
                  const hasFailed =
                    failedMediaIds.has(content.id) || !content.media_url
                  return (
                    <View className="media-item" key={content.id}>
                      {hasFailed ? (
                        <View className="media-failure">
                          <Text>媒体加载失败</Text>
                          <Button
                            className="media-retry-button"
                            size="mini"
                            onClick={() => void loadHome()}
                          >
                            重新加载
                          </Button>
                        </View>
                      ) : content.block_type === 'image' ? (
                        <Image
                          className="home-media-image"
                          src={content.media_url!}
                          mode="aspectFill"
                          onClick={() => void openTarget(content)}
                          onError={() => markMediaFailed(content.id)}
                        />
                      ) : (
                        <Video
                          className="home-media-video"
                          src={content.media_url!}
                          controls
                          showFullscreenBtn
                          onError={() => markMediaFailed(content.id)}
                        />
                      )}
                      <View className="media-caption">
                        <Text>{content.title}</Text>
                        <Text>{content.block_type === 'image' ? '图片' : '视频'}</Text>
                      </View>
                    </View>
                  )
                })}
              </View>
            )}
          </View>
        </>
      ) : null}
    </View>
  )
}
