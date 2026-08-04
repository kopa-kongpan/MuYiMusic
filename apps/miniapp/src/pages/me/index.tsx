import { Text, View } from '@tarojs/components'

import { readCurrentStore } from '../../store/current-store'
import '../shared/section-state.scss'

export default function MePage() {
  const store = readCurrentStore()
  return (
    <View className="section-page">
      <View className="section-page-header">
        <Text className="section-page-title">我的</Text>
        <Text className="section-page-store">{store?.name ?? '尚未选择门店'}</Text>
      </View>
      <View className="section-state">
        <View className="section-state-mark">我</View>
        <Text className="section-state-title">未登录</Text>
        <Text className="section-state-copy">登录后可查看课程、课表和预约</Text>
      </View>
    </View>
  )
}
