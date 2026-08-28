import type { FranchisePagePublicRead } from '@muyimusic/api-client'
import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useState } from 'react'

import { getFranchisePage } from '../../services/franchise'
import { readCurrentStore } from '../../store/current-store'
import './index.scss'

function lines(value: string): string[] {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
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
        <Text className="hero-kicker">JOIN MUYI MUSIC</Text>
        <Text className="hero-title">{page.title}</Text>
        <Text className="hero-copy">{page.introduction}</Text>
      </View>
      <View className="franchise-card"><Text className="section-title">合作优势</Text>{lines(page.advantages).map((item, index) => <View className="list-item" key={item}><Text className="list-index">{String(index + 1).padStart(2, '0')}</Text><Text>{item}</Text></View>)}</View>
      <View className="franchise-card"><Text className="section-title">全程支持</Text>{lines(page.support_policy).map((item) => <View className="support-item" key={item}><Text className="support-dot">✓</Text><Text>{item}</Text></View>)}</View>
      <View className="franchise-card"><Text className="section-title">申请流程</Text>{lines(page.application_process).map((item, index) => <View className="process-item" key={item}><Text className="process-step">{index + 1}</Text><Text>{item}</Text></View>)}</View>
      <View className="contact-card">
        <Text className="section-title">开启合作沟通</Text>
        <Text>联系人：{page.contact_name}</Text>
        <Text>联系电话：{page.contact_phone}</Text>
        {page.contact_wechat ? <Text>微信：{page.contact_wechat}</Text> : null}
        <Button className="contact-button" onClick={() => void Taro.makePhoneCall({ phoneNumber: page.contact_phone })}>立即咨询</Button>
      </View>
    </View>
  )
}
