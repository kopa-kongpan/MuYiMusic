import type {
  ContentBlockCreate,
  ContentBlockRead,
  ContentBlockType,
  ContentJumpType,
  StoreRead,
} from '@muyimusic/api-client'
import {
  App as AntdApp,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Select,
  Switch,
  Upload,
} from 'antd'
import type { UploadFile, UploadProps } from 'antd'
import { ImagePlus, UploadCloud, Video } from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'

interface ContentFormModalProps {
  open: boolean
  store: StoreRead
  content: ContentBlockRead | null
  onClose: () => void
  onSaved: () => Promise<void>
}

interface ContentFormValues {
  block_type: ContentBlockType
  title: string
  media_object_key?: string
  jump_type: ContentJumpType
  jump_target?: string
  sort_order: number
  is_enabled: boolean
  starts_at?: string
  ends_at?: string
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
  return objectKey.split('/').at(-1) ?? '已上传媒体'
}

export function ContentFormModal({
  open,
  store,
  content,
  onClose,
  onSaved,
}: ContentFormModalProps) {
  const { message } = AntdApp.useApp()
  const [form] = Form.useForm<ContentFormValues>()
  const blockType = Form.useWatch('block_type', form) ?? 'image'
  const jumpType = Form.useWatch('jump_type', form) ?? 'none'
  const [isSaving, setIsSaving] = useState(false)
  const [fileList, setFileList] = useState<UploadFile[]>([])

  function initializeForm() {
    form.setFieldsValue({
      block_type: content?.block_type ?? 'image',
      title: content?.title ?? '',
      media_object_key: content?.media_object_key ?? undefined,
      jump_type: content?.jump_type ?? 'none',
      jump_target: content?.jump_target ?? undefined,
      sort_order: content?.sort_order ?? 0,
      is_enabled: content?.status !== 'disabled',
      starts_at: toLocalDateTime(content?.starts_at),
      ends_at: toLocalDateTime(content?.ends_at),
    })
    setFileList(
      content?.media_object_key
        ? [
            {
              uid: content.id,
              name: fileNameFromKey(content.media_object_key),
              status: 'done',
              url: content.media_url ?? undefined,
            },
          ]
        : [],
    )
  }

  const uploadMedia: UploadProps['customRequest'] = async (options) => {
    const file = options.file as File
    try {
      const ticket = await apiClient.createUploadTicket({
        store_id: store.id,
        file_name: file.name,
        content_type: file.type,
        file_size: file.size,
      })
      const response = await fetch(ticket.upload_url, {
        method: ticket.method,
        headers: ticket.headers,
        body: file,
      })
      if (!response.ok) {
        throw new Error(`对象存储上传失败（${response.status}）`)
      }
      form.setFieldValue('media_object_key', ticket.object_key)
      setFileList([
        {
          uid: ticket.object_key,
          name: file.name,
          status: 'done',
          url: ticket.public_url ?? undefined,
        },
      ])
      options.onSuccess?.({ objectKey: ticket.object_key })
      void message.success('媒体上传完成')
    } catch (error) {
      const uploadError = error instanceof Error ? error : new Error('媒体上传失败')
      setFileList([
        {
          uid: file.name,
          name: file.name,
          status: 'error',
          error: uploadError,
        },
      ])
      options.onError?.(uploadError)
      void message.error(uploadError.message)
    }
  }

  async function save() {
    const values = await form.validateFields()
    const startsAt = toIsoDateTime(values.starts_at)
    const endsAt = toIsoDateTime(values.ends_at)
    if (startsAt && endsAt && startsAt >= endsAt) {
      form.setFields([
        { name: 'ends_at', errors: ['结束时间必须晚于开始时间'] },
      ])
      return
    }
    const payload: ContentBlockCreate = {
      block_type: values.block_type,
      title: values.title,
      media_object_key: values.media_object_key || null,
      jump_type: values.jump_type,
      jump_target: values.jump_type === 'none' ? null : values.jump_target || null,
      sort_order: values.sort_order,
      status: values.is_enabled ? 'enabled' : 'disabled',
      starts_at: startsAt,
      ends_at: endsAt,
    }
    setIsSaving(true)
    try {
      if (content) {
        await apiClient.updateStoreContent(store.id, content.id, payload)
      } else {
        await apiClient.createStoreContent(store.id, payload)
      }
      await onSaved()
      void message.success(content ? '首页内容已更新' : '首页内容已创建')
      onClose()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setIsSaving(false)
    }
  }

  function clearMedia() {
    form.setFieldValue('media_object_key', undefined)
    setFileList([])
  }

  return (
    <Modal
      open={open}
      title={content ? '编辑首页内容' : '创建首页内容'}
      width={680}
      okText="保存"
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
      <Form<ContentFormValues>
        className="content-form"
        form={form}
        layout="vertical"
        requiredMark="optional"
      >
        <Form.Item label="所属门店">
          <Input value={store.name} disabled />
        </Form.Item>

        <Form.Item name="block_type" label="内容类型" rules={[{ required: true }]}>
          <Segmented
            block
            options={[
              {
                label: '图片',
                value: 'image',
                icon: <ImagePlus size={16} aria-hidden="true" />,
              },
              {
                label: '视频',
                value: 'video',
                icon: <Video size={16} aria-hidden="true" />,
              },
              { label: '快捷入口', value: 'shortcut' },
            ]}
            onChange={(value) => {
              if (value !== blockType) {
                clearMedia()
              }
              if (value === 'shortcut' && form.getFieldValue('jump_type') === 'none') {
                form.setFieldValue('jump_type', 'internal')
              }
            }}
          />
        </Form.Item>

        <div className="form-grid form-grid--two">
          <Form.Item
            name="title"
            label="内容标题"
            rules={[
              { required: true, message: '请输入内容标题' },
              { max: 128, message: '标题不能超过 128 个字符' },
            ]}
          >
            <Input placeholder="例如：琴房环境" />
          </Form.Item>
          <Form.Item name="sort_order" label="展示顺序" rules={[{ required: true }]}>
            <InputNumber className="field-full" min={0} max={9999} />
          </Form.Item>
        </div>

        {blockType !== 'shortcut' ? (
          <Form.Item
            label={blockType === 'image' ? '图片文件' : '视频文件'}
            required
          >
            <Form.Item
              name="media_object_key"
              noStyle
              rules={[{ required: true, message: '请先上传媒体文件' }]}
            >
              <Input type="hidden" />
            </Form.Item>
            <Upload
              accept={
                blockType === 'image'
                  ? 'image/jpeg,image/png,image/webp,image/gif'
                  : 'video/mp4,video/webm,video/quicktime'
              }
              customRequest={uploadMedia}
              fileList={fileList}
              listType={blockType === 'image' ? 'picture' : 'text'}
              maxCount={1}
              onChange={({ fileList: nextFileList }) =>
                setFileList(nextFileList.slice(-1))
              }
              onRemove={() => {
                clearMedia()
                return true
              }}
            >
              <button className="upload-trigger" type="button">
                <UploadCloud size={22} aria-hidden="true" />
                <span>{fileList.length ? '替换文件' : '选择并上传'}</span>
              </button>
            </Upload>
          </Form.Item>
        ) : null}

        <div className="form-grid form-grid--two">
          <Form.Item name="jump_type" label="跳转类型" rules={[{ required: true }]}>
            <Select<ContentJumpType>
              options={[
                { label: '不跳转', value: 'none', disabled: blockType === 'shortcut' },
                { label: '小程序页面', value: 'internal' },
                { label: '网页链接', value: 'web_url' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="jump_target"
            label="跳转目标"
            rules={
              jumpType === 'none'
                ? []
                : [{ required: true, message: '请输入跳转目标' }]
            }
          >
            <Input
              disabled={jumpType === 'none'}
              placeholder={
                jumpType === 'internal'
                  ? '/pages/courses/index'
                  : 'https://example.com/activity'
              }
            />
          </Form.Item>
        </div>

        <div className="form-grid form-grid--two">
          <Form.Item name="starts_at" label="展示开始时间">
            <Input type="datetime-local" />
          </Form.Item>
          <Form.Item name="ends_at" label="展示结束时间">
            <Input type="datetime-local" />
          </Form.Item>
        </div>

        <Form.Item
          name="is_enabled"
          label="启用状态"
          valuePropName="checked"
        >
          <Switch checkedChildren="启用" unCheckedChildren="停用" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
