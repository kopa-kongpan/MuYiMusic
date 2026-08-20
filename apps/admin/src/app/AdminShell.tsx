import { Button, Layout, Menu, Tooltip } from 'antd'
import type { MenuProps } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import {
  BookOpen,
  CalendarDays,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  Music2,
  Send,
  Store,
  ShieldCheck,
  UsersRound,
} from 'lucide-react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { clearAdminSession, getAdminSession } from './session'

const { Content, Header, Sider } = Layout

const pageNames: Record<string, string> = {
  appointments: '预约与消课',
  notifications: '消息投递',
  products: '课程商品',
  schedules: '排课管理',
  'store-content': '首页内容',
  stores: '门店管理',
  users: '用户与权益',
  'admin-accounts': '运营账号',
}

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
          : location.pathname.startsWith('/notifications')
            ? 'notifications'
          : location.pathname.startsWith('/users')
            ? 'users'
            : location.pathname.startsWith('/admin-accounts')
              ? 'admin-accounts'
              : 'stores'
  const hasPermission = (permission: string) =>
    session.admin.permissions.includes(permission)
  const storeItems: MenuProps['items'] = [
    {
      key: 'stores',
      icon: <Store size={18} aria-hidden="true" />,
      label: '门店管理',
    },
    ...(hasPermission('store_content:manage')
      ? [
          {
            key: 'store-content',
            icon: <LayoutDashboard size={18} aria-hidden="true" />,
            label: '首页内容',
          },
        ]
      : []),
    ...(hasPermission('products:manage')
      ? [
          {
            key: 'products',
            icon: <BookOpen size={18} aria-hidden="true" />,
            label: '课程商品',
          },
        ]
      : []),
  ]
  const teachingItems: MenuProps['items'] = [
    ...(hasPermission('schedules:manage')
      ? [
          {
            key: 'schedules',
            icon: <CalendarDays size={18} aria-hidden="true" />,
            label: '排课管理',
          },
        ]
      : []),
    ...(hasPermission('appointments:manage')
      ? [
          {
            key: 'appointments',
            icon: <ClipboardCheck size={18} aria-hidden="true" />,
            label: '预约与消课',
          },
          {
            key: 'notifications',
            icon: <Send size={18} aria-hidden="true" />,
            label: '消息投递',
          },
        ]
      : []),
  ]
  const customerItems: MenuProps['items'] = hasPermission('users:read')
    ? [
        {
          key: 'users',
          icon: <UsersRound size={18} aria-hidden="true" />,
          label: '用户与权益',
        },
      ]
    : []
  const platformItems: MenuProps['items'] = hasPermission('admins:manage')
    ? [
        {
          key: 'admin-accounts',
          icon: <ShieldCheck size={18} aria-hidden="true" />,
          label: '运营账号',
        },
      ]
    : []
  const menuItems: MenuProps['items'] = [
    { type: 'group', label: '门店经营', children: storeItems },
    ...(teachingItems.length
      ? [{ type: 'group' as const, label: '教学运营', children: teachingItems }]
      : []),
    ...(customerItems.length
      ? [{ type: 'group' as const, label: '客户中心', children: customerItems }]
      : []),
    ...(platformItems.length
      ? [{ type: 'group' as const, label: '平台设置', children: platformItems }]
      : []),
  ]
  const currentPageName = pageNames[selectedMenuKey]

  return (
    <Layout className="admin-shell">
      <Sider className="admin-sider" width={248}>
        <div className="admin-brand">
          <span className="brand-mark brand-mark--small" aria-hidden="true">
            <Music2 size={21} strokeWidth={2.2} />
          </span>
          <span className="admin-brand-copy">
            <strong>MuYiMusic</strong>
            <small>音乐门店运营中心</small>
          </span>
        </div>
        <Menu
          className="admin-menu"
          mode="inline"
          theme="dark"
          selectedKeys={[selectedMenuKey]}
          items={menuItems}
          onClick={({ key }) => navigate(`/${key}`)}
        />
        <div className="admin-sider-footer">
          <span className="admin-status-dot" aria-hidden="true" />
          <span>
            <strong>门店运营系统</strong>
            <small>服务连接正常</small>
          </span>
        </div>
      </Sider>
      <Layout className="admin-main">
        <Header className="admin-header">
          <div className="mobile-brand">
            <Music2 size={20} aria-hidden="true" />
            <span>MuYiMusic</span>
          </div>
          <div className="admin-page-context">
            <span>运营工作台</span>
            <strong>{currentPageName}</strong>
          </div>
          <div className="admin-user">
            <span className="admin-user-avatar" aria-hidden="true">
              {session.admin.username.slice(0, 1).toUpperCase()}
            </span>
            <span className="admin-user-copy">
              <strong className="admin-user-name">{session.admin.username}</strong>
              <small>后台账号</small>
            </span>
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
