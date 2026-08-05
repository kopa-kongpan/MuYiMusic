import type {
  CategoryRead,
  ProductCreate,
  ProductRead,
  StoreRead,
} from '@muyimusic/api-client'
import {
  App as AntdApp,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Switch,
  Upload,
} from 'antd'
import type { UploadFile, UploadProps } from 'antd'
import { ImagePlus, Plus, Trash2, UploadCloud } from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'

interface ProductFormModalProps {
  open: boolean
  store: StoreRead
  categories: CategoryRead[]
  product: ProductRead | null
  onClose: () => void
  onSaved: () => Promise<void>
}

interface SkuFormValue {
  id?: string
  name: string
  price_yuan: number
  lesson_count: number
  validity_days: number
  sort_order: number
  is_active: boolean
}

interface ProductFormValues {
  category_id: string
  name: string
  summary: string
  details: string
  notes?: string
  cover_object_key: string
  sale_starts_at?: string
  sale_ends_at?: string
  sort_order: number
  skus: SkuFormValue[]
}

interface ProductImageValue {
  objectKey: string
  name: string
  url?: string
  sortOrder: number
}

function toLocalDateTime(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined
  }
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

function toIsoDateTime(value: string | undefined): string | null {
  return value ? new Date(value).toISOString() : null
}

function fileNameFromKey(objectKey: string): string {
  return objectKey.split('/').at(-1) ?? '商品图片'
}

export function ProductFormModal({
  open,
  store,
  categories,
  product,
  onClose,
  onSaved,
}: ProductFormModalProps) {
  const { message } = AntdApp.useApp()
  const [form] = Form.useForm<ProductFormValues>()
  const [isSaving, setIsSaving] = useState(false)
  const [coverFiles, setCoverFiles] = useState<UploadFile[]>([])
  const [images, setImages] = useState<ProductImageValue[]>([])

  function initializeForm() {
    form.setFieldsValue({
      category_id: product?.category_id ?? categories[0]?.id,
      name: product?.name ?? '',
      summary: product?.summary ?? '',
      details: product?.details ?? '',
      notes: product?.notes ?? undefined,
      cover_object_key: product?.cover_object_key ?? '',
      sale_starts_at: toLocalDateTime(product?.sale_starts_at),
      sale_ends_at: toLocalDateTime(product?.sale_ends_at),
      sort_order: product?.sort_order ?? 0,
      skus:
        product?.skus.map((sku) => ({
          id: sku.id,
          name: sku.name,
          price_yuan: sku.price_cents / 100,
          lesson_count: sku.lesson_count,
          validity_days: sku.validity_days,
          sort_order: sku.sort_order,
          is_active: sku.is_active,
        })) ?? [
          {
            name: '',
            price_yuan: 0,
            lesson_count: 1,
            validity_days: 30,
            sort_order: 10,
            is_active: true,
          },
        ],
    })
    setCoverFiles(
      product
        ? [
            {
              uid: product.cover_object_key,
              name: fileNameFromKey(product.cover_object_key),
              status: 'done',
              url: product.cover_url ?? undefined,
            },
          ]
        : [],
    )
    setImages(
      product?.images.map((image) => ({
        objectKey: image.object_key,
        name: fileNameFromKey(image.object_key),
        url: image.image_url ?? undefined,
        sortOrder: image.sort_order,
      })) ?? [],
    )
  }

  async function uploadFile(file: File) {
    const ticket = await apiClient.createUploadTicket({
      store_id: store.id,
      file_name: file.name,
      content_type: file.type,
      file_size: file.size,
      purpose: 'product',
    })
    const response = await fetch(ticket.upload_url, {
      method: ticket.method,
      headers: ticket.headers,
      body: file,
    })
    if (!response.ok) {
      throw new Error(`对象存储上传失败（${response.status}）`)
    }
    return ticket
  }

  const uploadCover: UploadProps['customRequest'] = async (options) => {
    const file = options.file as File
    try {
      const ticket = await uploadFile(file)
      form.setFieldValue('cover_object_key', ticket.object_key)
      setCoverFiles([
        {
          uid: ticket.object_key,
          name: file.name,
          status: 'done',
          url: ticket.public_url ?? undefined,
        },
      ])
      options.onSuccess?.({ objectKey: ticket.object_key })
      void message.success('商品封面上传完成')
    } catch (error) {
      const uploadError = error instanceof Error ? error : new Error('封面上传失败')
      options.onError?.(uploadError)
      void message.error(uploadError.message)
    }
  }

  const uploadGalleryImage: UploadProps['customRequest'] = async (options) => {
    const file = options.file as File
    try {
      const ticket = await uploadFile(file)
      setImages((current) => [
        ...current,
        {
          objectKey: ticket.object_key,
          name: file.name,
          url: ticket.public_url ?? undefined,
          sortOrder: (current.length + 1) * 10,
        },
      ])
      options.onSuccess?.({ objectKey: ticket.object_key })
    } catch (error) {
      const uploadError = error instanceof Error ? error : new Error('图片上传失败')
      options.onError?.(uploadError)
      void message.error(uploadError.message)
    }
  }

  async function save() {
    const values = await form.validateFields()
    const startsAt = toIsoDateTime(values.sale_starts_at)
    const endsAt = toIsoDateTime(values.sale_ends_at)
    if (startsAt && endsAt && startsAt >= endsAt) {
      form.setFields([
        { name: 'sale_ends_at', errors: ['结束时间必须晚于开始时间'] },
      ])
      return
    }
    const payload: ProductCreate = {
      category_id: values.category_id,
      name: values.name,
      summary: values.summary,
      details: values.details,
      notes: values.notes || null,
      cover_object_key: values.cover_object_key,
      sale_starts_at: startsAt,
      sale_ends_at: endsAt,
      sort_order: values.sort_order,
      skus: values.skus.map((sku) => ({
        id: sku.id ?? null,
        name: sku.name,
        price_cents: Math.round(sku.price_yuan * 100),
        lesson_count: sku.lesson_count,
        validity_days: sku.validity_days,
        sort_order: sku.sort_order,
        is_active: sku.is_active,
      })),
      images: images.map((image, index) => ({
        object_key: image.objectKey,
        sort_order: (index + 1) * 10,
      })),
    }
    setIsSaving(true)
    try {
      if (product) {
        await apiClient.updateProduct(store.id, product.id, payload)
      } else {
        await apiClient.createProduct(store.id, {
          ...payload,
          skus: payload.skus.map((sku) => {
            const createSku = { ...sku }
            delete createSku.id
            return createSku
          }),
        })
      }
      await onSaved()
      void message.success(product ? '课程商品已更新' : '课程商品已创建')
      onClose()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setIsSaving(false)
    }
  }

  const galleryFiles: UploadFile[] = images.map((image) => ({
    uid: image.objectKey,
    name: image.name,
    status: 'done',
    url: image.url,
  }))

  return (
    <Modal
      open={open}
      title={product ? '编辑课程商品' : '创建课程商品'}
      width={920}
      okText="保存草稿"
      cancelText="取消"
      confirmLoading={isSaving}
      destroyOnHidden
      afterOpenChange={(isOpen) => {
        if (isOpen) {
          initializeForm()
        }
      }}
      onOk={() => void save()}
      onCancel={onClose}
    >
      <Form<ProductFormValues>
        className="product-form"
        form={form}
        layout="vertical"
        requiredMark="optional"
      >
        <div className="form-grid form-grid--two">
          <Form.Item label="所属门店">
            <Input value={store.name} disabled />
          </Form.Item>
          <Form.Item
            name="category_id"
            label="课程分类"
            rules={[{ required: true, message: '请选择课程分类' }]}
          >
            <Select
              placeholder="选择分类"
              options={categories.map((category) => ({
                value: category.id,
                label: category.name,
                disabled: !category.is_enabled,
              }))}
            />
          </Form.Item>
        </div>

        <div className="form-grid form-grid--two">
          <Form.Item
            name="name"
            label="商品名称"
            rules={[{ required: true, message: '请输入商品名称' }]}
          >
            <Input maxLength={128} placeholder="例如：少儿钢琴启蒙课" />
          </Form.Item>
          <Form.Item name="sort_order" label="展示顺序" rules={[{ required: true }]}>
            <InputNumber className="field-full" min={0} max={9999} />
          </Form.Item>
        </div>

        <Form.Item name="summary" label="商品摘要">
          <Input maxLength={300} showCount placeholder="列表页展示的简短介绍" />
        </Form.Item>
        <Form.Item name="details" label="课程详情">
          <Input.TextArea rows={5} maxLength={50000} showCount />
        </Form.Item>
        <Form.Item name="notes" label="购买须知">
          <Input.TextArea rows={3} maxLength={5000} showCount />
        </Form.Item>

        <Form.Item label="商品封面" required>
          <Form.Item
            name="cover_object_key"
            noStyle
            rules={[{ required: true, message: '请上传商品封面' }]}
          >
            <Input type="hidden" />
          </Form.Item>
          <Upload
            accept="image/jpeg,image/png,image/webp,image/gif"
            customRequest={uploadCover}
            fileList={coverFiles}
            listType="picture"
            maxCount={1}
            onChange={({ fileList }) => setCoverFiles(fileList.slice(-1))}
            onRemove={() => {
              form.setFieldValue('cover_object_key', '')
              setCoverFiles([])
              return true
            }}
          >
            <button className="upload-trigger" type="button">
              <UploadCloud size={22} aria-hidden="true" />
              <span>{coverFiles.length ? '替换封面' : '上传封面'}</span>
            </button>
          </Upload>
        </Form.Item>

        <Form.Item label="商品图集">
          <Upload
            accept="image/jpeg,image/png,image/webp,image/gif"
            customRequest={uploadGalleryImage}
            fileList={galleryFiles}
            listType="picture-card"
            multiple
            maxCount={20}
            onChange={() => undefined}
            onRemove={(file) => {
              setImages((current) =>
                current.filter((image) => image.objectKey !== file.uid),
              )
              return true
            }}
          >
            {images.length < 20 ? (
              <button className="gallery-upload-trigger" type="button">
                <ImagePlus size={21} aria-hidden="true" />
                <span>添加图片</span>
              </button>
            ) : null}
          </Upload>
        </Form.Item>

        <div className="form-grid form-grid--two">
          <Form.Item name="sale_starts_at" label="销售开始时间">
            <Input type="datetime-local" />
          </Form.Item>
          <Form.Item name="sale_ends_at" label="销售结束时间">
            <Input type="datetime-local" />
          </Form.Item>
        </div>

        <div className="sku-heading">
          <strong>课程规格</strong>
          <span>金额按元录入，系统以整数分保存</span>
        </div>
        <Form.List name="skus">
          {(fields, { add, remove }) => (
            <div className="sku-list">
              {fields.map((field, index) => (
                <div className="sku-row" key={field.key}>
                  <Form.Item name={[field.name, 'id']} hidden>
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[field.name, 'name']}
                    label="规格名称"
                    rules={[{ required: true, message: '请输入规格名称' }]}
                  >
                    <Input maxLength={128} placeholder="例如：10 课时" />
                  </Form.Item>
                  <Form.Item
                    name={[field.name, 'price_yuan']}
                    label="售价（元）"
                    rules={[{ required: true, message: '请输入售价' }]}
                  >
                    <InputNumber className="field-full" min={0} precision={2} />
                  </Form.Item>
                  <Form.Item
                    name={[field.name, 'lesson_count']}
                    label="课时数"
                    rules={[{ required: true }]}
                  >
                    <InputNumber className="field-full" min={1} max={10000} />
                  </Form.Item>
                  <Form.Item
                    name={[field.name, 'validity_days']}
                    label="有效天数"
                    rules={[{ required: true }]}
                  >
                    <InputNumber className="field-full" min={1} max={36500} />
                  </Form.Item>
                  <Form.Item
                    name={[field.name, 'sort_order']}
                    label="顺序"
                    rules={[{ required: true }]}
                  >
                    <InputNumber className="field-full" min={0} max={9999} />
                  </Form.Item>
                  <Form.Item
                    name={[field.name, 'is_active']}
                    label="启用"
                    valuePropName="checked"
                  >
                    <Switch size="small" />
                  </Form.Item>
                  <Button
                    className="sku-remove"
                    type="text"
                    danger
                    disabled={fields.length === 1}
                    icon={<Trash2 size={17} aria-hidden="true" />}
                    aria-label={`移除第 ${index + 1} 个规格`}
                    onClick={() => remove(field.name)}
                  />
                </div>
              ))}
              <Button
                block
                type="dashed"
                icon={<Plus size={17} aria-hidden="true" />}
                onClick={() =>
                  add({
                    name: '',
                    price_yuan: 0,
                    lesson_count: 1,
                    validity_days: 30,
                    sort_order: (fields.length + 1) * 10,
                    is_active: true,
                  })
                }
              >
                添加课程规格
              </Button>
            </div>
          )}
        </Form.List>
      </Form>
    </Modal>
  )
}
