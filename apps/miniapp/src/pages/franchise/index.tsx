import type { FranchisePagePublicRead } from '@muyimusic/api-client'
import { Button, Image, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useState } from 'react'

import { appIcons } from '../../assets/icons'
import { getFranchisePage } from '../../services/franchise'
import { readCurrentStore } from '../../store/current-store'
import './index.scss'

function lines(value: string): string[] {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

const assetPath = (fileName: string) => `/assets/franchise/${fileName}`

const franchiseVisuals = {
  hero: assetPath('brand-hero.jpg'),
  stores: assetPath('store-network.jpg'),
  introduction: assetPath('brand-introduction.jpg'),
  teaching: assetPath('teaching-materials.jpg'),
  benefits: assetPath('cooperation-benefits.jpg'),
  contact: assetPath('contact-us.jpg'),
}

const operationVisuals = [
  { src: assetPath('operation-daily.jpg'), label: '单日经营数据' },
  { src: assetPath('operation-monthly.jpg'), label: '月度经营数据' },
  { src: assetPath('live-results.jpg'), label: '直播经营成果' },
  { src: assetPath('industry-ranking.jpg'), label: '行业经营排名' },
]

function previewImage(current: string, urls: string[] = [current]) {
  void Taro.previewImage({ current, urls })
}

export default function FranchisePage() {
  const [page, setPage] = useState<FranchisePagePublicRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    const store = readCurrentStore()
    if (!store) {
      setError('请先选择门店')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setPage(await getFranchisePage(store.id))
    } catch (reason) {
      setPage(null)
      setError(reason instanceof Error ? reason.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useDidShow(() => void load())
  usePullDownRefresh(() => void load().finally(() => Taro.stopPullDownRefresh()))

  if (loading) return <View className="franchise-state"><Text>加盟合作内容加载中</Text></View>
  if (error || !page) {
    return <View className="franchise-state"><Text className="state-title">暂时无法查看加盟合作</Text><Text>{error}</Text><Button size="mini" onClick={() => void load()}>重新加载</Button></View>
  }

  return (
    <View className="franchise-page">
      <View className="franchise-hero">
        <Image
          className="hero-image"
          src={franchiseVisuals.hero}
          mode="widthFix"
          onClick={() => previewImage(franchiseVisuals.hero)}
        />
        <View className="hero-content">
          <View className="hero-brand-line">
            <Image className="hero-brand-icon" src={appIcons.franchiseBrand} mode="aspectFill" />
            <Text className="hero-kicker">JOIN MUYI MUSIC</Text>
          </View>
          <Text className="hero-title">{page.title}</Text>
          <Text className="hero-copy">{page.introduction}</Text>
        </View>
      </View>

      <View className="franchise-section brand-section">
        <View className="section-heading">
          <Text className="section-kicker">BRAND & NETWORK</Text>
          <Text className="section-title">品牌与门店</Text>
        </View>
        <View className="visual-stack">
          <Image
            className="content-image landscape-image"
            src={franchiseVisuals.stores}
            mode="widthFix"
            onClick={() => previewImage(franchiseVisuals.stores)}
          />
          <Image
            className="content-image portrait-image"
            src={franchiseVisuals.introduction}
            mode="widthFix"
            onClick={() => previewImage(franchiseVisuals.introduction)}
          />
        </View>
      </View>

      <View className="franchise-section advantages-section">
        <View className="section-heading">
          <Text className="section-kicker">WHY MUYI</Text>
          <Text className="section-title">合作优势</Text>
        </View>
        <View className="numbered-list">
          {lines(page.advantages).map((item, index) => (
            <View className="list-item" key={item}>
              <Text className="list-index">{String(index + 1).padStart(2, '0')}</Text>
              <Text className="list-copy">{item}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className="franchise-section operation-section">
        <View className="section-heading">
          <Text className="section-kicker">PROVEN OPERATION</Text>
          <Text className="section-title">经营成果</Text>
          <Text className="section-summary">左右滑动查看经营数据，点击图片可放大</Text>
        </View>
        <ScrollView className="proof-scroll" scrollX enhanced showScrollbar={false}>
          <View className="proof-list">
            {operationVisuals.map((item) => (
              <View className="proof-item" key={item.src} onClick={() => previewImage(item.src, operationVisuals.map((visual) => visual.src))}>
                <Image className="proof-image" src={item.src} mode="aspectFill" />
                <Text className="proof-label">{item.label}</Text>
              </View>
            ))}
          </View>
        </ScrollView>
      </View>

      <View className="franchise-section support-section">
        <View className="section-heading">
          <Text className="section-kicker">CONTENT & SUPPORT</Text>
          <Text className="section-title">课程内容与全程支持</Text>
        </View>
        <Image
          className="content-image landscape-image"
          src={franchiseVisuals.teaching}
          mode="widthFix"
          onClick={() => previewImage(franchiseVisuals.teaching)}
        />
        <View className="support-list">
          {lines(page.support_policy).map((item) => (
            <View className="support-item" key={item}>
              <Text className="support-dot">✓</Text>
              <Text className="list-copy">{item}</Text>
            </View>
          ))}
        </View>
        <Image
          className="content-image landscape-image"
          src={franchiseVisuals.benefits}
          mode="widthFix"
          onClick={() => previewImage(franchiseVisuals.benefits)}
        />
      </View>

      <View className="franchise-section process-section">
        <View className="section-heading">
          <Text className="section-kicker">HOW TO JOIN</Text>
          <Text className="section-title">申请流程</Text>
        </View>
        <View className="process-list">
          {lines(page.application_process).map((item, index) => (
            <View className="process-item" key={item}>
              <Text className="process-step">{index + 1}</Text>
              <Text className="list-copy">{item}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className="contact-section">
        <Image
          className="contact-image"
          src={franchiseVisuals.contact}
          mode="widthFix"
          onClick={() => previewImage(franchiseVisuals.contact)}
        />
        <View className="contact-content">
          <Text className="section-kicker contact-kicker">START A CONVERSATION</Text>
          <Text className="section-title contact-title">开启合作沟通</Text>
          <Text>联系人：{page.contact_name}</Text>
          <Text>联系电话：{page.contact_phone}</Text>
          {page.contact_wechat ? <Text>微信：{page.contact_wechat}</Text> : null}
          <Button className="contact-button" onClick={() => void Taro.makePhoneCall({ phoneNumber: page.contact_phone })}>立即咨询</Button>
        </View>
      </View>
    </View>
  )
}
