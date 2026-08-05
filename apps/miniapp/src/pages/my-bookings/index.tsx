import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'

import { readCurrentStore } from '../../store/current-store'
import { readUserSession } from '../../store/user-session'
import '../shared/user-records.scss'

export default function MyBookingsPage() {
  const session = readUserSession()
  const store = readCurrentStore()
  return (
    <View className="record-page">
      <View className="record-heading">
        <Text className="record-title">我的预约</Text>
        <Text className="record-store">{store?.name ?? '全部门店'}</Text>
      </View>
      <View className="record-state">
        <View className="record-state-mark">约</View>
        <Text className="record-state-title">
          {session ? '暂无预约记录' : '请先登录'}
        </Text>
        <Text className="record-state-copy">
          {session
            ? '预约数据将在下一阶段接入，此处不会展示模拟记录'
            : '登录后可查看本人预约记录'}
        </Text>
        {!session ? (
          <Button
            className="record-state-button"
            size="mini"
            onClick={() => void Taro.switchTab({ url: '/pages/me/index' })}
          >
            去登录
          </Button>
        ) : null}
      </View>
    </View>
  )
}
