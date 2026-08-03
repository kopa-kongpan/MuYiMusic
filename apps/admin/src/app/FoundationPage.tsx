import { Layout, Typography } from 'antd'

const { Content, Header } = Layout

export function FoundationPage() {
  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <Typography.Text className="app-brand">MuYiMusic</Typography.Text>
        <Typography.Text className="app-context">Admin Console</Typography.Text>
      </Header>
      <Content className="app-content" />
    </Layout>
  )
}

