import { defineConfig, type UserConfigExport } from '@tarojs/cli'

const outputRoot = `dist/${process.env.TARO_ENV ?? 'weapp'}`
const apiBaseUrl = process.env.TARO_APP_API_BASE_URL ?? 'http://127.0.0.1:8080'

const config: UserConfigExport = {
  projectName: 'MuYiMusic',
  date: '2026-08-03',
  designWidth: 750,
  deviceRatio: {
    640: 2.34 / 2,
    750: 1,
    828: 1.81 / 2,
  },
  sourceRoot: 'src',
  outputRoot,
  copy: {
    patterns: [
      {
        from: 'src/assets/icons/cart.png',
        to: `${outputRoot}/assets/icons/cart.png`,
      },
    ],
    options: {},
  },
  framework: 'react',
  compiler: 'webpack5',
  defineConstants: {
    MUYIMUSIC_API_BASE_URL: JSON.stringify(apiBaseUrl),
    MUYIMUSIC_WECHAT_TEMPLATE_STUDENT_CANCELLED: JSON.stringify(
      process.env.TARO_APP_WECHAT_TEMPLATE_STUDENT_CANCELLED ?? '',
    ),
    MUYIMUSIC_WECHAT_TEMPLATE_NEXT_DAY_REMINDER: JSON.stringify(
      process.env.TARO_APP_WECHAT_TEMPLATE_NEXT_DAY_REMINDER ?? '',
    ),
    MUYIMUSIC_WECHAT_TEMPLATE_TEACHER_NEW_APPOINTMENT: JSON.stringify(
      process.env.TARO_APP_WECHAT_TEMPLATE_TEACHER_NEW_APPOINTMENT ?? '',
    ),
    MUYIMUSIC_WECHAT_TEMPLATE_TEACHER_CANCELLED: JSON.stringify(
      process.env.TARO_APP_WECHAT_TEMPLATE_TEACHER_CANCELLED ?? '',
    ),
  },
  cache: {
    // Webpack 的微信端缓存不会感知 defineConstants 中构建期环境变量的变化，
    // 发布包必须重新烘焙 API 地址和订阅消息模板 ID。
    enable: process.env.TARO_ENV !== 'weapp',
  },
  mini: {
    postcss: {
      pxtransform: {
        enable: true,
      },
      cssModules: {
        enable: false,
      },
    },
  },
  h5: {
    publicPath: '/',
    staticDirectory: 'static',
  },
}

export default defineConfig(config)
