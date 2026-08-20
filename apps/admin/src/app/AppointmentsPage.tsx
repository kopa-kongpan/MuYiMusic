import type {
  AppointmentRead,
  AppointmentStatus,
} from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  App as AntdApp,
  Button,
  Input,
  Modal,
  Select,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import type { TableProps } from 'antd'
import {
  CheckCircle2,
  RefreshCw,
  RotateCcw,
  UserX,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'
import { DateRangeFilter } from './DateRangeFilter'
import { dateRangeWindow, presetDateRange } from './dateRange'
import { getAdminSession } from './session'

const statusLabels: Record<AppointmentStatus, string> = {
  reserved: '已预约',
  cancelled: '已取消',
  completed: '已消课',
  no_show: '缺席扣课',
}

const statusColors: Record<AppointmentStatus, string> = {
  reserved: 'blue',
  cancelled: 'default',
  completed: 'green',
  no_show: 'orange',
}

type ActionKind = 'cancel' | 'consume' | 'no_show' | 'reverse'

interface AppointmentAction {
  kind: ActionKind
  appointment: AppointmentRead
  idempotencyKey: string
}

function formatTimeWindow(startsAt: string, endsAt: string): string {
  const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })
  const timeFormatter = new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return `${dateFormatter.format(new Date(startsAt))} ${timeFormatter.format(
    new Date(startsAt),
  )} - ${timeFormatter.format(new Date(endsAt))}`
}

function actionLabel(kind: ActionKind): string {
  if (kind === 'cancel') return '取消预约'
  if (kind === 'consume') return '确认消课'
  if (kind === 'no_show') return '登记缺席'
  return '撤销消课'
}

function createIdempotencyKey(kind: ActionKind, appointmentId: string): string {
  return `${kind}-${appointmentId}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function AppointmentsPage() {
  const { message } = AntdApp.useApp()
  const session = getAdminSession()
  const permissions = session?.admin.permissions ?? []
  const canSettle = permissions.includes('consumptions:manage')
  const canReverse = permissions.includes('consumptions:reverse')
  const [storeId, setStoreId] = useState<string>()
  const [dateRange, setDateRange] = useState(() => presetDateRange('this-week'))
  const [status, setStatus] = useState<AppointmentStatus>()
  const [keyword, setKeyword] = useState('')
  const [submittedKeyword, setSubmittedKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [action, setAction] = useState<AppointmentAction | null>(null)
  const [actionText, setActionText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const storesQuery = useQuery({
    queryKey: ['admin-stores-for-appointments'],
    queryFn: () => apiClient.listAdminStores({ pageSize: 100 }),
  })
  const activeStoreId = storeId ?? storesQuery.data?.items[0]?.id
  const appointmentsQuery = useQuery({
    queryKey: [
      'admin-appointments',
      activeStoreId,
      dateRange.startDate,
      dateRange.endDate,
      status,
      submittedKeyword,
      page,
      pageSize,
    ],
    queryFn: () =>
      apiClient.listAdminAppointments(activeStoreId!, {
        ...dateRangeWindow(dateRange),
        status,
        keyword: submittedKeyword || undefined,
        page,
        pageSize,
      }),
    enabled: Boolean(activeStoreId),
  })
  const selectedStore =
    storesQuery.data?.items.find((store) => store.id === activeStoreId) ?? null

  function openAction(kind: ActionKind, appointment: AppointmentRead) {
    setAction({
      kind,
      appointment,
      idempotencyKey: createIdempotencyKey(kind, appointment.id),
    })
    setActionText('')
  }

  async function submitAction() {
    if (!action || !activeStoreId) return
    const text = actionText.trim()
    if ((action.kind === 'cancel' || action.kind === 'reverse') && !text) {
      void message.warning('请填写操作原因')
      return
    }
    setIsSubmitting(true)
    try {
      if (action.kind === 'cancel') {
        await apiClient.cancelAdminAppointment(
          activeStoreId,
          action.appointment.id,
          { reason: text },
          action.idempotencyKey,
        )
      } else if (action.kind === 'consume') {
        await apiClient.consumeAppointment(
          activeStoreId,
          action.appointment.id,
          { notes: text },
          action.idempotencyKey,
        )
      } else if (action.kind === 'no_show') {
        await apiClient.markAppointmentNoShow(
          activeStoreId,
          action.appointment.id,
          { notes: text },
          action.idempotencyKey,
        )
      } else if (action.appointment.active_consumption_id) {
        await apiClient.reverseConsumption(
          activeStoreId,
          action.appointment.active_consumption_id,
          { reason: text },
          action.idempotencyKey,
        )
      }
      setAction(null)
      setActionText('')
      await appointmentsQuery.refetch()
      void message.success(`${actionLabel(action.kind)}成功`)
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '操作失败')
    } finally {
      setIsSubmitting(false)
    }
  }

  const columns: NonNullable<TableProps<AppointmentRead>['columns']> = [
    {
      title: '预约号 / 学员',
      key: 'user',
      width: 210,
      render: (_, appointment) => (
        <div className="appointment-primary-cell">
          <strong>{appointment.user_nickname}</strong>
          <span>{appointment.appointment_no}</span>
        </div>
      ),
    },
    {
      title: '课程',
      key: 'course',
      width: 240,
      render: (_, appointment) => (
        <div className="appointment-primary-cell">
          <strong>{appointment.course_name}</strong>
          <span>{appointment.teacher_name}</span>
        </div>
      ),
    },
    {
      title: '上课时间',
      key: 'time',
      width: 160,
      render: (_, appointment) =>
        formatTimeWindow(appointment.starts_at, appointment.ends_at),
    },
    {
      title: '课程权益',
      key: 'entitlement',
      width: 220,
      render: (_, appointment) => (
        <div className="appointment-primary-cell">
          <strong>{appointment.entitlement_course_name}</strong>
          <span>
            可用 {appointment.entitlement_available_lessons}，锁定{' '}
            {appointment.entitlement_reserved_lessons}，剩余{' '}
            {appointment.entitlement_remaining_lessons}
          </span>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (appointmentStatus: AppointmentStatus) => (
        <Tag color={statusColors[appointmentStatus]}>
          {statusLabels[appointmentStatus]}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 180,
      render: (_, appointment) => (
        <div className="table-actions">
          {appointment.status === 'reserved' ? (
            <Tooltip title="取消预约">
              <Button
                type="text"
                danger
                icon={<XCircle size={17} aria-hidden="true" />}
                aria-label={`取消${appointment.user_nickname}的预约`}
                onClick={() => openAction('cancel', appointment)}
              />
            </Tooltip>
          ) : null}
          {canSettle && appointment.can_admin_settle ? (
            <>
              <Tooltip title="正常消课">
                <Button
                  type="text"
                  icon={<CheckCircle2 size={17} aria-hidden="true" />}
                  aria-label={`为${appointment.user_nickname}正常消课`}
                  onClick={() => openAction('consume', appointment)}
                />
              </Tooltip>
              <Tooltip title="登记缺席并扣课">
                <Button
                  type="text"
                  icon={<UserX size={17} aria-hidden="true" />}
                  aria-label={`登记${appointment.user_nickname}缺席`}
                  onClick={() => openAction('no_show', appointment)}
                />
              </Tooltip>
            </>
          ) : null}
          {canReverse && appointment.active_consumption_id ? (
            <Tooltip title="撤销消课">
              <Button
                type="text"
                icon={<RotateCcw size={17} aria-hidden="true" />}
                aria-label={`撤销${appointment.user_nickname}的消课`}
                onClick={() => openAction('reverse', appointment)}
              />
            </Tooltip>
          ) : null}
        </div>
      ),
    },
  ]

  const hasError = storesQuery.isError || appointmentsQuery.isError

  return (
    <section className="stores-page appointments-page">
      <header className="page-heading">
        <div>
          <h1>预约与消课</h1>
          <span>
            {selectedStore
              ? `${selectedStore.name} · ${appointmentsQuery.data?.total ?? 0} 条预约`
              : '管理学员预约、到课与课时扣减'}
          </span>
        </div>
      </header>

      <div className="store-toolbar appointment-toolbar">
        <Select<string>
          className="content-store-select"
          value={activeStoreId}
          loading={storesQuery.isLoading}
          placeholder="选择门店"
          options={(storesQuery.data?.items ?? []).map((store) => ({
            label: store.name,
            value: store.id,
          }))}
          onChange={(value) => {
            setStoreId(value)
            setPage(1)
          }}
        />
        <DateRangeFilter
          value={dateRange}
          labelPrefix="预约"
          onChange={(value) => {
            setDateRange(value)
            setPage(1)
          }}
        />
        <Select<AppointmentStatus>
          className="status-filter"
          allowClear
          value={status}
          placeholder="全部状态"
          options={Object.entries(statusLabels).map(([value, label]) => ({
            value: value as AppointmentStatus,
            label,
          }))}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
        <Input.Search
          className="appointment-keyword"
          allowClear
          value={keyword}
          placeholder="学员、手机号或预约号"
          enterButton="查询"
          onChange={(event) => setKeyword(event.target.value)}
          onSearch={(value) => {
            setSubmittedKeyword(value.trim())
            setPage(1)
          }}
        />
        <Tooltip title="刷新预约">
          <Button
            disabled={!activeStoreId}
            icon={<RefreshCw size={17} aria-hidden="true" />}
            aria-label="刷新预约列表"
            onClick={() => void appointmentsQuery.refetch()}
          />
        </Tooltip>
      </div>

      {hasError ? (
        <Alert
          className="page-alert"
          type="error"
          showIcon
          message="预约数据加载失败"
          description="请检查当前账号权限和门店授权后重试。"
        />
      ) : (
        <div className="table-surface">
          <Table<AppointmentRead>
            rowKey="id"
            size="middle"
            scroll={{ x: 1120 }}
            loading={
              storesQuery.isLoading ||
              appointmentsQuery.isLoading ||
              appointmentsQuery.isFetching
            }
            columns={columns}
            dataSource={appointmentsQuery.data?.items ?? []}
            pagination={{
              current: page,
              pageSize,
              total: appointmentsQuery.data?.total ?? 0,
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

      <Modal
        title={action ? actionLabel(action.kind) : ''}
        open={Boolean(action)}
        okText="确认"
        cancelText="返回"
        confirmLoading={isSubmitting}
        onOk={() => void submitAction()}
        onCancel={() => {
          if (!isSubmitting) setAction(null)
        }}
      >
        <p className="appointment-action-summary">
          {action
            ? `${action.appointment.user_nickname} · ${action.appointment.course_name} · ${formatTimeWindow(action.appointment.starts_at, action.appointment.ends_at)}`
            : ''}
        </p>
        <Input.TextArea
          value={actionText}
          rows={4}
          maxLength={action?.kind === 'cancel' || action?.kind === 'reverse' ? 500 : 1000}
          showCount
          placeholder={
            action?.kind === 'cancel' || action?.kind === 'reverse'
              ? '请填写操作原因'
              : '可填写到课或缺席备注'
          }
          onChange={(event) => setActionText(event.target.value)}
        />
      </Modal>
    </section>
  )
}
