import type { ProductPublicRead } from '@muyimusic/api-client'
import { Button, Image, Swiper, SwiperItem, Text, View } from '@tarojs/components'
import Taro, { useLoad, useRouter, useShareAppMessage } from '@tarojs/taro'
import { useState } from 'react'

import { getCourseProduct, validateCoursePurchase } from '../../services/courses'
import { listPublicStores } from '../../services/stores'
import { addCartItem, cartQuantity } from '../../store/cart'
import { readCurrentStore, saveCurrentStore } from '../../store/current-store'
import './index.scss'

function formatMoney(priceCents: number): string {
  return `¥${(priceCents / 100).toFixed(2)}`
}

function formatDuration(seconds: number | null): string {
  if (!seconds) {
    return '时长未知'
  }
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes}分${rest}秒` : `${minutes}分钟`
}

export default function CourseDetailPage() {
  const router = useRouter()
  const [product, setProduct] = useState<ProductPublicRead | null>(null)
  const [selectedSkuId, setSelectedSkuId] = useState<string>()
  const [quantity, setQuantity] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [isAdding, setIsAdding] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [cartCount, setCartCount] = useState(0)
  const [failedImages, setFailedImages] = useState<Set<string>>(new Set())

  async function loadProduct() {
    let store = readCurrentStore()
    const sharedStoreId = router.params.storeId
    const productId = router.params.id
    setIsLoading(true)
    setErrorMessage(null)
    try {
      if (sharedStoreId && store?.id !== sharedStoreId) {
        const stores = await listPublicStores({})
        store = stores.items.find((item) => item.id === sharedStoreId) ?? null
        if (store) saveCurrentStore(store)
      }
      if (!store || !productId) {
        throw new Error(!store ? '分享门店不存在或已停用' : '课程参数无效')
      }
      const response = await getCourseProduct(store.id, productId)
      setProduct(response)
      setSelectedSkuId(response.skus[0]?.id)
      setCartCount(cartQuantity(store.id))
      setFailedImages(new Set())
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '课程详情加载失败')
    } finally {
      setIsLoading(false)
    }
  }

  useLoad(() => {
    void loadProduct()
  })

  useShareAppMessage(() => ({
    title: product?.name ?? '慕义音乐课程',
    path: `/pages/course-detail/index?id=${router.params.id ?? ''}&storeId=${router.params.storeId ?? readCurrentStore()?.id ?? ''}`,
  }))

  async function addToCart(openCart: boolean) {
    const store = readCurrentStore()
    const sku = product?.skus.find((item) => item.id === selectedSkuId)
    if (!store || !product || !sku) {
      await Taro.showToast({ title: '请选择课程规格', icon: 'none' })
      return
    }
    setIsAdding(true)
    try {
      const validation = await validateCoursePurchase(store.id, product.id, {
        sku_id: sku.id,
        quantity,
      })
      const items = addCartItem(store.id, {
        productId: product.id,
        productName: validation.product_name,
        skuId: validation.sku_id,
        skuName: validation.sku_name,
        quantity: validation.quantity,
        unitPriceCents: validation.unit_price_cents,
        coverUrl: product.cover_url,
        validatedAt: validation.validated_at,
      })
      setCartCount(items.reduce((total, item) => total + item.quantity, 0))
      if (openCart) {
        await Taro.redirectTo({ url: '/pages/cart/index' })
      } else {
        await Taro.showToast({ title: '已加入购物车', icon: 'success' })
      }
    } catch (error) {
      await Taro.showToast({
        title: error instanceof Error ? error.message : '加入购物车失败',
        icon: 'none',
      })
    } finally {
      setIsAdding(false)
    }
  }

  if (isLoading) {
    return (
      <View className="detail-page">
        <View className="detail-loading-cover" />
        <View className="detail-loading-body">
          <View />
          <View />
          <View />
        </View>
      </View>
    )
  }

  if (errorMessage || !product) {
    return (
      <View className="detail-page detail-page--state">
        <Text className="detail-state-title">课程暂不可查看</Text>
        <Text className="detail-state-copy">{errorMessage ?? '课程不存在'}</Text>
        <Button className="detail-retry-button" size="mini" onClick={() => void loadProduct()}>
          重试
        </Button>
      </View>
    )
  }

  const media = [
    { id: 'cover', url: product.cover_url },
    ...product.images.map((image) => ({ id: image.id, url: image.image_url })),
  ].filter((item): item is { id: string; url: string } => Boolean(item.url))
  const selectedSku = product.skus.find((sku) => sku.id === selectedSkuId)
  const totalPrice = (selectedSku?.price_cents ?? 0) * quantity

  async function shareCourse(currentProduct: ProductPublicRead) {
    if (Taro.getEnv() !== Taro.ENV_TYPE.WEB) {
      return
    }
    try {
      await Taro.setClipboardData({
        data: `${currentProduct.name}\n/pages/course-detail/index?id=${currentProduct.id}&storeId=${router.params.storeId ?? readCurrentStore()?.id ?? ''}`,
      })
      await Taro.showToast({ title: '课程信息已复制', icon: 'success' })
    } catch {
      await Taro.showToast({ title: '分享暂不可用', icon: 'none' })
    }
  }

  return (
    <View className="detail-page detail-page--content">
      {media.length ? (
        <Swiper className="detail-gallery" indicatorDots circular>
          {media.map((item) => (
            <SwiperItem key={item.id}>
              {failedImages.has(item.id) ? (
                <View className="detail-media-empty">图片加载失败</View>
              ) : (
                <Image
                  className="detail-gallery-image"
                  src={item.url}
                  mode="aspectFill"
                  onError={() =>
                    setFailedImages((current) => new Set(current).add(item.id))
                  }
                />
              )}
            </SwiperItem>
          ))}
        </Swiper>
      ) : (
        <View className="detail-gallery detail-media-empty">课程图片</View>
      )}

      <View className="detail-main">
        <View className="detail-category-row">
          <Text className="detail-category">{product.category_name}</Text>
          <Button
            className="detail-share-button"
            size="mini"
            openType="share"
            onClick={() => void shareCourse(product)}
          >
            分享
          </Button>
        </View>
        <Text className="detail-name">{product.name}</Text>
        <Text className="detail-summary">{product.summary || '门店精品课程'}</Text>
        <View className="detail-sales-line">
          <Text className="detail-price">{formatMoney(selectedSku?.price_cents ?? 0)}</Text>
          <Text>已售 {product.sales_count}</Text>
        </View>
      </View>

      <View className="detail-section">
        <Text className="detail-section-title">选择规格</Text>
        <View className="sku-options">
          {product.skus.map((sku) => (
            <View
              className={`sku-option${sku.id === selectedSkuId ? ' sku-option--active' : ''}`}
              key={sku.id}
              onClick={() => setSelectedSkuId(sku.id)}
            >
              <View>
                <Text>{sku.name}</Text>
                <Text>
                  {product.product_type === 'video'
                    ? `${sku.validity_days} 天观看权益`
                    : `${sku.lesson_count} 课时 · ${sku.validity_days} 天有效`}
                </Text>
              </View>
              <Text>{formatMoney(sku.price_cents)}</Text>
            </View>
          ))}
        </View>
        <View className="quantity-row">
          <Text>购买数量</Text>
          <View className="quantity-stepper">
            <Button
              size="mini"
              disabled={quantity <= 1}
              aria-label="减少数量"
              onClick={() => setQuantity((current) => Math.max(1, current - 1))}
            >
              −
            </Button>
            <Text>{quantity}</Text>
            <Button
              size="mini"
              disabled={quantity >= 99}
              aria-label="增加数量"
              onClick={() => setQuantity((current) => Math.min(99, current + 1))}
            >
              +
            </Button>
          </View>
        </View>
      </View>

      {product.product_type === 'video' && product.video_chapters.length > 0 ? (
        <View className="detail-section">
          <Text className="detail-section-title">
            视频章节（{product.video_chapters.length}）
          </Text>
          <View className="detail-chapters">
            {product.video_chapters.map((chapter, index) => (
              <View className="detail-chapter" key={chapter.id}>
                <Text className="detail-chapter-index">{index + 1}</Text>
                <Text className="detail-chapter-title">{chapter.title}</Text>
                <Text className="detail-chapter-duration">
                  {formatDuration(chapter.duration_seconds)}
                </Text>
              </View>
            ))}
          </View>
          <Text className="detail-chapter-notice">
            购买后可在「我的 - 我的课程」中观看视频
          </Text>
        </View>
      ) : null}

      <View className="detail-section detail-copy">
        <Text className="detail-section-title">课程详情</Text>
        <Text>{product.details || '暂无课程详情'}</Text>
      </View>

      {product.notes ? (
        <View className="detail-section detail-copy">
          <Text className="detail-section-title">购买须知</Text>
          <Text>{product.notes}</Text>
        </View>
      ) : null}

      <View className="detail-action-bar">
        <Button
          className="detail-home-shortcut"
          size="mini"
          onClick={() => void Taro.switchTab({ url: '/pages/home/index' })}
        >
          首页
        </Button>
        <Button
          className="detail-contact-shortcut"
          size="mini"
          onClick={() => {
            const currentStore = readCurrentStore()
            if (currentStore) {
              void Taro.makePhoneCall({ phoneNumber: currentStore.phone })
            }
          }}
        >
          联系
        </Button>
        <Button
          className="detail-cart-shortcut"
          size="mini"
          onClick={() => void Taro.redirectTo({ url: '/pages/cart/index' })}
        >
          购物车{cartCount ? ` ${cartCount}` : ''}
        </Button>
        <View className="detail-total">
          <Text>合计</Text>
          <Text>{formatMoney(totalPrice)}</Text>
        </View>
        <Button
          className="detail-add-button"
          size="mini"
          loading={isAdding}
          disabled={!selectedSku}
          onClick={() => void addToCart(false)}
        >
          加入购物车
        </Button>
        <Button
          className="detail-buy-button"
          size="mini"
          loading={isAdding}
          disabled={!selectedSku}
          onClick={() => void addToCart(true)}
        >
          立即购买
        </Button>
      </View>
    </View>
  )
}
