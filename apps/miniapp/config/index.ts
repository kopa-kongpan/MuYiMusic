import { defineConfig, type UserConfigExport } from '@tarojs/cli'

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
  outputRoot: `dist/${process.env.TARO_ENV ?? 'weapp'}`,
  framework: 'react',
  compiler: 'webpack5',
  defineConstants: {
    MUYIMUSIC_API_BASE_URL: JSON.stringify(
      process.env.TARO_APP_API_BASE_URL ?? 'https://muyimusic.net',
    ),
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
    enable: true,
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
