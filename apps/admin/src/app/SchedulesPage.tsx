import type {
  ScheduleRead,
  ScheduleStatus,
} from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  App as AntdApp,
  Button,
  Input,
  Popconfirm,
  Select,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import type { TableProps } from 'antd'
import {
  CalendarPlus,
  CirclePause,
  Pencil,
  RefreshCw,
  RotateCcw,
  UserRoundCog,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'
import { ScheduleFormModal } from './ScheduleFormModal'
import { TeacherManagerModal } from './TeacherManagerModal'

const statusLabels: Record<ScheduleStatus, string> = {
  open: '开放预约',
  closed: '暂停预约',
  cancelled: '已取消',
}

const statusColors: Record<ScheduleStatus, string> = {
  open: 'green',
  closed: 'orange',
  cancelled: 'red',
}

function today(): string {
  const current = new Date()
  const local = new Date(current.getTime() - current.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function dayWindow(date: string): { startsFrom: string; startsBefore: string } {
  const startsFrom = new Date(`${date}T00:00:00`)
  const startsBefore = new Date(startsFrom)
  startsBefore.setDate(startsBefore.getDate() + 1)
  return {
    startsFrom: startsFrom.toISOString(),
    startsBefore: startsBefore.toISOString(),
  }
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function formatUpdatedAt(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export function SchedulesPage() {
  const { message } = AntdApp.useApp()
  const [storeId, setStoreId] = useState<string>()
  const [selectedDate, setSelectedDate] = useState(today)
  const [teacherId, setTeacherId] = useState<string>()
  const [status, setStatus] = useState<ScheduleStatus>()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editingSchedule, setEditingSchedule] = useState<ScheduleRead | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [isTeacherManagerOpen, setIsTeacherManagerOpen] = useState(false)
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const storesQuery = useQuery({
    queryKey: ['admin-stores-for-schedules'],
    queryFn: () => apiClient.listAdminStores({ pageSize: 100 }),
  })
  const activeStoreId = storeId ?? storesQuery.data?.items[0]?.id
  const teachersQuery = useQuery({
    queryKey: ['admin-schedule-teachers', activeStoreId],
    queryFn: () => apiClient.listAdminTeachers(activeStoreId!, { pageSize: 100 }),
    enabled: Boolean(activeStoreId),
  })
  const productsQuery = useQuery({
    queryKey: ['admin-published-products-for-schedules', activeStoreId],
    queryFn: () =>
      apiClient.listAdminProducts(activeStoreId!, {
        status: 'published',
        pageSize: 100,
      }),
    enabled: Boolean(activeStoreId),
  })
  const schedulesQuery = useQuery({
    queryKey: [
      'admin-schedules',
      activeStoreId,
      selectedDate,
      teacherId,
      status,
      page,
      pageSize,
    ],
    queryFn: () =>
      apiClient.listAdminSchedules(activeStoreId!, {
        ...dayWindow(selectedDate),
        teacherId,
        status,
        page,
        pageSize,
      }),
    enabled: Boolean(activeStoreId),
  })

  const selectedStore =
    storesQuery.data?.items.find((store) => store.id === activeStoreId) ?? null
  const teachers = teachersQuery.data?.items ?? []
  const products = productsQuery.data?.items ?? []

  async function refreshSchedules() {
    await schedulesQuery.refetch()
  }

  async function refreshTeachers() {
    await teachersQuery.refetch()
  }

  async function changeStatus(schedule: ScheduleRead, nextStatus: ScheduleStatus) {
    if (!activeStoreId) {
      return
    }
    setUpdatingId(schedule.id)
    try {
      await apiClient.changeScheduleStatus(activeStoreId, schedule.id, {
        status: nextStatus,
      })
      await refreshSchedules()
      void message.success(
        nextStatus === 'open'
          ? '排课已重新开放'
          : nextStatus === 'closed'
            ? '排课已暂停预约'
            : '排课已取消',
      )
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '状态变更失败')
    } finally {
      setUpdatingId(null)
    }
  }

  const columns: NonNullable<TableProps<ScheduleRead>['columns']> = [
    {
      title: '时间',
      key: 'time',
      width: 150,
      render: (_, schedule) => (
        <div className="schedule-time-cell">
          <strong>{formatTime(schedule.starts_at)}</strong>
          <span>至 {formatTime(schedule.ends_at)}</span>
        </div>
      ),
    },
    {
      title: '课程与教师',
      key: 'course',
      width: 260,
      render: (_, schedule) => (
        <div className="schedule-course-cell">
          <strong>{schedule.course_name}</strong>
          <span>{schedule.teacher_name}</span>
        </div>
      ),
    },
    {
      title: '名额',
      key: 'capacity',
      width: 130,
      render: (_, schedule) => (
        <div className="schedule-capacity-cell">
          <strong>{schedule.available_slots}</strong>
          <span>
            剩余 / {schedule.capacity}，已约 {schedule.reserved_count}
          </span>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (scheduleStatus: ScheduleStatus) => (
        <Tag color={statusColors[scheduleStatus]}>{statusLabels[scheduleStatus]}</Tag>
      ),
    },
    {
      title: '到课说明',
      dataIndex: 'notes',
      width: 220,
      ellipsis: true,
      render: (notes: string) => notes || '—',
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 150,
      render: (value: string) => formatUpdatedAt(value),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 170,
      render: (_, schedule) => (
        <div className="table-actions">
          <Tooltip title={schedule.status === 'cancelled' ? '已取消排课不可编辑' : '编辑排课'}>
            <Button
              type="text"
              disabled={schedule.status === 'cancelled'}
              icon={<Pencil size={17} aria-hidden="true" />}
              aria-label={`编辑${schedule.course_name}`}
              onClick={() => {
                setEditingSchedule(schedule)
                setIsFormOpen(true)
              }}
            />
          </Tooltip>
          {schedule.status === 'open' ? (
            <Popconfirm
              title={`暂停“${schedule.course_name}”的预约？`}
              description="暂停后可重新开放。"
              okText="确认暂停"
              cancelText="取消"
              onConfirm={() => void changeStatus(schedule, 'closed')}
            >
              <Tooltip title="暂停预约">
                <Button
                  type="text"
                  loading={updatingId === schedule.id}
                  icon={<CirclePause size={17} aria-hidden="true" />}
                  aria-label={`暂停${schedule.course_name}`}
                />
              </Tooltip>
            </Popconfirm>
          ) : null}
          {schedule.status === 'closed' ? (
            <Popconfirm
              title={`重新开放“${schedule.course_name}”？`}
              okText="确认开放"
              cancelText="取消"
              onConfirm={() => void changeStatus(schedule, 'open')}
            >
              <Tooltip title="重新开放">
                <Button
                  type="text"
                  loading={updatingId === schedule.id}
                  icon={<RotateCcw size={17} aria-hidden="true" />}
                  aria-label={`重新开放${schedule.course_name}`}
                />
              </Tooltip>
            </Popconfirm>
          ) : null}
          {schedule.status !== 'cancelled' ? (
            <Popconfirm
              title={`确认取消“${schedule.course_name}”？`}
              description="取消后不能恢复；若已有预约，需要先处理受影响用户。"
              okText="确认取消"
              cancelText="返回"
              onConfirm={() => void changeStatus(schedule, 'cancelled')}
            >
              <Tooltip title="取消排课">
                <Button
                  type="text"
                  danger
                  loading={updatingId === schedule.id}
                  icon={<XCircle size={17} aria-hidden="true" />}
                  aria-label={`取消${schedule.course_name}`}
                />
              </Tooltip>
            </Popconfirm>
          ) : null}
        </div>
      ),
    },
  ]

  const hasError =
    storesQuery.isError ||
    teachersQuery.isError ||
    productsQuery.isError ||
    schedulesQuery.isError

  return (
    <section className="stores-page schedules-page">
      <header className="page-heading">
        <div>
          <h1>排课管理</h1>
          <span>
            {selectedStore
              ? `${selectedStore.name} · ${schedulesQuery.data?.total ?? 0} 节排课`
              : '按门店维护教师与可预约时段'}
          </span>
        </div>
        <div className="page-heading-actions">
          <Button
            disabled={!selectedStore}
            icon={<UserRoundCog size={18} aria-hidden="true" />}
            onClick={() => setIsTeacherManagerOpen(true)}
          >
            教师管理
          </Button>
          <Button
            type="primary"
            disabled={!selectedStore || !teachers.some((teacher) => teacher.is_active)}
            icon={<CalendarPlus size={18} aria-hidden="true" />}
            onClick={() => {
              setEditingSchedule(null)
              setIsFormOpen(true)
            }}
          >
            创建排课
          </Button>
        </div>
      </header>

      <div className="store-toolbar schedule-toolbar">
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
            setTeacherId(undefined)
            setPage(1)
          }}
        />
        <Input
          className="schedule-date-input"
          type="date"
          value={selectedDate}
          aria-label="排课日期"
          onChange={(event) => {
            if (event.target.value) {
              setSelectedDate(event.target.value)
              setPage(1)
            }
          }}
        />
        <Select<string>
          className="status-filter"
          allowClear
          value={teacherId}
          placeholder="全部教师"
          options={teachers.map((teacher) => ({
            value: teacher.id,
            label: teacher.is_active ? teacher.name : `${teacher.name}（停用）`,
          }))}
          onChange={(value) => {
            setTeacherId(value)
            setPage(1)
          }}
        />
        <Select<ScheduleStatus>
          className="status-filter"
          allowClear
          value={status}
          placeholder="全部状态"
          options={Object.entries(statusLabels).map(([value, label]) => ({
            value: value as ScheduleStatus,
            label,
          }))}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
        <Tooltip title="刷新排课">
          <Button
            disabled={!activeStoreId}
            icon={<RefreshCw size={17} aria-hidden="true" />}
            aria-label="刷新排课列表"
            onClick={() => void refreshSchedules()}
          />
        </Tooltip>
      </div>

      {!hasError && teachersQuery.isSuccess && teachers.length === 0 ? (
        <Alert
          className="page-alert schedule-guide-alert"
          type="info"
          showIcon
          message="请先添加教师"
          description="创建排课前需要在当前门店至少添加一位启用教师。"
          action={
            <Button size="small" onClick={() => setIsTeacherManagerOpen(true)}>
              教师管理
            </Button>
          }
        />
      ) : null}

      {hasError ? (
        <Alert
          className="page-alert"
          type="error"
          showIcon
          message="排课数据加载失败"
          description="请检查当前账号权限和门店授权后重试。"
        />
      ) : (
        <div className="table-surface">
          <Table<ScheduleRead>
            rowKey="id"
            size="middle"
            scroll={{ x: 1190 }}
            loading={
              storesQuery.isLoading ||
              teachersQuery.isLoading ||
              productsQuery.isLoading ||
              schedulesQuery.isLoading ||
              schedulesQuery.isFetching
            }
            columns={columns}
            dataSource={schedulesQuery.data?.items ?? []}
            pagination={{
              current: page,
              pageSize,
              total: schedulesQuery.data?.total ?? 0,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 节`,
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPageSize === pageSize ? nextPage : 1)
                setPageSize(nextPageSize)
              },
            }}
          />
        </div>
      )}

      {activeStoreId && selectedStore ? (
        <>
          <TeacherManagerModal
            open={isTeacherManagerOpen}
            storeId={activeStoreId}
            storeName={selectedStore.name}
            teachers={teachers}
            onClose={() => setIsTeacherManagerOpen(false)}
            onSaved={refreshTeachers}
          />
          <ScheduleFormModal
            open={isFormOpen}
            storeId={activeStoreId}
            selectedDate={selectedDate}
            teachers={teachers}
            products={products}
            schedule={editingSchedule}
            onClose={() => {
              setIsFormOpen(false)
              setEditingSchedule(null)
            }}
            onSaved={refreshSchedules}
          />
        </>
      ) : null}
    </section>
  )
}
