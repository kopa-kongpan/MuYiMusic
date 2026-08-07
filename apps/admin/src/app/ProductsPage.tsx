import type {
  ProductRead,
  ProductStatus,
  ProductType,
} from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  App as AntdApp,
  Button,
  Empty,
  Image,
  Input,
  Popconfirm,
  Select,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import type { TableProps } from 'antd'
import {
  Archive,
  CirclePause,
  Eye,
  ImageIcon,
  ListTree,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Send,
} from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'
import { CategoryManagerModal } from './CategoryManagerModal'
import { ProductFormModal } from './ProductFormModal'
import { ProductPreviewDrawer } from './ProductPreviewDrawer'

const statusLabels: Record<ProductStatus, string> = {
  draft: '草稿',
  published: '已发布',
  offline: '已下架',
  archived: '已归档',
}

const statusColors: Record<ProductStatus, string> = {
  draft: 'default',
  published: 'green',
  offline: 'orange',
  archived: 'red',
}

const statusActions: Record<
  ProductStatus,
  { target: ProductStatus; label: string; icon: typeof Send }[]
> = {
  draft: [{ target: 'published', label: '发布', icon: Send }],
  published: [{ target: 'offline', label: '下架', icon: CirclePause }],
  offline: [
    { target: 'published', label: '上架', icon: Send },
    { target: 'archived', label: '归档', icon: Archive },
  ],
  archived: [],
}

function formatMoney(priceCents: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(priceCents / 100)
}

function formatPriceRange(product: ProductRead): string {
  const activePrices = product.skus
    .filter((sku) => sku.is_active)
    .map((sku) => sku.price_cents)
  if (activePrices.length === 0) {
    return '无可售规格'
  }
  const minimum = Math.min(...activePrices)
  const maximum = Math.max(...activePrices)
  return minimum === maximum
    ? formatMoney(minimum)
    : `${formatMoney(minimum)} - ${formatMoney(maximum)}`
}

function formatSaleWindow(product: ProductRead): string {
  if (!product.sale_starts_at && !product.sale_ends_at) {
    return '长期销售'
  }
  const formatter = new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  const start = product.sale_starts_at
    ? formatter.format(new Date(product.sale_starts_at))
    : '立即'
  const end = product.sale_ends_at
    ? formatter.format(new Date(product.sale_ends_at))
    : '不限'
  return `${start} - ${end}`
}

export function ProductsPage() {
  const { message } = AntdApp.useApp()
  const [storeId, setStoreId] = useState<string>()
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [categoryId, setCategoryId] = useState<string>()
  const [status, setStatus] = useState<ProductStatus>()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editingProduct, setEditingProduct] = useState<ProductRead | null>(null)
  const [previewProduct, setPreviewProduct] = useState<ProductRead | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [isCategoryOpen, setIsCategoryOpen] = useState(false)
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const storesQuery = useQuery({
    queryKey: ['admin-stores-for-products'],
    queryFn: () => apiClient.listAdminStores({ pageSize: 100 }),
  })
  const activeStoreId = storeId ?? storesQuery.data?.items[0]?.id
  const categoriesQuery = useQuery({
    queryKey: ['admin-product-categories', activeStoreId],
    queryFn: () => apiClient.listAdminCategories(activeStoreId!),
    enabled: Boolean(activeStoreId),
  })
  const productsQuery = useQuery({
    queryKey: [
      'admin-products',
      activeStoreId,
      keyword,
      categoryId,
      status,
      page,
      pageSize,
    ],
    queryFn: () =>
      apiClient.listAdminProducts(activeStoreId!, {
        keyword,
        categoryId,
        status,
        page,
        pageSize,
      }),
    enabled: Boolean(activeStoreId),
  })

  const selectedStore =
    storesQuery.data?.items.find((store) => store.id === activeStoreId) ?? null
  const categories = categoriesQuery.data ?? []

  function search() {
    setPage(1)
    setKeyword(keywordInput.trim())
  }

  async function changeStatus(product: ProductRead, targetStatus: ProductStatus) {
    if (!activeStoreId) {
      return
    }
    setUpdatingId(product.id)
    try {
      await apiClient.changeProductStatus(activeStoreId, product.id, {
        status: targetStatus,
      })
      await productsQuery.refetch()
      void message.success(
        targetStatus === 'published'
          ? '商品已发布'
          : targetStatus === 'offline'
            ? '商品已下架'
            : '商品已归档',
      )
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '状态变更失败')
    } finally {
      setUpdatingId(null)
    }
  }

  const columns: NonNullable<TableProps<ProductRead>['columns']> = [
    {
      title: '课程商品',
      key: 'product',
      width: 320,
      render: (_, product) => (
        <div className="product-cell">
          <div className="product-thumbnail">
            {product.cover_url ? (
              <Image
                src={product.cover_url}
                alt=""
                width={80}
                height={56}
                preview={false}
              />
            ) : (
              <ImageIcon size={22} aria-hidden="true" />
            )}
          </div>
          <div>
            <strong>{product.name}</strong>
            <span>{product.category_name} · 顺序 {product.sort_order}</span>
          </div>
        </div>
      ),
    },
    {
      title: '售价',
      key: 'price',
      width: 190,
      render: (_, product) => (
        <div className="product-price-cell">
          <strong>{formatPriceRange(product)}</strong>
          <span>{product.skus.filter((sku) => sku.is_active).length} 个可售规格</span>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'product_type',
      width: 100,
      render: (productType: ProductType) => (
        <Tag color={productType === 'video' ? 'blue' : 'default'}>
          {productType === 'video' ? '视频课程' : '线下课时课'}
        </Tag>
      ),
    },
    {
      title: '销售时间',
      key: 'sale-window',
      width: 210,
      render: (_, product) => (
        <span className="window-text">{formatSaleWindow(product)}</span>
      ),
    },
    {
      title: '销量',
      dataIndex: 'sales_count',
      width: 90,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (productStatus: ProductStatus) => (
        <Tag color={statusColors[productStatus]}>{statusLabels[productStatus]}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 150,
      render: (_, product) => {
        const actions = statusActions[product.status]
        return (
          <div className="table-actions">
            <Tooltip title="预览商品">
              <Button
                type="text"
                icon={<Eye size={17} aria-hidden="true" />}
                aria-label={`预览${product.name}`}
                onClick={() => setPreviewProduct(product)}
              />
            </Tooltip>
            <Tooltip title={product.status === 'archived' ? '已归档商品不可编辑' : '编辑商品'}>
              <Button
                type="text"
                disabled={product.status === 'archived'}
                icon={<Pencil size={17} aria-hidden="true" />}
                aria-label={`编辑${product.name}`}
                onClick={() => {
                  setEditingProduct(product)
                  setIsFormOpen(true)
                }}
              />
            </Tooltip>
            {actions.map(({ target, label, icon: ActionIcon }) => (
              <Popconfirm
                key={target}
                title={`确认${label}“${product.name}”？`}
                description={target === 'archived' ? '归档后不能恢复或修改。' : undefined}
                okText="确认"
                cancelText="取消"
                onConfirm={() => void changeStatus(product, target)}
              >
                <Tooltip title={label}>
                  <Button
                    type="text"
                    loading={updatingId === product.id}
                    danger={target !== 'published'}
                    icon={<ActionIcon size={17} aria-hidden="true" />}
                    aria-label={`${label}${product.name}`}
                  />
                </Tooltip>
              </Popconfirm>
            ))}
          </div>
        )
      },
    },
  ]

  const hasError =
    storesQuery.isError || categoriesQuery.isError || productsQuery.isError

  return (
    <section className="stores-page products-page">
      <header className="page-heading">
        <div>
          <h1>课程商品</h1>
          <span>
            {selectedStore
              ? `${selectedStore.name} · ${productsQuery.data?.total ?? 0} 个商品`
              : '按门店维护课程分类与商品'}
          </span>
        </div>
        <div className="page-heading-actions">
          <Button
            disabled={!selectedStore}
            icon={<ListTree size={18} aria-hidden="true" />}
            onClick={() => setIsCategoryOpen(true)}
          >
            分类管理
          </Button>
          <Button
            type="primary"
            disabled={!selectedStore || categories.length === 0}
            icon={<Plus size={18} aria-hidden="true" />}
            onClick={() => {
              setEditingProduct(null)
              setIsFormOpen(true)
            }}
          >
            创建商品
          </Button>
        </div>
      </header>

      <div className="store-toolbar product-toolbar">
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
            setCategoryId(undefined)
            setPage(1)
          }}
        />
        <Input
          className="product-search"
          value={keywordInput}
          allowClear
          prefix={<Search size={16} aria-hidden="true" />}
          placeholder="搜索商品名称或摘要"
          onChange={(event) => setKeywordInput(event.target.value)}
          onPressEnter={search}
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
        <Select<ProductStatus>
          className="status-filter"
          allowClear
          value={status}
          placeholder="全部状态"
          options={Object.entries(statusLabels).map(([value, label]) => ({
            value: value as ProductStatus,
            label,
          }))}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
        <Button icon={<Search size={17} aria-hidden="true" />} onClick={search}>
          搜索
        </Button>
        <Tooltip title="刷新列表">
          <Button
            disabled={!activeStoreId}
            icon={<RefreshCw size={17} aria-hidden="true" />}
            aria-label="刷新商品列表"
            onClick={() => void productsQuery.refetch()}
          />
        </Tooltip>
      </div>

      {hasError ? (
        <Alert
          className="page-alert"
          type="error"
          showIcon
          message="课程商品加载失败"
          description="请检查当前账号的门店权限后重试"
        />
      ) : (
        <div className="table-surface">
          <Table<ProductRead>
            rowKey="id"
            size="middle"
            loading={
              storesQuery.isLoading ||
              categoriesQuery.isLoading ||
              productsQuery.isLoading ||
              productsQuery.isFetching
            }
            columns={columns}
            dataSource={productsQuery.data?.items ?? []}
            scroll={{ x: 1160 }}
            pagination={{
              current: page,
              pageSize,
              total: productsQuery.data?.total ?? 0,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 个商品`,
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPageSize === pageSize ? nextPage : 1)
                setPageSize(nextPageSize)
              },
            }}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={
                    activeStoreId
                      ? categories.length
                        ? '该门店暂无课程商品'
                        : '请先创建课程分类'
                      : '请先选择门店'
                  }
                />
              ),
            }}
          />
        </div>
      )}

      {selectedStore ? (
        <>
          <CategoryManagerModal
            open={isCategoryOpen}
            storeId={selectedStore.id}
            storeName={selectedStore.name}
            categories={categories}
            onClose={() => setIsCategoryOpen(false)}
            onSaved={async () => {
              await categoriesQuery.refetch()
              await productsQuery.refetch()
            }}
          />
          <ProductFormModal
            open={isFormOpen}
            store={selectedStore}
            categories={categories}
            product={editingProduct}
            onClose={() => setIsFormOpen(false)}
            onSaved={async () => {
              await productsQuery.refetch()
            }}
          />
        </>
      ) : null}

      <ProductPreviewDrawer
        open={Boolean(previewProduct)}
        store={selectedStore}
        product={previewProduct}
        onClose={() => setPreviewProduct(null)}
      />
    </section>
  )
}
