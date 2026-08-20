import type {
  NotificationDeliveryRead,
  NotificationDeliveryStatus,
} from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import { App as AntdApp, Button, Select, Table, Tag, Tooltip } from 'antd'
import type { TableColumnsType } from 'antd'
import { RefreshCw, RotateCcw } from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'

const labels: Record<NotificationDeliveryStatus, string> = {
  pending: '待投递',
  sent: '已发送',
  skipped: '已跳过',
  failed: '失败',
}

const colors: Record<NotificationDeliveryStatus, string> = {
  pending: 'processing',
  sent: 'success',
  skipped: 'default',
  failed: 'error',
}

export function NotificationDeliveriesPage() {
  const { message } = AntdApp.useApp()
  const [status, setStatus] = useState<NotificationDeliveryStatus>()
  const [page, setPage] = useState(1)
  const [retryingId, setRetryingId] = useState<string | null>(null)
  const query = useQuery({
    queryKey: ['notification-deliveries', status, page],
    queryFn: () => apiClient.listNotificationDeliveries(status, page, 20),
  })

  async function retry(item: NotificationDeliveryRead) {
    setRetryingId(item.id)
    try {
      await apiClient.retryNotificationDelivery(item.id)
      await query.refetch()
      void message.success('已重新加入投递队列')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '重试失败')
    } finally {
      setRetryingId(null)
    }
  }

  const columns: TableColumnsType<NotificationDeliveryRead> = [
    {
      title: '消息',
      key: 'message',
      render: (_, item) => (
        <div className="appointment-primary-cell">
          <strong>{item.title}</strong>
          <span>{item.kind}</span>
        </div>
      ),
    },
    { title: '模板', dataIndex: 'template_key', key: 'template_key' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: NotificationDeliveryStatus) => (
        <Tag color={colors[value]}>{labels[value]}</Tag>
      ),
    },
    { title: '尝试', dataIndex: 'attempts', key: 'attempts', width: 76 },
    {
      title: '结果',
      key: 'result',
      render: (_, item) => item.last_error ?? (item.sent_at ? '发送成功' : '—'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 72,
      render: (_, item) => (
        <Tooltip title="重新投递">
          <Button
            type="text"
            icon={<RotateCcw size={16} aria-hidden="true" />}
            aria-label={`重新投递${item.title}`}
            loading={retryingId === item.id}
            disabled={item.status === 'sent'}
            onClick={() => void retry(item)}
          />
        </Tooltip>
      ),
    },
  ]

  return (
    <section className="stores-page appointments-page">
      <div className="page-heading-row">
        <div>
          <h1>消息投递</h1>
          <p>查看微信订阅消息结果并处理失败投递</p>
        </div>
      </div>
      <div className="store-toolbar">
        <Select
          allowClear
          value={status}
          placeholder="全部状态"
          options={Object.entries(labels).map(([value, label]) => ({ value, label }))}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
        <Tooltip title="刷新投递记录">
          <Button
            icon={<RefreshCw size={16} aria-hidden="true" />}
            aria-label="刷新投递记录"
            onClick={() => void query.refetch()}
          />
        </Tooltip>
      </div>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={query.data?.items ?? []}
        loading={query.isLoading || query.isFetching}
        pagination={{
          current: page,
          pageSize: 20,
          total: query.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
      />
    </section>
  )
}
