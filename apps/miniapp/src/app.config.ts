export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/home/index',
    'pages/courses/index',
    'pages/course-detail/index',
    'pages/cart/index',
    'pages/booking/index',
    'pages/me/index',
    'pages/webview/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#f3f5f4',
    navigationBarTitleText: '选择门店',
    navigationBarTextStyle: 'black',
  },
  tabBar: {
    color: '#747c77',
    selectedColor: '#176b57',
    backgroundColor: '#ffffff',
    borderStyle: 'white',
    list: [
      { pagePath: 'pages/home/index', text: '首页' },
      { pagePath: 'pages/courses/index', text: '课程' },
      { pagePath: 'pages/booking/index', text: '预约' },
      { pagePath: 'pages/me/index', text: '我的' },
    ],
  },
})
