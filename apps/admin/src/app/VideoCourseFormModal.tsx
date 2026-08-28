import type {
  CategoryRead,
  StoreRead,
  VideoCourseCreate,
  VideoCourseRead,
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
import type { UploadProps } from 'antd'
import { Plus, Trash2, UploadCloud } from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'

interface Props {
  open: boolean
  store: StoreRead
  categories: CategoryRead[]
  videoCourse: VideoCourseRead | null
  onClose: () => void
  onSaved: () => Promise<void>
}

interface LessonValue {
  id?: string
  lesson_number: number
  title: string
  object_key: string
  duration_seconds: number | null
  is_active: boolean
}

interface FormValues {
  category_id: string
  name: string
  summary: string
  is_active: boolean
  lessons: LessonValue[]
}

function fileName(objectKey: string): string {
  return objectKey.split('/').at(-1) ?? '教学视频'
}

export function VideoCourseFormModal({
  open,
  store,
  categories,
  videoCourse,
  onClose,
  onSaved,
}: Props) {
  const { message } = AntdApp.useApp()
  const [form] = Form.useForm<FormValues>()
  const [saving, setSaving] = useState(false)
  const [uploadingIndex, setUploadingIndex] = useState<number | null>(null)
  const lessons = Form.useWatch('lessons', form) ?? []

  function initialize() {
    form.setFieldsValue({
      category_id: videoCourse?.category_id ?? categories[0]?.id,
      name: videoCourse?.name ?? '',
      summary: videoCourse?.summary ?? '',
      is_active: videoCourse?.is_active ?? true,
      lessons:
        videoCourse?.lessons.map((lesson) => ({
          id: lesson.id,
          lesson_number: lesson.lesson_number,
          title: lesson.title,
          object_key: lesson.object_key,
          duration_seconds: lesson.duration_seconds,
          is_active: lesson.is_active,
        })) ?? [
          {
            lesson_number: 1,
            title: '',
            object_key: '',
            duration_seconds: null,
            is_active: true,
          },
        ],
    })
  }

  const uploadVideo =
    (index: number): UploadProps['customRequest'] =>
    async (options) => {
      const file = options.file as File
      setUploadingIndex(index)
      try {
        const ticket = await apiClient.createUploadTicket({
          store_id: store.id,
          file_name: file.name,
          content_type: file.type,
          file_size: file.size,
          purpose: 'product_video',
        })
        const response = await fetch(ticket.upload_url, {
          method: ticket.method,
          headers: ticket.headers,
          body: file,
        })
        if (!response.ok) {
          throw new Error(`对象存储上传失败（${response.status}）`)
        }
        form.setFieldValue(['lessons', index, 'object_key'], ticket.object_key)
        options.onSuccess?.({ objectKey: ticket.object_key })
        void message.success('课时视频上传完成')
      } catch (error) {
        const uploadError =
          error instanceof Error ? error : new Error('视频上传失败')
        options.onError?.(uploadError)
        void message.error(uploadError.message)
      } finally {
        setUploadingIndex(null)
      }
    }

  async function save() {
    const values = await form.validateFields()
    const payload: VideoCourseCreate = {
      category_id: values.category_id,
      name: values.name,
      summary: values.summary,
      is_active: values.is_active,
      lessons: values.lessons.map((lesson) => ({
        id: lesson.id ?? null,
        lesson_number: lesson.lesson_number,
        title: lesson.title,
        object_key: lesson.object_key,
        duration_seconds: lesson.duration_seconds,
        is_active: lesson.is_active,
      })),
    }
    setSaving(true)
    try {
      if (videoCourse) {
        await apiClient.updateVideoCourse(store.id, videoCourse.id, payload)
      } else {
        await apiClient.createVideoCourse(store.id, {
          ...payload,
          lessons: payload.lessons.map((lesson) => {
            const createLesson = { ...lesson }
            delete createLesson.id
            return createLesson
          }),
        })
      }
      await onSaved()
      void message.success(videoCourse ? '视频课程已更新' : '视频课程已创建')
      onClose()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      width={980}
      title={videoCourse ? '编辑视频课程' : '创建视频课程'}
      okText="保存"
      cancelText="取消"
      confirmLoading={saving}
      destroyOnHidden
      afterOpenChange={(visible) => visible && initialize()}
      onOk={() => void save()}
      onCancel={onClose}
    >
      <Form<FormValues> form={form} layout="vertical" requiredMark="optional">
        <div className="form-grid form-grid--two">
          <Form.Item
            name="category_id"
            label="课程分类"
            rules={[{ required: true, message: '请选择课程分类' }]}
          >
            <Select
              options={categories.map((category) => ({
                value: category.id,
                label: category.name,
                disabled: !category.is_enabled,
              }))}
            />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </div>
        <Form.Item
          name="name"
          label="视频课程名称"
          rules={[{ required: true, message: '请输入视频课程名称' }]}
        >
          <Input maxLength={128} />
        </Form.Item>
        <Form.Item name="summary" label="课程简介">
          <Input.TextArea rows={3} maxLength={300} showCount />
        </Form.Item>
        <div className="sku-heading">
          <strong>视频课时</strong>
          <span>每个课时对应上传一段视频</span>
        </div>
        <Form.List name="lessons">
          {(fields, { add, remove }) => (
            <div className="chapter-list">
              {fields.map((field, index) => {
                const objectKey = lessons[field.name]?.object_key ?? ''
                return (
                  <div className="chapter-row" key={field.key}>
                    <Form.Item name={[field.name, 'id']} hidden>
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name={[field.name, 'object_key']}
                      hidden
                      rules={[{ required: true, message: '请上传课时视频' }]}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name={[field.name, 'lesson_number']}
                      label="课时序号"
                      rules={[{ required: true }]}
                    >
                      <InputNumber className="field-full" min={1} max={10000} />
                    </Form.Item>
                    <Form.Item
                      name={[field.name, 'title']}
                      label="课时标题"
                      rules={[{ required: true, message: '请输入课时标题' }]}
                    >
                      <Input maxLength={128} />
                    </Form.Item>
                    <Form.Item name={[field.name, 'duration_seconds']} label="时长（秒）">
                      <InputNumber className="field-full" min={1} max={604800} />
                    </Form.Item>
                    <Form.Item
                      name={[field.name, 'is_active']}
                      label="启用"
                      valuePropName="checked"
                    >
                      <Switch size="small" />
                    </Form.Item>
                    <Form.Item label="教学视频" required>
                      <Upload
                        accept="video/mp4,video/quicktime,video/webm"
                        customRequest={uploadVideo(field.name)}
                        showUploadList={false}
                        disabled={uploadingIndex !== null}
                      >
                        <Button
                          loading={uploadingIndex === field.name}
                          icon={<UploadCloud size={15} aria-hidden="true" />}
                        >
                          {objectKey ? '更换视频' : '上传视频'}
                        </Button>
                      </Upload>
                      {objectKey ? (
                        <span className="chapter-file">{fileName(objectKey)}</span>
                      ) : null}
                    </Form.Item>
                    <Button
                      className="sku-remove"
                      type="text"
                      danger
                      disabled={fields.length === 1}
                      icon={<Trash2 size={17} aria-hidden="true" />}
                      aria-label={`移除第 ${index + 1} 个视频课时`}
                      onClick={() => remove(field.name)}
                    />
                  </div>
                )
              })}
              <Button
                block
                type="dashed"
                icon={<Plus size={17} aria-hidden="true" />}
                onClick={() =>
                  add({
                    lesson_number: fields.length + 1,
                    title: '',
                    object_key: '',
                    duration_seconds: null,
                    is_active: true,
                  })
                }
              >
                添加视频课时
              </Button>
            </div>
          )}
        </Form.List>
      </Form>
    </Modal>
  )
}
