import { createReactConfig } from '@muyimusic/eslint-config'

export default [
  ...createReactConfig(),
  {
    languageOptions: {
      globals: {
        defineAppConfig: 'readonly',
        definePageConfig: 'readonly',
        process: 'readonly',
      },
    },
  },
]

