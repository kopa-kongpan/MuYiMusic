import { Image } from '@tarojs/components'

import { appIcons, type AppIconName } from '../assets/icons'

interface AppIconProps {
  name: AppIconName
  className?: string
}

/**
 * 资源与显示区域均为正方形；scaleToFill 避免 H5 的 aspectFit 绝对定位裁切。
 * 图标旁保留文字，纯图标按钮由所属按钮提供无障碍名称。
 */
export default function AppIcon({ name, className = '' }: AppIconProps) {
  return (
    <Image
      className={`app-icon ${className}`}
      src={appIcons[name]}
      mode="scaleToFill"
      aria-hidden="true"
    />
  )
}
