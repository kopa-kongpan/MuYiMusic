import type { VideoCourseRead } from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Empty,
  Input,
  Select,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import type { TableProps } from 'antd'
import { Pencil, Plus, RefreshCw, Search } from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'
import { VideoCourseFormModal } from './VideoCourseFormModal'

export function VideoCoursesPage() {
  const [storeId, setStoreId] = useState<string>()
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [categoryId, setCategoryId] = useState<string>()
  const [isActive, setIsActive] = useState<boolean>()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<VideoCourseRead | null>(null)

  const storesQuery = useQuery({
    queryKey: ['admin-stores-for-video-courses'],
    queryFn: () => apiClient.listAdminStores({ pageSize: 100 }),
  })
  const activeStoreId = storeId ?? storesQuery.data?.items[0]?.id
  const categoriesQuery = useQuery({
    queryKey: ['admin-video-course-categories', activeStoreId],
    queryFn: () => apiClient.listAdminCategories(activeStoreId!),
    enabled: Boolean(activeStoreId),
  })
  const coursesQuery = useQuery({
    queryKey: [
      'admin-video-courses',
      activeStoreId,
      keyword,
      categoryId,
      isActive,
      page,
      pageSize,
    ],
    queryFn: () =>
      apiClient.listAdminVideoCourses(activeStoreId!, {
        keyword,
        categoryId,
        isActive,
        page,
        pageSize,
      }),
    enabled: Boolean(activeStoreId),
  })
  const selectedStore =
    storesQuery.data?.items.find((store) => store.id === activeStoreId) ?? null
  const categories = categoriesQuery.data ?? []

  const columns: NonNullable<TableProps<VideoCourseRead>['columns']> = [
    {
      title: '视频课程',
      key: 'course',
      render: (_, course) => (
        <div className="product-price-cell">
          <strong>{course.name}</strong>
          <span>{course.summary || '暂无简介'}</span>
        </div>
      ),
    },
    { title: '分类', dataIndex: 'category_name', width: 160 },
    {
      title: '课时',
      width: 100,
      render: (_, course) =>
        `${course.lessons.filter((lesson) => lesson.is_active).length} / ${course.lessons.length}`,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 100,
      render: (active: boolean) => (
        <Tag color={active ? 'success' : 'default'}>
          {active ? '已启用' : '已停用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 80,
      render: (_, course) => (
        <Tooltip title="编辑视频课程">
          <Button
            type="text"
            icon={<Pencil size={17} aria-hidden="true" />}
            onClick={() => {
              setEditing(course)
              setFormOpen(true)
            }}
          />
        </Tooltip>
      ),
    },
  ]

  return (
    <section className="stores-page products-page">
      <header className="page-heading">
        <div>
          <h1>视频课程</h1>
          <span>
            {selectedStore
              ? `${selectedStore.name} · ${coursesQuery.data?.total ?? 0} 门视频课程`
              : '独立维护视频课程及每个课时的教学视频'}
          </span>
        </div>
        <Button
          type="primary"
          disabled={!selectedStore || !categories.length}
          icon={<Plus size={18} aria-hidden="true" />}
          onClick={() => {
            setEditing(null)
            setFormOpen(true)
          }}
        >
          创建视频课程
        </Button>
      </header>
      <div className="store-toolbar product-toolbar">
        <Select<string>
          className="content-store-select"
          value={activeStoreId}
          placeholder="选择门店"
          options={(storesQuery.data?.items ?? []).map((store) => ({
            value: store.id,
            label: store.name,
          }))}
          onChange={(value) => {
            setStoreId(value)
            setCategoryId(undefined)
            setPage(1)
          }}
        />
        <Input
          className="product-search"
          value={keywordInput}
          allowClear
          prefix={<Search size={16} aria-hidden="true" />}
          placeholder="搜索视频课程"
          onChange={(event) => setKeywordInput(event.target.value)}
          onPressEnter={() => {
            setKeyword(keywordInput.trim())
            setPage(1)
          }}
        />
        <Select<string>
          className="status-filter"
          allowClear
          value={categoryId}
          placeholder="全部分类"
          options={categories.map((category) => ({
            value: category.id,
            label: category.name,
          }))}
          onChange={(value) => {
            setCategoryId(value)
            setPage(1)
          }}
        />
        <Select<string>
          className="status-filter"
          allowClear
          value={isActive === undefined ? undefined : String(isActive)}
          placeholder="全部状态"
          options={[
            { value: 'true', label: '已启用' },
            { value: 'false', label: '已停用' },
          ]}
          onChange={(value) => {
            setIsActive(value === undefined ? undefined : value === 'true')
            setPage(1)
          }}
        />
        <Button
          icon={<Search size={17} aria-hidden="true" />}
          onClick={() => {
            setKeyword(keywordInput.trim())
            setPage(1)
          }}
        >
          搜索
        </Button>
        <Tooltip title="刷新列表">
          <Button
            icon={<RefreshCw size={17} aria-hidden="true" />}
            onClick={() => void coursesQuery.refetch()}
          />
        </Tooltip>
      </div>
      {coursesQuery.isError ? (
        <Alert type="error" showIcon message="视频课程加载失败" />
      ) : (
        <div className="table-surface">
          <Table<VideoCourseRead>
            rowKey="id"
            columns={columns}
            dataSource={coursesQuery.data?.items ?? []}
            loading={coursesQuery.isLoading || coursesQuery.isFetching}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="暂无视频课程"
                />
              ),
            }}
            pagination={{
              current: page,
              pageSize,
              total: coursesQuery.data?.total ?? 0,
              showSizeChanger: true,
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPageSize === pageSize ? nextPage : 1)
                setPageSize(nextPageSize)
              },
            }}
          />
        </div>
      )}
      {selectedStore ? (
        <VideoCourseFormModal
          open={formOpen}
          store={selectedStore}
          categories={categories}
          videoCourse={editing}
          onClose={() => setFormOpen(false)}
          onSaved={async () => {
            await coursesQuery.refetch()
          }}
        />
      ) : null}
    </section>
  )
}
