import type { StorePublicRead } from '@muyimusic/api-client'
import { Button, Input, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useEffect, useState } from 'react'

import { listPublicStores } from '../../services/stores'
import { readCurrentStore, saveCurrentStore } from '../../store/current-store'
import './index.scss'

interface Coordinates {
  latitude: number
  longitude: number
}

type LocationState = 'loading' | 'ready' | 'unavailable'

export default function StoreSelectionPage() {
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [coordinates, setCoordinates] = useState<Coordinates | null>(null)
  const [locationState, setLocationState] = useState<LocationState>('loading')
  const [stores, setStores] = useState<StorePublicRead[]>([])
  const [currentStore, setCurrentStore] = useState<StorePublicRead | null>(() =>
    readCurrentStore(),
  )
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function loadStores(
    nextKeyword: string,
    nextCoordinates: Coordinates | null,
  ) {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const response = await listPublicStores({
        keyword: nextKeyword || undefined,
        latitude: nextCoordinates?.latitude,
        longitude: nextCoordinates?.longitude,
      })
      setStores(response.items)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '门店加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    let isMounted = true

    async function locate() {
      try {
        const result = await Taro.getLocation({ type: 'gcj02' })
        if (!isMounted) {
          return
        }
        const nextCoordinates = {
          latitude: result.latitude,
          longitude: result.longitude,
        }
        setCoordinates(nextCoordinates)
        setLocationState('ready')
        await loadStores('', nextCoordinates)
      } catch {
        if (!isMounted) {
          return
        }
        setLocationState('unavailable')
        await loadStores('', null)
      }
    }

    void locate()
    return () => {
      isMounted = false
    }
  }, [])

  function search() {
    const nextKeyword = keywordInput.trim()
    setKeyword(nextKeyword)
    void loadStores(nextKeyword, coordinates)
  }

  async function retryLocation() {
    setLocationState('loading')
    try {
      const result = await Taro.getLocation({ type: 'gcj02' })
      const nextCoordinates = {
        latitude: result.latitude,
        longitude: result.longitude,
      }
      setCoordinates(nextCoordinates)
      setLocationState('ready')
      await loadStores(keyword, nextCoordinates)
    } catch {
      setCoordinates(null)
      setLocationState('unavailable')
      await loadStores(keyword, null)
    }
  }

  async function selectStore(store: StorePublicRead) {
    saveCurrentStore(store)
    setCurrentStore(store)
    await Taro.showToast({ title: '门店已选择', icon: 'success' })
    await Taro.switchTab({ url: '/pages/home/index' })
  }

  function callStore(store: StorePublicRead) {
    void Taro.makePhoneCall({ phoneNumber: store.phone })
  }

  return (
    <View className="store-page">
      <View className="store-header">
        <View className="brand-lockup">
          <View className="brand-mark">M</View>
          <View>
            <Text className="brand-name">MuYiMusic</Text>
            <Text className="brand-subtitle">慕义音乐</Text>
          </View>
        </View>
        <Text className="page-title">选择门店</Text>
      </View>

      <View className="search-band">
        <View className="search-row">
          <Input
            className="search-input"
            value={keywordInput}
            placeholder="搜索门店、城市或地址"
            confirmType="search"
            onInput={(event) => setKeywordInput(event.detail.value)}
            onConfirm={search}
          />
          <Button className="search-button" size="mini" onClick={search}>
            搜索
          </Button>
        </View>
        <View className="location-row">
          <View className="location-label">
            <View className="location-dot" />
            <Text>
              {locationState === 'loading'
                ? '正在获取位置'
                : locationState === 'ready'
                  ? '已按距离排序'
                  : '未获取定位，可按城市搜索'}
            </Text>
          </View>
          {locationState === 'unavailable' ? (
            <Button className="text-button" size="mini" onClick={retryLocation}>
              重新定位
            </Button>
          ) : null}
        </View>
      </View>

      {currentStore ? (
        <View className="current-store-band">
          <View>
            <Text className="band-label">当前门店</Text>
            <Text className="band-store-name">{currentStore.name}</Text>
          </View>
          <View className="band-actions">
            <Text className="band-city">{currentStore.city}</Text>
            <Button
              className="band-enter-button"
              size="mini"
              onClick={() => void Taro.switchTab({ url: '/pages/home/index' })}
            >
              进入首页
            </Button>
          </View>
        </View>
      ) : null}

      <View className="store-list-heading">
        <Text className="store-list-title">
          {keyword ? `“${keyword}”的结果` : '可选门店'}
        </Text>
        {!isLoading && !errorMessage ? (
          <Text className="store-count">{stores.length} 家</Text>
        ) : null}
      </View>

      {isLoading ? (
        <View className="state-panel">
          <View className="loading-line" />
          <View className="loading-line loading-line--short" />
          <Text>门店加载中</Text>
        </View>
      ) : null}

      {!isLoading && errorMessage ? (
        <View className="state-panel state-panel--error">
          <Text className="state-title">暂时无法加载门店</Text>
          <Text className="state-copy">{errorMessage}</Text>
          <Button
            className="secondary-button"
            size="mini"
            onClick={() => void loadStores(keyword, coordinates)}
          >
            重试
          </Button>
        </View>
      ) : null}

      {!isLoading && !errorMessage && stores.length === 0 ? (
        <View className="state-panel">
          <Text className="state-title">没有找到匹配门店</Text>
          <Text className="state-copy">换个门店名称、城市或地址试试</Text>
        </View>
      ) : null}

      {!isLoading && !errorMessage ? (
        <View className="store-list">
          {stores.map((store, index) => {
            const isCurrent = currentStore?.id === store.id
            const isNearest = coordinates && index === 0 && store.distance_km != null
            return (
              <View className="store-item" key={store.id}>
                <View className="store-item-topline">
                  <View className="store-name-row">
                    <Text className="store-name">{store.name}</Text>
                    {isNearest ? <Text className="nearest-tag">最近</Text> : null}
                  </View>
                  {store.distance_km != null ? (
                    <Text className="distance-text">{store.distance_km} km</Text>
                  ) : null}
                </View>
                <Text className="store-address">
                  {store.city}
                  {store.district} {store.address}
                </Text>
                <View className="store-item-footer">
                  <Button
                    className="contact-button"
                    size="mini"
                    onClick={() => callStore(store)}
                  >
                    联系门店
                  </Button>
                  <Button
                    className="select-button"
                    size="mini"
                    onClick={() => void selectStore(store)}
                  >
                    {isCurrent ? '进入门店' : '选择门店'}
                  </Button>
                </View>
              </View>
            )
          })}
        </View>
      ) : null}
    </View>
  )
}
