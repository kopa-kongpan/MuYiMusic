import type {
  AdminUserCreate,
  AdminUserRead,
} from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  App as AntdApp,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Switch,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import type { TableProps } from 'antd'
import {
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  Search,
} from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'
import { getAdminSession } from './session'

interface AccountFormValues {
  username?: string
  password?: string
  role_code: string
  store_ids: string[]
  is_active: boolean
}

interface PasswordFormValues {
  password: string
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function AdminAccountsPage() {
  const { message } = AntdApp.useApp()
  const currentAdminId = getAdminSession()?.admin.id
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editingAccount, setEditingAccount] = useState<AdminUserRead | null>(null)
  const [passwordAccount, setPasswordAccount] = useState<AdminUserRead | null>(
    null,
  )
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false)
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [accountForm] = Form.useForm<AccountFormValues>()
  const [passwordForm] = Form.useForm<PasswordFormValues>()

  const optionsQuery = useQuery({
    queryKey: ['admin-account-options'],
    queryFn: () => apiClient.getAdminUserOptions(),
  })
  const accountsQuery = useQuery({
    queryKey: ['admin-accounts', keyword, page, pageSize],
    queryFn: () => apiClient.listAdminAccounts({ keyword, page, pageSize }),
  })

  const options = optionsQuery.data
  const roleOptions = (options?.roles ?? []).map((role) => ({
    label: role.name,
    value: role.code,
  }))
  const storeOptions = (options?.stores ?? []).map((store) => ({
    label: `${store.name} · ${store.city}`,
    value: store.id,
  }))

  function search() {
    setPage(1)
    setKeyword(keywordInput.trim())
  }

  function openCreate() {
    setEditingAccount(null)
    setIsAccountModalOpen(true)
  }

  function openEdit(account: AdminUserRead) {
    setEditingAccount(account)
    setIsAccountModalOpen(true)
  }

  async function submitAccount(values: AccountFormValues) {
    setUpdatingId(editingAccount?.id ?? 'new')
    try {
      if (editingAccount) {
        await apiClient.updateAdminUser(editingAccount.id, {
          role_code: values.role_code,
          store_ids: values.store_ids,
          is_active: values.is_active,
        })
      } else {
        await apiClient.createAdminUser({
          username: values.username ?? '',
          password: values.password ?? '',
          role_code: values.role_code,
          store_ids: values.store_ids,
        } satisfies AdminUserCreate)
      }
      await accountsQuery.refetch()
      void message.success(editingAccount ? '运营账号已更新' : '运营账号已创建')
      setIsAccountModalOpen(false)
      accountForm.resetFields()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setUpdatingId(null)
    }
  }

  async function toggleAccount(account: AdminUserRead, isActive: boolean) {
    if (account.id === currentAdminId) {
      return
    }
    setUpdatingId(account.id)
    try {
      await apiClient.updateAdminUser(account.id, { is_active: isActive })
      await accountsQuery.refetch()
      void message.success(isActive ? '账号已启用' : '账号已停用')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '状态更新失败')
    } finally {
      setUpdatingId(null)
    }
  }

  async function resetPassword(values: PasswordFormValues) {
    if (!passwordAccount) {
      return
    }
    setUpdatingId(passwordAccount.id)
    try {
      await apiClient.resetAdminUserPassword(passwordAccount.id, values)
      void message.success('登录密码已重置')
      setIsPasswordModalOpen(false)
      passwordForm.resetFields()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '密码重置失败')
    } finally {
      setUpdatingId(null)
    }
  }

  const columns: NonNullable<TableProps<AdminUserRead>['columns']> = [
    {
      title: '运营账号',
      key: 'account',
      width: 220,
      render: (_, account) => (
        <div className="account-cell">
          <span className="account-avatar" aria-hidden="true">
            {account.username.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>{account.username}</strong>
            <span>创建于 {formatTime(account.created_at)}</span>
          </div>
        </div>
      ),
    },
    {
      title: '角色',
      key: 'roles',
      width: 180,
      render: (_, account) => (
        <div className="account-tags">
          {account.roles.map((role) => (
            <Tag key={role.code} color="blue">
              {role.name}
            </Tag>
          ))}
        </div>
      ),
    },
    {
      title: '授权门店',
      key: 'stores',
      width: 270,
      render: (_, account) => (
        <div className="account-stores">
          {account.stores.map((store) => (
            <span key={store.id}>{store.name}</span>
          ))}
        </div>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 120,
      render: (_, account) => (
        <div className="account-status">
          <Tag color={account.is_active ? 'success' : 'default'}>
            {account.is_active ? '正常' : '已停用'}
          </Tag>
          {account.id === currentAdminId ? <span>当前账号</span> : null}
        </div>
      ),
    },
    {
      title: '最近更新',
      dataIndex: 'updated_at',
      width: 170,
      render: (value: string) => formatTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 150,
      render: (_, account) => (
        <div className="table-actions">
          <Tooltip title="编辑账号">
            <Button
              type="text"
              icon={<Pencil size={17} aria-hidden="true" />}
              aria-label={`编辑${account.username}`}
              onClick={() => openEdit(account)}
            />
          </Tooltip>
          <Tooltip title="重置密码">
            <Button
              type="text"
              icon={<KeyRound size={17} aria-hidden="true" />}
              aria-label={`重置${account.username}密码`}
              onClick={() => {
                setPasswordAccount(account)
                setIsPasswordModalOpen(true)
              }}
            />
          </Tooltip>
          <Tooltip title={account.is_active ? '停用账号' : '启用账号'}>
            <Switch
              size="small"
              checked={account.is_active}
              loading={updatingId === account.id}
              disabled={account.id === currentAdminId}
              aria-label={`${account.is_active ? '停用' : '启用'}${account.username}`}
              onChange={(checked) => void toggleAccount(account, checked)}
            />
          </Tooltip>
        </div>
      ),
    },
  ]

  const hasError = optionsQuery.isError || accountsQuery.isError

  return (
    <section className="stores-page accounts-page">
      <header className="page-heading">
        <div>
          <h1>运营账号</h1>
          <span>
            {accountsQuery.data
              ? `共 ${accountsQuery.data.total} 个子门店账号`
              : '管理角色与门店授权'}
          </span>
        </div>
        <Button
          type="primary"
          icon={<Plus size={18} aria-hidden="true" />}
          disabled={!options || roleOptions.length === 0 || storeOptions.length === 0}
          onClick={openCreate}
        >
          创建账号
        </Button>
      </header>

      <div className="store-toolbar account-toolbar">
        <Input
          className="store-search"
          value={keywordInput}
          allowClear
          prefix={<Search size={16} aria-hidden="true" />}
          placeholder="搜索账号用户名"
          onChange={(event) => setKeywordInput(event.target.value)}
          onPressEnter={search}
        />
        <Button icon={<Search size={17} aria-hidden="true" />} onClick={search}>
          查询
        </Button>
        <Tooltip title="刷新账号列表">
          <Button
            icon={<RefreshCw size={17} aria-hidden="true" />}
            aria-label="刷新账号列表"
            onClick={() => void accountsQuery.refetch()}
          />
        </Tooltip>
      </div>

      {hasError ? (
        <Alert
          className="page-alert"
          type="error"
          showIcon
          message="运营账号加载失败"
          description="请确认当前登录账号具有平台管理员权限"
        />
      ) : (
        <div className="table-surface">
          <Table<AdminUserRead>
            rowKey="id"
            size="middle"
            loading={
              optionsQuery.isLoading ||
              accountsQuery.isLoading ||
              accountsQuery.isFetching
            }
            columns={columns}
            dataSource={accountsQuery.data?.items ?? []}
            scroll={{ x: 1100 }}
            pagination={{
              current: page,
              pageSize,
              total: accountsQuery.data?.total ?? 0,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 个账号`,
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPageSize === pageSize ? nextPage : 1)
                setPageSize(nextPageSize)
              },
            }}
          />
        </div>
      )}

      <Modal
        title={editingAccount ? '编辑运营账号' : '创建运营账号'}
        open={isAccountModalOpen}
        width={560}
        okText="保存"
        cancelText="取消"
        confirmLoading={updatingId === (editingAccount?.id ?? 'new')}
        destroyOnHidden
        afterOpenChange={(open) => {
          if (!open) {
            return
          }
          accountForm.setFieldsValue(
            editingAccount
              ? {
                  role_code: editingAccount.roles[0]?.code,
                  store_ids: editingAccount.stores.map((store) => store.id),
                  is_active: editingAccount.is_active,
                }
              : {
                  role_code: roleOptions[0]?.value,
                  store_ids: [],
                  is_active: true,
                },
          )
        }}
        onOk={() => accountForm.submit()}
        onCancel={() => setIsAccountModalOpen(false)}
      >
        <Form<AccountFormValues>
          form={accountForm}
          className="account-form"
          layout="vertical"
          requiredMark={false}
          preserve={false}
          onFinish={(values) => void submitAccount(values)}
        >
          {!editingAccount ? (
            <>
              <Form.Item
                name="username"
                label="登录账号"
                rules={[
                  { required: true, message: '请输入登录账号' },
                  { min: 3, max: 64, message: '请输入 3-64 个字符' },
                ]}
              >
                <Input placeholder="用于后台登录的账号名" />
              </Form.Item>
              <Form.Item
                name="password"
                label="初始密码"
                rules={[
                  { required: true, message: '请输入初始密码' },
                  { min: 12, message: '密码至少 12 位' },
                ]}
              >
                <Input.Password placeholder="至少 12 位字符" />
              </Form.Item>
            </>
          ) : null}
          <Form.Item
            name="role_code"
            label="运营角色"
            rules={[{ required: true, message: '请选择运营角色' }]}
          >
            <Select options={roleOptions} placeholder="选择角色" />
          </Form.Item>
          <Form.Item
            name="store_ids"
            label="授权门店"
            rules={[{ required: true, message: '至少授权一个门店' }]}
          >
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              options={storeOptions}
              placeholder="选择可运营的门店"
            />
          </Form.Item>
          {editingAccount ? (
            <Form.Item name="is_active" label="账号状态" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
          ) : null}
        </Form>
      </Modal>

      <Modal
        title={`重置 ${passwordAccount?.username ?? ''} 的密码`}
        open={isPasswordModalOpen}
        okText="确认重置"
        cancelText="取消"
        confirmLoading={updatingId === passwordAccount?.id}
        destroyOnHidden
        onOk={() => passwordForm.submit()}
        onCancel={() => setIsPasswordModalOpen(false)}
      >
        <Form<PasswordFormValues>
          form={passwordForm}
          className="account-form"
          layout="vertical"
          requiredMark={false}
          onFinish={(values) => void resetPassword(values)}
        >
          <Form.Item
            name="password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 12, message: '密码至少 12 位' },
            ]}
          >
            <Input.Password placeholder="至少 12 位字符" />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}
