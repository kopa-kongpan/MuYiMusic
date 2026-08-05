import type { ProductRead, StoreRead } from '@muyimusic/api-client'
import { Drawer, Empty, Image, Tag } from 'antd'

interface ProductPreviewDrawerProps {
  open: boolean
  store: StoreRead | null
  product: ProductRead | null
  onClose: () => void
}

function formatMoney(priceCents: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(priceCents / 100)
}

export function ProductPreviewDrawer({
  open,
  store,
  product,
  onClose,
}: ProductPreviewDrawerProps) {
  return (
    <Drawer open={open} title="课程商品预览" width={520} onClose={onClose}>
      {product ? (
        <div className="product-preview">
          <div className="product-preview-cover">
            {product.cover_url ? (
              <Image src={product.cover_url} alt={product.name} preview={false} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="封面不可预览" />
            )}
          </div>
          <div className="product-preview-heading">
            <div>
              <h2>{product.name}</h2>
              <span>{store?.name ?? '当前门店'} · {product.category_name}</span>
            </div>
            <Tag>{product.status}</Tag>
          </div>
          <p className="product-preview-summary">{product.summary || '暂无摘要'}</p>
          <div className="product-preview-skus">
            {product.skus.map((sku) => (
              <div key={sku.id}>
                <div>
                  <strong>{sku.name}</strong>
                  <span>{sku.lesson_count} 课时 · {sku.validity_days} 天有效</span>
                </div>
                <strong>{formatMoney(sku.price_cents)}</strong>
              </div>
            ))}
          </div>
          <section className="product-preview-copy">
            <h3>课程详情</h3>
            <p>{product.details || '暂无详情'}</p>
          </section>
          {product.notes ? (
            <section className="product-preview-copy">
              <h3>购买须知</h3>
              <p>{product.notes}</p>
            </section>
          ) : null}
        </div>
      ) : null}
    </Drawer>
  )
}
