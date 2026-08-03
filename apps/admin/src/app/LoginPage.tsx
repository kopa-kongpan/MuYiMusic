import { ApiError } from '@muyimusic/api-client'
import { App as AntdApp, Alert, Button, Form, Input } from 'antd'
import { LockKeyhole, LogIn, Music2, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { apiClient } from './api'
import { getAdminSession, saveAdminSession } from './session'

interface LoginFormValues {
  username: string
  password: string
}

export function LoginPage() {
  const navigate = useNavigate()
  const { message } = AntdApp.useApp()
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (getAdminSession()) {
    return <Navigate to="/stores" replace />
  }

  async function submit(values: LoginFormValues) {
    setIsSubmitting(true)
    setErrorMessage(null)
    try {
      const response = await apiClient.login(values)
      saveAdminSession(response)
      void message.success('登录成功')
      navigate('/stores', { replace: true })
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError ? error.message : '暂时无法连接服务，请稍后重试',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-brand-panel" aria-label="MuYiMusic 管理后台">
        <div className="login-brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            <Music2 size={25} strokeWidth={2.2} />
          </span>
          <span className="brand-name">MuYiMusic</span>
        </div>
        <h1>门店运营后台</h1>
        <p>慕义音乐</p>
      </section>
      <section className="login-form-panel">
        <div className="login-form-wrap">
          <header className="login-form-header">
            <h2>管理员登录</h2>
            <span>使用后台账号继续</span>
          </header>
          {errorMessage ? (
            <Alert
              className="login-alert"
              message={errorMessage}
              type="error"
              showIcon
            />
          ) : null}
          <Form<LoginFormValues>
            layout="vertical"
            requiredMark={false}
            onFinish={(values) => void submit(values)}
          >
            <Form.Item
              name="username"
              label="账号"
              rules={[{ required: true, message: '请输入管理员账号' }]}
            >
              <Input
                size="large"
                prefix={<UserRound size={17} aria-hidden="true" />}
                placeholder="管理员账号"
                autoComplete="username"
              />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                size="large"
                prefix={<LockKeyhole size={17} aria-hidden="true" />}
                placeholder="登录密码"
                autoComplete="current-password"
              />
            </Form.Item>
            <Button
              className="login-submit"
              type="primary"
              htmlType="submit"
              size="large"
              icon={<LogIn size={18} aria-hidden="true" />}
              loading={isSubmitting}
              block
            >
              登录
            </Button>
          </Form>
        </div>
      </section>
    </main>
  )
}
