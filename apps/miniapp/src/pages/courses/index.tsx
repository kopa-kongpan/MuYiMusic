import type {
  CategoryPublicRead,
  ProductPublicListItem,
  ProductSort,
} from '@muyimusic/api-client'
import { Button, Image, Input, Picker, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh, useReachBottom } from '@tarojs/taro'
import { useState } from 'react'

import {
  listCourseCategories,
  listCourseProducts,
  validateCoursePurchase,
} from '../../services/courses'
import { addCartItem, cartQuantity } from '../../store/cart'
import { readCurrentStore } from '../../store/current-store'
import './index.scss'

const sortOptions: Array<{ label: string; value: ProductSort }> = [
  { label: '综合排序', value: 'comprehensive' },
  { label: '销量优先', value: 'sales' },
  { label: '最新上架', value: 'newest' },
  { label: '价格从低到高', value: 'price_asc' },
  { label: '价格从高到低', value: 'price_desc' },
]

function formatMoney(priceCents: number): string {
  return `¥${(priceCents / 100).toFixed(2)}`
}

export default function CoursesPage() {
  const [categories, setCategories] = useState<CategoryPublicRead[]>([])
  const [products, setProducts] = useState<ProductPublicListItem[]>([])
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [categoryId, setCategoryId] = useState<string>()
  const [sort, setSort] = useState<ProductSort>('comprehensive')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [failedImages, setFailedImages] = useState<Set<string>>(new Set())
  const [cartCount, setCartCount] = useState(0)

  async function loadProducts(options?: {
    nextKeyword?: string
    nextCategoryId?: string
    nextSort?: ProductSort
    nextPage?: number
    append?: boolean
  }) {
    const store = readCurrentStore()
    if (!store) {
      setErrorMessage('请先选择门店')
      setIsLoading(false)
      return
    }
    const requestedPage = options?.nextPage ?? 1
    if (options?.append) {
      setIsLoadingMore(true)
    } else {
      setIsLoading(true)
    }
    setErrorMessage(null)
    try {
      const response = await listCourseProducts(store.id, {
        keyword: options?.nextKeyword ?? keyword,
        categoryId:
          options && 'nextCategoryId' in options
            ? options.nextCategoryId
            : categoryId,
        sort: options?.nextSort ?? sort,
        page: requestedPage,
        pageSize: 20,
      })
      setProducts((current) =>
        options?.append ? [...current, ...response.items] : response.items,
      )
      setTotal(response.total)
      setPage(requestedPage)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '课程加载失败')
    } finally {
      setIsLoading(false)
      setIsLoadingMore(false)
    }
  }

  async function loadCourses() {
    const store = readCurrentStore()
    if (!store) {
      setCategories([])
      setProducts([])
      setCartCount(0)
      setErrorMessage('请先选择门店')
      setIsLoading(false)
      return
    }
    setCartCount(cartQuantity(store.id))
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const [nextCategories, response] = await Promise.all([
        listCourseCategories(store.id),
        listCourseProducts(store.id, {
          keyword,
          categoryId,
          sort,
          page: 1,
          pageSize: 20,
        }),
      ])
      setCategories(nextCategories)
      setProducts(response.items)
      setTotal(response.total)
      setPage(1)
      setFailedImages(new Set())
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '课程加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  useDidShow(() => {
    void loadCourses()
  })

  usePullDownRefresh(() => {
    void loadCourses().finally(() => Taro.stopPullDownRefresh())
  })

  useReachBottom(() => {
    if (!isLoading && !isLoadingMore && products.length < total) {
      void loadProducts({ nextPage: page + 1, append: true })
    }
  })

  function search() {
    const nextKeyword = keywordInput.trim()
    setKeyword(nextKeyword)
    void loadProducts({ nextKeyword })
  }

  async function addProductToCart(product: ProductPublicListItem) {
    const currentStore = readCurrentStore()
    if (!currentStore) {
      await Taro.showToast({ title: '请先选择门店', icon: 'none' })
      return
    }
    try {
      const validation = await validateCoursePurchase(
        currentStore.id,
        product.id,
        { sku_id: product.default_sku_id, quantity: 1 },
      )
      const items = addCartItem(currentStore.id, {
        productId: product.id,
        productName: validation.product_name,
        skuId: validation.sku_id,
        skuName: validation.sku_name,
        quantity: 1,
        unitPriceCents: validation.unit_price_cents,
        coverUrl: product.cover_url,
        validatedAt: validation.validated_at,
      })
      setCartCount(items.reduce((total, item) => total + item.quantity, 0))
      await Taro.showToast({ title: '已加入购物车', icon: 'success' })
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '加入购物车失败',
        icon: 'none',
      })
    }
  }

  const store = readCurrentStore()
  const selectedSortIndex = Math.max(
    0,
    sortOptions.findIndex((option) => option.value === sort),
  )

  return (
    <View className="courses-page">
      <View className="courses-header">
        <View>
          <Text className="courses-title">课程</Text>
          <Text className="courses-store">{store?.name ?? '尚未选择门店'}</Text>
        </View>
        <Button
          className="cart-entry"
          size="mini"
          onClick={() => void Taro.navigateTo({ url: '/pages/cart/index' })}
        >
          购物车{cartCount ? ` ${cartCount}` : ''}
        </Button>
      </View>

      <View className="course-search-row">
        <Input
          className="course-search-input"
          value={keywordInput}
          confirmType="search"
          placeholder="搜索课程"
          onInput={(event) => setKeywordInput(event.detail.value)}
          onConfirm={search}
        />
        <Button className="course-search-button" size="mini" onClick={search}>
          搜索
        </Button>
      </View>

      <ScrollView className="category-scroll" scrollX enhanced showScrollbar={false}>
        <View className="category-tabs">
          <View
            className={`category-tab${categoryId ? '' : ' category-tab--active'}`}
            onClick={() => {
              setCategoryId(undefined)
              void loadProducts({ nextCategoryId: undefined })
            }}
          >
            全部
          </View>
          {categories.map((category) => (
            <View
              className={`category-tab${category.id === categoryId ? ' category-tab--active' : ''}`}
              key={category.id}
              onClick={() => {
                setCategoryId(category.id)
                void loadProducts({ nextCategoryId: category.id })
              }}
            >
              {category.name}
            </View>
          ))}
        </View>
      </ScrollView>

      <View className="course-result-bar">
        <Text>{total} 门课程</Text>
        <Picker
          mode="selector"
          range={sortOptions.map((option) => option.label)}
          value={selectedSortIndex}
          onChange={(event) => {
            const next = sortOptions[Number(event.detail.value)]
            if (next) {
              setSort(next.value)
              void loadProducts({ nextSort: next.value })
            }
          }}
        >
          <View className="sort-picker">{sortOptions[selectedSortIndex]?.label}</View>
        </Picker>
      </View>

      {isLoading ? (
        <View className="course-list">
          {[0, 1, 2].map((item) => (
            <View className="course-skeleton" key={item}>
              <View />
              <View><View /><View /><View /></View>
            </View>
          ))}
        </View>
      ) : null}

      {!isLoading && errorMessage ? (
        <View className="course-state course-state--error">
          <Text className="course-state-title">暂时无法加载课程</Text>
          <Text className="course-state-copy">{errorMessage}</Text>
          <Button className="course-retry-button" size="mini" onClick={() => void loadCourses()}>
            重试
          </Button>
        </View>
      ) : null}

      {!isLoading && !errorMessage && products.length === 0 ? (
        <View className="course-state">
          <Text className="course-state-title">暂无符合条件的课程</Text>
          <Text className="course-state-copy">可更换分类或搜索词后查看</Text>
        </View>
      ) : null}

      {!isLoading && !errorMessage && products.length ? (
        <View className="course-list">
          {products.map((product) => (
            <View
              className="course-item"
              key={product.id}
              hoverClass="course-item--pressed"
              onClick={() =>
                void Taro.navigateTo({
                  url: `/pages/course-detail/index?id=${product.id}`,
                })
              }
            >
              {product.cover_url && !failedImages.has(product.id) ? (
                <Image
                  className="course-cover"
                  src={product.cover_url}
                  mode="aspectFill"
                  onError={() =>
                    setFailedImages((current) => new Set(current).add(product.id))
                  }
                />
              ) : (
                <View className="course-cover course-cover--empty">课程</View>
              )}
              <View className="course-item-body">
                <Text className="course-item-category">{product.category_name}</Text>
                <Text className="course-item-name">{product.name}</Text>
                <Text className="course-item-summary">
                  {product.lesson_count} 课时 · {product.validity_days} 天有效
                </Text>
                <View className="course-item-meta">
                  <View>
                    <Text className="course-item-price">
                      {formatMoney(product.min_price_cents)}
                      {product.max_price_cents !== product.min_price_cents ? ' 起' : ''}
                    </Text>
                    <Text>已售 {product.sales_count}</Text>
                  </View>
                  <Button
                    className="course-cart-button"
                    size="mini"
                    onClick={(event) => {
                      event.stopPropagation()
                      void addProductToCart(product)
                    }}
                  >
                    加入购物车
                  </Button>
                </View>
              </View>
            </View>
          ))}
          {isLoadingMore ? <Text className="course-loading-more">加载中</Text> : null}
        </View>
      ) : null}
    </View>
  )
}
