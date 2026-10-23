import { assetPath } from './path'

const iconPath = (fileName: string) => assetPath(`icons/muyi/${fileName}`)

export const appIcons = {
  home: iconPath('home-deer.png'),
  franchise: iconPath('franchise-deer.png'),
  courses: iconPath('course-note.png'),
  myCourses: iconPath('schedule.png'),
  schedule: iconPath('bookings.png'),
  headphones: iconPath('headphones.png'),
  teacher: iconPath('teacher.png'),
  profile: iconPath('profile.png'),
  franchiseBrand: iconPath('franchise-deer-alt.png'),
  orders: iconPath('orders.png'),
  bookings: iconPath('bookings.png'),
  notifications: iconPath('notifications.png'),
  store: iconPath('store.png'),
  videoCourses: iconPath('video-courses.png'),
  cart: iconPath('cart.png'),
  search: iconPath('search.png'),
  check: iconPath('check.png'),
  plus: iconPath('plus.png'),
  minus: iconPath('minus.png'),
  sort: iconPath('sort.png'),
  sortUp: iconPath('sort-up.png'),
  phone: iconPath('phone.png'),
  share: iconPath('share.png'),
  piano: iconPath('piano.png'),
  guitar: iconPath('guitar.png'),
} as const

export type AppIconName = keyof typeof appIcons

export function courseCategoryIcon(name: string): AppIconName {
  if (/钢琴|键盘|piano/i.test(name)) return 'piano'
  if (/吉他|guitar/i.test(name)) return 'guitar'
  if (/声乐|唱|vocal/i.test(name)) return 'teacher'
  return 'courses'
}

export function shortcutIcon(title: string, target = ''): AppIconName {
  if (/预约/.test(title) || target.includes('/booking/')) return 'bookings'
  if (target.includes('/teacher-portal/') || /教师/.test(title)) return 'teacher'
  if (target.includes('/my-orders/') || /订单/.test(title)) return 'orders'
  if (target.includes('/notifications/') || /消息|通知/.test(title)) return 'notifications'
  if (target.includes('/cart/') || /购物车/.test(title)) return 'cart'
  if (target.includes('/schedule/') || /课表/.test(title)) return 'myCourses'
  if (target.includes('/video-player/') || /视频/.test(title)) return 'videoCourses'
  if (target.includes('/my-courses/') || /我的课程/.test(title)) return 'headphones'
  if (target.includes('/franchise/') || /加盟/.test(title)) return 'franchise'
  if (target.includes('/me/') || /个人|我的/.test(title)) return 'profile'
  if (target.includes('/index/') || /门店/.test(title)) return 'store'
  return courseCategoryIcon(title)
}
