import type {
  CourseEntitlementRead,
  EntitlementStatus,
  OrderRead,
  OrderStatus,
  ProductRead,
  UserAdminRead,
  UserStatus,
} from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  App as AntdApp,
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import type { TableProps } from 'antd'
import {
  BookPlus,
  Eye,
  GraduationCap,
  Pencil,
  ReceiptText,
  RefreshCw,
  Search,
} from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'
import { getAdminSession } from './session'

interface CourseBindingFormValues {
  productId: string
  skuId: string
}

interface LessonAdjustmentFormValues {
  remainingLessons: number
  reason: string
}

const userStatusLabels: Record<UserStatus, string> = {
  active: '正常',
  disabled: '已停用',
}

const orderStatusLabels: Record<OrderStatus, string> = {
  pending: '待确认',
  confirmed: '已确认',
  cancelled: '已取消',
}

const entitlementStatusLabels: Record<EntitlementStatus, string> = {
  active: '生效中',
  exhausted: '已用完',
  expired: '已过期',
}

const providerLabels = {
  weapp: '微信',
  tt: '抖音',
  h5: 'H5',
} as const

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatDate(value: string | null): string {
  if (!value) {
    return '长期有效'
  }
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(
    new Date(value),
  )
}

function formatMoney(priceCents: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(priceCents / 100)
}

export function UsersPage() {
  const { message } = AntdApp.useApp()
  const [courseBindingForm] = Form.useForm<CourseBindingFormValues>()
  const [lessonAdjustmentForm] = Form.useForm<LessonAdjustmentFormValues>()
  const [storeId, setStoreId] = useState<string>()
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [selectedUser, setSelectedUser] = useState<UserAdminRead | null>(null)
  const [orderPage, setOrderPage] = useState(1)
  const [entitlementPage, setEntitlementPage] = useState(1)
  const [bindingUser, setBindingUser] = useState<UserAdminRead | null>(null)
  const [isBindingCourse, setIsBindingCourse] = useState(false)
  const [adjustingEntitlement, setAdjustingEntitlement] =
    useState<CourseEntitlementRead | null>(null)
  const [isAdjustingLessons, setIsAdjustingLessons] = useState(false)
  const selectedProductId = Form.useWatch('productId', courseBindingForm)
  const session = getAdminSession()
  const canBindCourse =
    session?.admin.permissions.includes('products:manage') ?? false
  const canAdjustLessons =
    session?.admin.permissions.includes('consumptions:manage') ?? false

  const storesQuery = useQuery({
    queryKey: ['admin-stores-for-users'],
    queryFn: () => apiClient.listAdminStores({ pageSize: 100 }),
  })
  const activeStoreId = storeId ?? storesQuery.data?.items[0]?.id
  const selectedStore =
    storesQuery.data?.items.find((store) => store.id === activeStoreId) ?? null

  const usersQuery = useQuery({
    queryKey: ['admin-users', activeStoreId, keyword, page, pageSize],
    queryFn: () =>
      apiClient.listAdminUsers(activeStoreId!, {
        keyword,
        page,
        pageSize,
      }),
    enabled: Boolean(activeStoreId),
  })
  const ordersQuery = useQuery({
    queryKey: [
      'admin-user-orders',
      activeStoreId,
      selectedUser?.id,
      orderPage,
    ],
    queryFn: () =>
      apiClient.listAdminUserOrders(activeStoreId!, selectedUser!.id, {
        page: orderPage,
        pageSize: 20,
      }),
    enabled: Boolean(activeStoreId && selectedUser),
  })
  const entitlementsQuery = useQuery({
    queryKey: [
      'admin-user-entitlements',
      activeStoreId,
      selectedUser?.id,
      entitlementPage,
    ],
    queryFn: () =>
      apiClient.listAdminUserCourseEntitlements(
        activeStoreId!,
        selectedUser!.id,
        { page: entitlementPage, pageSize: 20 },
      ),
    enabled: Boolean(activeStoreId && selectedUser),
  })
  const productsQuery = useQuery({
    queryKey: ['admin-products-for-user-binding', activeStoreId],
    queryFn: () =>
      apiClient.listAdminProducts(activeStoreId!, {
        status: 'published',
        pageSize: 100,
      }),
    enabled: Boolean(activeStoreId && bindingUser && canBindCourse),
  })
  const publishedProducts = productsQuery.data?.items ?? []
  const selectedProduct = publishedProducts.find(
    (product) => product.id === selectedProductId,
  )

  function search() {
    setPage(1)
    setKeyword(keywordInput.trim())
  }

  function inspectUser(user: UserAdminRead) {
    setOrderPage(1)
    setEntitlementPage(1)
    setSelectedUser(user)
  }

  function openCourseBinding(user: UserAdminRead) {
    courseBindingForm.resetFields()
    setBindingUser(user)
  }

  function closeCourseBinding() {
    if (isBindingCourse) {
      return
    }
    setBindingUser(null)
    courseBindingForm.resetFields()
  }

  async function bindCourse(values: CourseBindingFormValues) {
    if (!activeStoreId || !bindingUser) {
      return
    }
    setIsBindingCourse(true)
    try {
      await apiClient.grantAdminUserEntitlement(activeStoreId, bindingUser.id, {
        product_id: values.productId,
        sku_id: values.skuId,
        quantity: 1,
        idempotency_key: `admin-grant-${crypto.randomUUID()}`,
      })
      await usersQuery.refetch()
      if (selectedUser?.id === bindingUser.id) {
        await Promise.all([ordersQuery.refetch(), entitlementsQuery.refetch()])
      }
      void message.success(`已为 ${bindingUser.nickname} 绑定课程`)
      setBindingUser(null)
      courseBindingForm.resetFields()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '课程绑定失败')
    } finally {
      setIsBindingCourse(false)
    }
  }

  function openLessonAdjustment(entitlement: CourseEntitlementRead) {
    lessonAdjustmentForm.setFieldsValue({
      remainingLessons: entitlement.remaining_lessons,
      reason: '',
    })
    setAdjustingEntitlement(entitlement)
  }

  function closeLessonAdjustment() {
    if (isAdjustingLessons) {
      return
    }
    setAdjustingEntitlement(null)
    lessonAdjustmentForm.resetFields()
  }

  async function adjustLessons(values: LessonAdjustmentFormValues) {
    if (!activeStoreId || !selectedUser || !adjustingEntitlement) {
      return
    }
    setIsAdjustingLessons(true)
    try {
      await apiClient.updateAdminUserEntitlementLessons(
        activeStoreId,
        selectedUser.id,
        adjustingEntitlement.id,
        {
          remaining_lessons: values.remainingLessons,
          reason: values.reason.trim(),
        },
      )
      await entitlementsQuery.refetch()
      void message.success('剩余课时已更新')
      setAdjustingEntitlement(null)
      lessonAdjustmentForm.resetFields()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '课时调整失败')
    } finally {
      setIsAdjustingLessons(false)
    }
  }

  const userColumns: NonNullable<TableProps<UserAdminRead>['columns']> = [
    {
      title: '用户',
      key: 'user',
      width: 260,
      render: (_, user) => (
        <div className="user-cell">
          <span className="user-avatar" aria-hidden="true">
            {user.nickname.slice(0, 1)}
          </span>
          <div>
            <strong>{user.nickname}</strong>
            <span>{user.phone_masked ?? '未绑定手机号'}</span>
          </div>
        </div>
      ),
    },
    {
      title: '平台账号',
      dataIndex: 'provider_names',
      width: 160,
      render: (providers: UserAdminRead['provider_names']) =>
        providers.length ? (
          providers.map((provider) => (
            <Tag key={provider}>{providerLabels[provider]}</Tag>
          ))
        ) : (
          <span className="muted-text">暂无</span>
        ),
    },
    {
      title: '业务数据',
      key: 'business',
      width: 220,
      render: (_, user) => (
        <div className="user-counts">
          <span>
            <ReceiptText size={15} aria-hidden="true" />
            {user.order_count} 笔订单
          </span>
          <span>
            <GraduationCap size={15} aria-hidden="true" />
            {user.entitlement_count} 项课程
          </span>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: UserStatus) => (
        <Tag color={status === 'active' ? 'success' : 'default'}>
          {userStatusLabels[status]}
        </Tag>
      ),
    },
    {
      title: '首次登录',
      dataIndex: 'created_at',
      width: 170,
      render: (value: string) => formatTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: canBindCourse ? 112 : 80,
      render: (_, user) => (
        <div className="table-actions">
          <Tooltip title="查看订单与课程权益">
            <Button
              type="text"
              icon={<Eye size={17} aria-hidden="true" />}
              aria-label={`查看${user.nickname}的订单与课程权益`}
              onClick={() => inspectUser(user)}
            />
          </Tooltip>
          {canBindCourse ? (
            <Tooltip title="绑定课程">
              <Button
                type="text"
                icon={<BookPlus size={17} aria-hidden="true" />}
                aria-label={`为${user.nickname}绑定课程`}
                onClick={() => openCourseBinding(user)}
              />
            </Tooltip>
          ) : null}
        </div>
      ),
    },
  ]

  const orderColumns: NonNullable<TableProps<OrderRead>['columns']> = [
    {
      title: '订单',
      key: 'order',
      width: 190,
      render: (_, order) => (
        <div className="order-summary-cell">
          <strong>{order.order_no}</strong>
          <span>{formatTime(order.created_at)}</span>
        </div>
      ),
    },
    {
      title: '课程快照',
      key: 'items',
      width: 330,
      render: (_, order) => (
        <div className="order-items-cell">
          {order.items.map((item) => (
            <span key={item.id}>
              {item.product_name} · {item.sku_name} × {item.quantity}
            </span>
          ))}
        </div>
      ),
    },
    {
      title: '金额',
      dataIndex: 'total_amount_cents',
      align: 'right',
      width: 120,
      render: (value: number) => formatMoney(value),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: OrderStatus) => (
        <Tag color={status === 'confirmed' ? 'success' : undefined}>
          {orderStatusLabels[status]}
        </Tag>
      ),
    },
  ]

  const entitlementColumns: NonNullable<
    TableProps<CourseEntitlementRead>['columns']
  > = [
    {
      title: '课程',
      dataIndex: 'course_name',
      width: 250,
    },
    {
      title: '课时',
      key: 'lessons',
      width: 150,
      render: (_, entitlement) => (
        <div className="order-summary-cell">
          <strong>
            {entitlement.remaining_lessons} / {entitlement.total_lessons}
          </strong>
          <span>锁定 {entitlement.reserved_lessons} 课时</span>
        </div>
      ),
    },
    {
      title: '有效期',
      key: 'validity',
      width: 230,
      render: (_, entitlement) =>
        `${formatDate(entitlement.valid_from)} 至 ${formatDate(entitlement.expires_at)}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: EntitlementStatus) => (
        <Tag color={status === 'active' ? 'success' : undefined}>
          {entitlementStatusLabels[status]}
        </Tag>
      ),
    },
    ...(canAdjustLessons
      ? [
          {
            title: '操作',
            key: 'actions',
            fixed: 'right' as const,
            width: 72,
            render: (_: unknown, entitlement: CourseEntitlementRead) =>
              entitlement.product_type === 'course' ? (
                <Tooltip title="调整课时">
                  <Button
                    type="text"
                    icon={<Pencil size={16} aria-hidden="true" />}
                    aria-label={`调整${entitlement.course_name}课时`}
                    onClick={() => openLessonAdjustment(entitlement)}
                  />
                </Tooltip>
              ) : null,
          },
        ]
      : []),
  ]

  const loadError = storesQuery.error ?? usersQuery.error

  return (
    <section className="stores-page users-page">
      <header className="page-heading">
        <div>
          <h1>用户与权益</h1>
          <span>
            {selectedStore
              ? `${selectedStore.name} · ${usersQuery.data?.total ?? 0} 位业务用户`
              : '按门店查询用户、订单与课程权益'}
          </span>
        </div>
      </header>

      <div className="store-toolbar user-toolbar">
        <Select<string>
          className="content-store-select"
          value={activeStoreId}
          loading={storesQuery.isLoading}
          showSearch
          optionFilterProp="label"
          placeholder="选择门店"
          options={(storesQuery.data?.items ?? []).map((store) => ({
            label: store.name,
            value: store.id,
          }))}
          onChange={(value) => {
            setStoreId(value)
            setPage(1)
            setSelectedUser(null)
          }}
        />
        <Input
          className="store-search"
          value={keywordInput}
          allowClear
          placeholder="搜索昵称或手机号"
          prefix={<Search size={16} aria-hidden="true" />}
          onChange={(event) => setKeywordInput(event.target.value)}
          onPressEnter={search}
        />
        <Button icon={<Search size={17} aria-hidden="true" />} onClick={search}>
          查询
        </Button>
        <Tooltip title="刷新列表">
          <Button
            disabled={!activeStoreId}
            icon={<RefreshCw size={17} aria-hidden="true" />}
            aria-label="刷新用户列表"
            onClick={() => void usersQuery.refetch()}
          />
        </Tooltip>
      </div>

      {loadError ? (
        <Alert
          className="page-alert"
          type="error"
          showIcon
          message="用户与权益加载失败"
          description={loadError instanceof Error ? loadError.message : '请稍后重试'}
        />
      ) : (
        <div className="table-surface">
          <Table<UserAdminRead>
            rowKey="id"
            size="middle"
            loading={
              storesQuery.isLoading || usersQuery.isLoading || usersQuery.isFetching
            }
            columns={userColumns}
            dataSource={usersQuery.data?.items ?? []}
            scroll={{ x: 1100 }}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={activeStoreId ? '该门店暂无业务用户' : '请先选择门店'}
                />
              ),
            }}
            pagination={{
              current: page,
              pageSize,
              total: usersQuery.data?.total ?? 0,
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

      <Drawer
        open={Boolean(selectedUser)}
        width={920}
        title={selectedUser ? `${selectedUser.nickname} · 业务详情` : '业务详情'}
        onClose={() => setSelectedUser(null)}
      >
        <div className="user-detail-section">
          <div className="user-detail-heading">
            <div>
              <ReceiptText size={18} aria-hidden="true" />
              <strong>门店订单</strong>
            </div>
            <span>价格与课程名称均为下单时快照</span>
          </div>
          <Table<OrderRead>
            rowKey="id"
            size="small"
            loading={ordersQuery.isLoading || ordersQuery.isFetching}
            columns={orderColumns}
            dataSource={ordersQuery.data?.items ?? []}
            scroll={{ x: 740 }}
            locale={{
              emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无订单" />,
            }}
            pagination={{
              current: orderPage,
              pageSize: 20,
              total: ordersQuery.data?.total ?? 0,
              showSizeChanger: false,
              onChange: setOrderPage,
            }}
          />
        </div>

        <div className="user-detail-section">
          <div className="user-detail-heading">
            <div>
              <GraduationCap size={18} aria-hidden="true" />
              <strong>课程权益</strong>
            </div>
            <span>课程绑定后自动生成已确认订单和对应权益</span>
          </div>
          <Table<CourseEntitlementRead>
            rowKey="id"
            size="small"
            loading={entitlementsQuery.isLoading || entitlementsQuery.isFetching}
            columns={entitlementColumns}
            dataSource={entitlementsQuery.data?.items ?? []}
            scroll={{ x: canAdjustLessons ? 830 : 750 }}
            locale={{
              emptyText: (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无课程权益" />
              ),
            }}
            pagination={{
              current: entitlementPage,
              pageSize: 20,
              total: entitlementsQuery.data?.total ?? 0,
              showSizeChanger: false,
              onChange: setEntitlementPage,
            }}
          />
        </div>
      </Drawer>

      <Modal
        title={bindingUser ? `为 ${bindingUser.nickname} 绑定课程` : '绑定课程'}
        open={Boolean(bindingUser)}
        okText="确认绑定"
        cancelText="取消"
        confirmLoading={isBindingCourse}
        destroyOnHidden
        onOk={() => courseBindingForm.submit()}
        onCancel={closeCourseBinding}
      >
        {productsQuery.isError ? (
          <Alert
            className="page-alert"
            type="error"
            showIcon
            message="课程加载失败"
            description={
              productsQuery.error instanceof Error
                ? productsQuery.error.message
                : '请稍后重试'
            }
          />
        ) : null}
        <Form<CourseBindingFormValues>
          form={courseBindingForm}
          layout="vertical"
          requiredMark={false}
          onFinish={(values) => void bindCourse(values)}
        >
          <Form.Item
            name="productId"
            label="课程"
            rules={[{ required: true, message: '请选择课程' }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              loading={productsQuery.isLoading}
              placeholder="选择已发布课程"
              options={publishedProducts.map((product: ProductRead) => ({
                label: product.name,
                value: product.id,
              }))}
              notFoundContent={productsQuery.isLoading ? null : '暂无已发布课程'}
              onChange={() => courseBindingForm.setFieldValue('skuId', undefined)}
            />
          </Form.Item>
          <Form.Item
            name="skuId"
            label="课程规格"
            rules={[{ required: true, message: '请选择课程规格' }]}
          >
            <Select
              disabled={!selectedProduct}
              placeholder="选择有效规格"
              options={(selectedProduct?.skus ?? [])
                .filter((sku) => sku.is_active)
                .map((sku) => ({
                  label: `${sku.name} · ${formatMoney(sku.price_cents)} · ${
                    sku.lesson_count > 0 ? `${sku.lesson_count} 课时` : '视频课程'
                  }`,
                  value: sku.id,
                }))}
              notFoundContent="该课程暂无有效规格"
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={
          adjustingEntitlement
            ? `调整 ${adjustingEntitlement.course_name} 课时`
            : '调整课时'
        }
        open={Boolean(adjustingEntitlement)}
        okText="确认调整"
        cancelText="取消"
        confirmLoading={isAdjustingLessons}
        destroyOnHidden
        onOk={() => lessonAdjustmentForm.submit()}
        onCancel={closeLessonAdjustment}
      >
        <Form<LessonAdjustmentFormValues>
          form={lessonAdjustmentForm}
          layout="vertical"
          requiredMark={false}
          onFinish={(values) => void adjustLessons(values)}
        >
          <Form.Item
            name="remainingLessons"
            label="剩余课时"
            rules={[
              { required: true, message: '请输入剩余课时' },
              {
                type: 'number',
                min: adjustingEntitlement?.reserved_lessons ?? 0,
                max: 9999,
                message: `不能少于锁定的 ${
                  adjustingEntitlement?.reserved_lessons ?? 0
                } 课时`,
              },
            ]}
          >
            <InputNumber
              min={adjustingEntitlement?.reserved_lessons ?? 0}
              max={9999}
              precision={0}
              addonAfter="课时"
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item
            name="reason"
            label="调整原因"
            rules={[
              { required: true, whitespace: true, message: '请输入调整原因' },
              { max: 500, message: '调整原因不能超过 500 字' },
            ]}
          >
            <Input.TextArea rows={3} maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}
