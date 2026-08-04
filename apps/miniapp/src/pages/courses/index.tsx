import { Text, View } from '@tarojs/components'

import { readCurrentStore } from '../../store/current-store'
import '../shared/section-state.scss'

export default function CoursesPage() {
  const store = readCurrentStore()
  return (
    <View className="section-page">
      <View className="section-page-header">
        <Text className="section-page-title">课程</Text>
        <Text className="section-page-store">{store?.name ?? '尚未选择门店'}</Text>
      </View>
      <View className="section-state">
        <View className="section-state-mark">课</View>
        <Text className="section-state-title">暂无可售课程</Text>
        <Text className="section-state-copy">门店上架课程后将在这里展示</Text>
      </View>
    </View>
  )
}
