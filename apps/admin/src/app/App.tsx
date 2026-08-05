import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { RouterProvider } from 'react-router-dom'

import { router } from './router'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
})

export function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          borderRadius: 10,
          borderRadiusLG: 16,
          colorBgLayout: '#f4f5f1',
          colorBorder: '#dfe5df',
          colorInfo: '#176b57',
          colorPrimary: '#176b57',
          colorText: '#1b2722',
          colorTextSecondary: '#68746e',
          controlHeight: 38,
          fontFamily:
            'Inter, "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
        components: {
          Button: {
            defaultBorderColor: '#d9e1dc',
            defaultColor: '#34453e',
            defaultHoverBg: '#f7faf8',
            fontWeight: 550,
            primaryShadow: '0 7px 18px rgba(23, 107, 87, 0.2)',
          },
          Layout: {
            bodyBg: '#f4f5f1',
            headerBg: 'rgba(255, 255, 255, 0.88)',
            siderBg: '#10251f',
          },
          Menu: {
            activeBarBorderWidth: 0,
            darkGroupTitleColor: '#81978f',
            darkItemBg: '#10251f',
            darkItemColor: '#c8d4cf',
            darkItemHoverBg: '#183b31',
            darkItemHoverColor: '#ffffff',
            darkItemSelectedBg: '#1d725d',
            darkItemSelectedColor: '#ffffff',
            darkSubMenuItemBg: '#10251f',
            groupTitleFontSize: 11,
            iconSize: 18,
            itemBorderRadius: 10,
            itemHeight: 44,
            itemMarginBlock: 4,
            itemMarginInline: 12,
          },
          Table: {
            borderColor: '#e7ebe7',
            cellPaddingBlockMD: 15,
            headerBg: '#f3f6f3',
            headerColor: '#59675f',
            headerSplitColor: '#e3e9e4',
            rowHoverBg: '#f7faf8',
          },
        },
      }}
    >
      <AntdApp>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AntdApp>
    </ConfigProvider>
  )
}
