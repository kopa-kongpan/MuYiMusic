import { Button, Layout, Menu, Tooltip } from 'antd'
import { LogOut, Music2, Store } from 'lucide-react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { clearAdminSession, getAdminSession } from './session'

const { Content, Header, Sider } = Layout

export function AdminShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const session = getAdminSession()

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  function logout() {
    clearAdminSession()
    navigate('/login', { replace: true })
  }

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
          selectedKeys={['stores']}
          items={[
            {
              key: 'stores',
              icon: <Store size={17} aria-hidden="true" />,
              label: '门店管理',
            },
          ]}
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
