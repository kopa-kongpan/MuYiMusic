import { Text, View } from '@tarojs/components'

import { readCurrentStore } from '../../store/current-store'
import '../shared/section-state.scss'

export default function BookingPage() {
  const store = readCurrentStore()
  return (
    <View className="section-page">
      <View className="section-page-header">
        <Text className="section-page-title">预约</Text>
        <Text className="section-page-store">{store?.name ?? '尚未选择门店'}</Text>
      </View>
      <View className="section-state">
        <View className="section-state-mark">约</View>
        <Text className="section-state-title">暂无可预约时段</Text>
        <Text className="section-state-copy">门店开放排课后将在这里展示</Text>
      </View>
    </View>
  )
}
