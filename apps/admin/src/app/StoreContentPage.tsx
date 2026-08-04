import type {
  ContentBlockRead,
  ContentBlockStatus,
  ContentBlockType,
} from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  App as AntdApp,
  Button,
  Empty,
  Image,
  Select,
  Switch,
  Table,
  Tooltip,
} from 'antd'
import type { TableProps } from 'antd'
import {
  ArrowDown,
  ArrowUp,
  Eye,
  ImageIcon,
  LayoutDashboard,
  Pencil,
  Plus,
  RefreshCw,
  Video,
} from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'
import { ContentFormModal } from './ContentFormModal'
import { ContentPreviewDrawer } from './ContentPreviewDrawer'

const typeLabels: Record<ContentBlockType, string> = {
  image: '图片',
  video: '视频',
  shortcut: '快捷入口',
}

function formatDisplayWindow(content: ContentBlockRead): string {
  const formatter = new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  if (!content.starts_at && !content.ends_at) {
    return '长期展示'
  }
  const start = content.starts_at
    ? formatter.format(new Date(content.starts_at))
    : '立即'
  const end = content.ends_at ? formatter.format(new Date(content.ends_at)) : '不限'
  return `${start} - ${end}`
}

export function StoreContentPage() {
  const { message } = AntdApp.useApp()
  const [storeId, setStoreId] = useState<string>()
  const [blockType, setBlockType] = useState<ContentBlockType>()
  const [status, setStatus] = useState<ContentBlockStatus>()
  const [editingContent, setEditingContent] = useState<ContentBlockRead | null>(null)
  const [previewContent, setPreviewContent] = useState<ContentBlockRead | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const storesQuery = useQuery({
    queryKey: ['admin-stores-for-content'],
    queryFn: () => apiClient.listAdminStores({ pageSize: 100 }),
  })

  const activeStoreId = storeId ?? storesQuery.data?.items[0]?.id

  const contentQuery = useQuery({
    queryKey: ['admin-store-content', activeStoreId, blockType, status],
    queryFn: () =>
      apiClient.listStoreContent(activeStoreId!, {
        blockType,
        status,
        pageSize: 100,
      }),
    enabled: Boolean(activeStoreId),
  })

  const selectedStore =
    storesQuery.data?.items.find((store) => store.id === activeStoreId) ?? null
  const items = contentQuery.data?.items ?? []
  const hasActiveFilters = Boolean(blockType || status)

  async function toggleContent(content: ContentBlockRead, isEnabled: boolean) {
    if (!activeStoreId) {
      return
    }
    setUpdatingId(content.id)
    try {
      await apiClient.updateStoreContent(activeStoreId, content.id, {
        status: isEnabled ? 'enabled' : 'disabled',
      })
      await contentQuery.refetch()
      void message.success(isEnabled ? '内容已启用' : '内容已停用')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '操作失败')
    } finally {
      setUpdatingId(null)
    }
  }

  async function moveContent(index: number, direction: -1 | 1) {
    if (!activeStoreId) {
      return
    }
    if (hasActiveFilters) {
      void message.info('请先清除类型和状态筛选，再调整展示顺序')
      return
    }
    const targetIndex = index + direction
    if (targetIndex < 0 || targetIndex >= items.length) {
      return
    }
    const reordered = [...items]
    const [moved] = reordered.splice(index, 1)
    if (!moved) {
      return
    }
    reordered.splice(targetIndex, 0, moved)
    setUpdatingId(moved.id)
    try {
      await apiClient.reorderStoreContent(activeStoreId, {
        items: reordered.map((item, itemIndex) => ({
          id: item.id,
          sort_order: (itemIndex + 1) * 10,
        })),
      })
      await contentQuery.refetch()
      void message.success('展示顺序已更新')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '排序失败')
    } finally {
      setUpdatingId(null)
    }
  }

  const columns: NonNullable<TableProps<ContentBlockRead>['columns']> = [
    {
      title: '顺序',
      key: 'order',
      width: 106,
      render: (_, content, index) => (
        <div className="order-actions">
          <Tooltip
            title={hasActiveFilters ? '清除类型和状态筛选后可调整顺序' : '上移'}
          >
            <Button
              type="text"
              size="small"
              disabled={hasActiveFilters || index === 0}
              loading={updatingId === content.id}
              icon={<ArrowUp size={16} aria-hidden="true" />}
              aria-label={`上移${content.title}`}
              onClick={() => void moveContent(index, -1)}
            />
          </Tooltip>
          <Tooltip
            title={hasActiveFilters ? '清除类型和状态筛选后可调整顺序' : '下移'}
          >
            <Button
              type="text"
              size="small"
              disabled={hasActiveFilters || index === items.length - 1}
              icon={<ArrowDown size={16} aria-hidden="true" />}
              aria-label={`下移${content.title}`}
              onClick={() => void moveContent(index, 1)}
            />
          </Tooltip>
          <span>{content.sort_order}</span>
        </div>
      ),
    },
    {
      title: '内容',
      key: 'content',
      width: 290,
      render: (_, content) => (
        <div className="content-cell">
          <div className="content-thumbnail">
            {content.block_type === 'image' && content.media_url ? (
              <Image
                src={content.media_url}
                alt=""
                width={72}
                height={48}
                preview={false}
              />
            ) : content.block_type === 'video' ? (
              <Video size={22} aria-hidden="true" />
            ) : content.block_type === 'image' ? (
              <ImageIcon size={22} aria-hidden="true" />
            ) : (
              <LayoutDashboard size={22} aria-hidden="true" />
            )}
          </div>
          <div>
            <strong>{content.title}</strong>
            <span>{typeLabels[content.block_type]}</span>
          </div>
        </div>
      ),
    },
    {
      title: '跳转目标',
      key: 'jump',
      width: 250,
      render: (_, content) => (
        <span className="target-text">
          {content.jump_type === 'none' ? '不跳转' : content.jump_target}
        </span>
      ),
    },
    {
      title: '展示时间',
      key: 'window',
      width: 210,
      render: (_, content) => (
        <span className="window-text">{formatDisplayWindow(content)}</span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (contentStatus: ContentBlockStatus, content) => (
        <Switch
          size="small"
          checked={contentStatus === 'enabled'}
          loading={updatingId === content.id}
          aria-label={`${contentStatus === 'enabled' ? '停用' : '启用'}${content.title}`}
          onChange={(checked) => void toggleContent(content, checked)}
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 100,
      render: (_, content) => (
        <div className="table-actions">
          <Tooltip title="预览内容">
            <Button
              type="text"
              icon={<Eye size={17} aria-hidden="true" />}
              aria-label={`预览${content.title}`}
              onClick={() => setPreviewContent(content)}
            />
          </Tooltip>
          <Tooltip title="编辑内容">
            <Button
              type="text"
              icon={<Pencil size={17} aria-hidden="true" />}
              aria-label={`编辑${content.title}`}
              onClick={() => {
                setEditingContent(content)
                setIsFormOpen(true)
              }}
            />
          </Tooltip>
        </div>
      ),
    },
  ]

  return (
    <section className="stores-page content-page">
      <header className="page-heading">
        <div>
          <h1>首页内容</h1>
          <span>
            {selectedStore
              ? `${selectedStore.name} · ${contentQuery.data?.total ?? 0} 条内容`
              : '按门店维护展示内容'}
          </span>
        </div>
        <Button
          type="primary"
          disabled={!selectedStore}
          icon={<Plus size={18} aria-hidden="true" />}
          onClick={() => {
            setEditingContent(null)
            setIsFormOpen(true)
          }}
        >
          创建内容
        </Button>
      </header>

      <div className="store-toolbar content-toolbar">
        <Select<string>
          className="content-store-select"
          value={activeStoreId}
          loading={storesQuery.isLoading}
          placeholder="选择门店"
          options={(storesQuery.data?.items ?? []).map((store) => ({
            label: store.name,
            value: store.id,
          }))}
          onChange={setStoreId}
        />
        <Select<ContentBlockType>
          className="status-filter"
          allowClear
          value={blockType}
          placeholder="全部类型"
          options={Object.entries(typeLabels).map(([value, label]) => ({
            value: value as ContentBlockType,
            label,
          }))}
          onChange={setBlockType}
        />
        <Select<ContentBlockStatus>
          className="status-filter"
          allowClear
          value={status}
          placeholder="全部状态"
          options={[
            { label: '已启用', value: 'enabled' },
            { label: '已停用', value: 'disabled' },
          ]}
          onChange={setStatus}
        />
        <Tooltip title="刷新列表">
          <Button
            disabled={!activeStoreId}
            icon={<RefreshCw size={17} aria-hidden="true" />}
            aria-label="刷新内容列表"
            onClick={() => void contentQuery.refetch()}
          />
        </Tooltip>
      </div>

      {storesQuery.isError || contentQuery.isError ? (
        <Alert
          className="page-alert"
          type="error"
          showIcon
          message="首页内容加载失败"
          description={
            storesQuery.error instanceof Error
              ? storesQuery.error.message
              : contentQuery.error instanceof Error
                ? contentQuery.error.message
                : '请稍后重试'
          }
        />
      ) : (
        <div className="table-surface">
          <Table<ContentBlockRead>
            rowKey="id"
            size="middle"
            loading={
              storesQuery.isLoading ||
              contentQuery.isLoading ||
              contentQuery.isFetching
            }
            columns={columns}
            dataSource={items}
            pagination={false}
            scroll={{ x: 1070 }}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={activeStoreId ? '该门店暂无首页内容' : '请先选择门店'}
                />
              ),
            }}
          />
        </div>
      )}

      {selectedStore ? (
        <ContentFormModal
          open={isFormOpen}
          store={selectedStore}
          content={editingContent}
          onClose={() => setIsFormOpen(false)}
          onSaved={async () => {
            await contentQuery.refetch()
          }}
        />
      ) : null}

      <ContentPreviewDrawer
        open={Boolean(previewContent)}
        store={selectedStore}
        content={previewContent}
        onClose={() => setPreviewContent(null)}
      />
    </section>
  )
}
