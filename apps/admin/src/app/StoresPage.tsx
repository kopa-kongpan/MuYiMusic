import type { StoreRead, StoreStatus } from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  App as AntdApp,
  Button,
  Empty,
  Input,
  Popconfirm,
  Select,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import type { TableProps } from 'antd'
import {
  MapPin,
  Pencil,
  Phone,
  Plus,
  Power,
  RefreshCw,
  Search,
} from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'
import { StoreFormModal } from './StoreFormModal'

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function StoresPage() {
  const { message } = AntdApp.useApp()
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<StoreStatus | undefined>()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editingStore, setEditingStore] = useState<StoreRead | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [updatingStoreId, setUpdatingStoreId] = useState<string | null>(null)

  const storesQuery = useQuery({
    queryKey: ['admin-stores', keyword, status, page, pageSize],
    queryFn: () =>
      apiClient.listAdminStores({ keyword, status, page, pageSize }),
  })

  function search() {
    setPage(1)
    setKeyword(keywordInput.trim())
  }

  async function toggleStore(store: StoreRead) {
    setUpdatingStoreId(store.id)
    try {
      const nextStatus: StoreStatus =
        store.status === 'active' ? 'inactive' : 'active'
      await apiClient.updateStore(store.id, { status: nextStatus })
      await storesQuery.refetch()
      void message.success(nextStatus === 'active' ? '门店已启用' : '门店已停用')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '操作失败')
    } finally {
      setUpdatingStoreId(null)
    }
  }

  const columns: NonNullable<TableProps<StoreRead>['columns']> = [
      {
        title: '门店',
        dataIndex: 'name',
        width: 220,
        render: (name: string, store) => (
          <div className="store-cell">
            <strong>{name}</strong>
            <span>排序 {store.sort_order}</span>
          </div>
        ),
      },
      {
        title: '地址',
        key: 'address',
        width: 320,
        render: (_, store) => (
          <div className="store-detail-cell">
            <span>
              <MapPin size={15} aria-hidden="true" />
              {store.city}
              {store.district} {store.address}
            </span>
            <span>
              <Phone size={15} aria-hidden="true" />
              {store.phone}
            </span>
          </div>
        ),
      },
      {
        title: '坐标',
        key: 'coordinates',
        width: 170,
        render: (_, store) => (
          <span className="coordinate-text">
            {Number(store.latitude).toFixed(6)}, {Number(store.longitude).toFixed(6)}
          </span>
        ),
      },
      {
        title: '状态',
        dataIndex: 'status',
        width: 100,
        render: (storeStatus: StoreStatus) =>
          storeStatus === 'active' ? (
            <Tag color="success">营业中</Tag>
          ) : (
            <Tag>已停用</Tag>
          ),
      },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        width: 170,
        render: (value: string) => formatTime(value),
      },
      {
        title: '操作',
        key: 'actions',
        fixed: 'right',
        width: 140,
        render: (_, store) => {
          const isActive = store.status === 'active'
          return (
            <div className="table-actions">
              <Tooltip title="编辑门店">
                <Button
                  type="text"
                  icon={<Pencil size={17} aria-hidden="true" />}
                  aria-label={`编辑${store.name}`}
                  onClick={() => {
                    setEditingStore(store)
                    setIsModalOpen(true)
                  }}
                />
              </Tooltip>
              <Popconfirm
                title={isActive ? '停用门店？' : '启用门店？'}
                description={
                  isActive
                    ? '停用后，小程序将立即隐藏该门店。'
                    : '启用后，小程序用户可选择该门店。'
                }
                okText={isActive ? '确认停用' : '确认启用'}
                cancelText="取消"
                okButtonProps={{ danger: isActive }}
                onConfirm={() => toggleStore(store)}
              >
                <Tooltip title={isActive ? '停用门店' : '启用门店'}>
                  <Button
                    type="text"
                    danger={isActive}
                    loading={updatingStoreId === store.id}
                    icon={<Power size={17} aria-hidden="true" />}
                    aria-label={`${isActive ? '停用' : '启用'}${store.name}`}
                  />
                </Tooltip>
              </Popconfirm>
            </div>
          )
        },
      },
    ]

  return (
    <section className="stores-page">
      <header className="page-heading">
        <div>
          <h1>门店管理</h1>
          <span>{storesQuery.data ? `共 ${storesQuery.data.total} 家门店` : '门店资料'}</span>
        </div>
        <Button
          type="primary"
          icon={<Plus size={18} aria-hidden="true" />}
          onClick={() => {
            setEditingStore(null)
            setIsModalOpen(true)
          }}
        >
          创建门店
        </Button>
      </header>

      <div className="store-toolbar">
        <Input
          className="store-search"
          value={keywordInput}
          allowClear
          placeholder="搜索名称、城市或地址"
          prefix={<Search size={16} aria-hidden="true" />}
          onChange={(event) => setKeywordInput(event.target.value)}
          onPressEnter={search}
        />
        <Select<StoreStatus>
          className="status-filter"
          allowClear
          value={status}
          placeholder="全部状态"
          options={[
            { label: '营业中', value: 'active' },
            { label: '已停用', value: 'inactive' },
          ]}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
        <Button icon={<Search size={17} aria-hidden="true" />} onClick={search}>
          查询
        </Button>
        <Tooltip title="刷新列表">
          <Button
            icon={<RefreshCw size={17} aria-hidden="true" />}
            aria-label="刷新门店列表"
            onClick={() => void storesQuery.refetch()}
          />
        </Tooltip>
      </div>

      {storesQuery.isError ? (
        <Alert
          className="page-alert"
          type="error"
          showIcon
          message="门店列表加载失败"
          description={
            storesQuery.error instanceof Error
              ? storesQuery.error.message
              : '请稍后重试'
          }
          action={
            <Button size="small" onClick={() => void storesQuery.refetch()}>
              重试
            </Button>
          }
        />
      ) : (
        <div className="table-surface">
          <Table<StoreRead>
            rowKey="id"
            size="middle"
            loading={storesQuery.isLoading || storesQuery.isFetching}
            columns={columns}
            dataSource={storesQuery.data?.items ?? []}
            scroll={{ x: 1100 }}
            locale={{
              emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无门店" />,
            }}
            pagination={{
              current: page,
              pageSize,
              total: storesQuery.data?.total ?? 0,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条`,
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPageSize === pageSize ? nextPage : 1)
                setPageSize(nextPageSize)
              },
            }}
          />
        </div>
      )}

      <StoreFormModal
        open={isModalOpen}
        store={editingStore}
        onClose={() => setIsModalOpen(false)}
        onSaved={async () => {
          await storesQuery.refetch()
        }}
      />
    </section>
  )
}
