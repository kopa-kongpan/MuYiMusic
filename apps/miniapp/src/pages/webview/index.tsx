import { Text, View, WebView } from '@tarojs/components'
import { useRouter } from '@tarojs/taro'

import '../shared/section-state.scss'

export default function WebPage() {
  const router = useRouter()
  const target = router.params.url ? decodeURIComponent(router.params.url) : ''
  const isValidUrl = /^https?:\/\//i.test(target)

  if (!isValidUrl) {
    return (
      <View className="section-page">
        <View className="section-state">
          <Text className="section-state-title">链接不可用</Text>
        </View>
      </View>
    )
  }
  return <WebView src={target} />
}
