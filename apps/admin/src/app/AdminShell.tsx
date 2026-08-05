import { Button, Layout, Menu, Tooltip } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import {
  BookOpen,
  CalendarDays,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  Music2,
  Store,
  UsersRound,
} from 'lucide-react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { clearAdminSession, getAdminSession } from './session'

const { Content, Header, Sider } = Layout

export function AdminShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const session = getAdminSession()

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  function logout() {
    clearAdminSession()
    queryClient.clear()
    navigate('/login', { replace: true })
  }

  const selectedMenuKey = location.pathname.startsWith('/store-content')
    ? 'store-content'
    : location.pathname.startsWith('/products')
      ? 'products'
      : location.pathname.startsWith('/schedules')
        ? 'schedules'
        : location.pathname.startsWith('/appointments')
          ? 'appointments'
          : location.pathname.startsWith('/users')
          ? 'users'
          : 'stores'
  const menuItems = [
    {
      key: 'stores',
      icon: <Store size={17} aria-hidden="true" />,
      label: '门店管理',
    },
    ...(session.admin.permissions.includes('store_content:manage')
      ? [
          {
            key: 'store-content',
            icon: <LayoutDashboard size={17} aria-hidden="true" />,
            label: '首页内容',
          },
        ]
      : []),
    ...(session.admin.permissions.includes('products:manage')
      ? [
          {
            key: 'products',
            icon: <BookOpen size={17} aria-hidden="true" />,
            label: '课程商品',
          },
        ]
      : []),
    ...(session.admin.permissions.includes('users:read')
      ? [
          {
            key: 'users',
            icon: <UsersRound size={17} aria-hidden="true" />,
            label: '用户与权益',
          },
        ]
      : []),
    ...(session.admin.permissions.includes('schedules:manage')
      ? [
          {
            key: 'schedules',
            icon: <CalendarDays size={17} aria-hidden="true" />,
            label: '排课管理',
          },
        ]
      : []),
    ...(session.admin.permissions.includes('appointments:manage')
      ? [
          {
            key: 'appointments',
            icon: <ClipboardCheck size={17} aria-hidden="true" />,
            label: '预约与消课',
          },
        ]
      : []),
  ]

  return (
    <Layout className="admin-shell">
      <Sider className="admin-sider" width={216}>
        <div className="admin-brand">
          <span className="brand-mark brand-mark--small" aria-hidden="true">
            <Music2 size={21} strokeWidth={2.2} />
          </span>
          <span>MuYiMusic</span>
        </div>
        <Menu
          className="admin-menu"
          mode="inline"
          selectedKeys={[selectedMenuKey]}
          items={menuItems}
          onClick={({ key }) => navigate(`/${key}`)}
        />
      </Sider>
      <Layout className="admin-main">
        <Header className="admin-header">
          <div className="mobile-brand">
            <Music2 size={20} aria-hidden="true" />
            <span>MuYiMusic</span>
          </div>
          <div className="admin-user">
            <span className="admin-user-name">{session.admin.username}</span>
            <Tooltip title="退出登录">
              <Button
                type="text"
                icon={<LogOut size={18} aria-hidden="true" />}
                aria-label="退出登录"
                onClick={logout}
              />
            </Tooltip>
          </div>
        </Header>
        <Content className="admin-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
