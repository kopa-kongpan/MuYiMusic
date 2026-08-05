import type {
  ProductRead,
  ScheduleRead,
  TeacherRead,
} from '@muyimusic/api-client'
import { App as AntdApp, Form, Input, InputNumber, Modal, Select } from 'antd'
import { useEffect, useState } from 'react'

import { apiClient } from './api'

interface ScheduleFormValues {
  teacher_id: string
  product_id?: string
  course_name: string
  starts_at: string
  ends_at: string
  capacity: number
  notes: string
}

interface ScheduleFormModalProps {
  open: boolean
  storeId: string
  selectedDate: string
  teachers: TeacherRead[]
  products: ProductRead[]
  schedule: ScheduleRead | null
  onClose: () => void
  onSaved: () => Promise<void>
}

function toLocalInput(value: string): string {
  const date = new Date(value)
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function defaultTimes(selectedDate: string): { starts_at: string; ends_at: string } {
  const selected = new Date(`${selectedDate}T10:00:00`)
  const now = new Date()
  if (selected <= now) {
    selected.setTime(now.getTime())
    selected.setMinutes(0, 0, 0)
    selected.setHours(selected.getHours() + 1)
  }
  const end = new Date(selected.getTime() + 60 * 60 * 1000)
  return {
    starts_at: toLocalInput(selected.toISOString()),
    ends_at: toLocalInput(end.toISOString()),
  }
}

export function ScheduleFormModal({
  open,
  storeId,
  selectedDate,
  teachers,
  products,
  schedule,
  onClose,
  onSaved,
}: ScheduleFormModalProps) {
  const { message } = AntdApp.useApp()
  const [form] = Form.useForm<ScheduleFormValues>()
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (!open) {
      return
    }
    if (schedule) {
      form.setFieldsValue({
        teacher_id: schedule.teacher_id,
        product_id: schedule.product_id ?? undefined,
        course_name: schedule.course_name,
        starts_at: toLocalInput(schedule.starts_at),
        ends_at: toLocalInput(schedule.ends_at),
        capacity: schedule.capacity,
        notes: schedule.notes,
      })
      return
    }
    form.setFieldsValue({
      teacher_id: teachers.find((teacher) => teacher.is_active)?.id,
      product_id: undefined,
      course_name: '',
      ...defaultTimes(selectedDate),
      capacity: 1,
      notes: '',
    })
  }, [form, open, schedule, selectedDate, teachers])

  async function save(values: ScheduleFormValues) {
    setIsSaving(true)
    try {
      const payload = {
        teacher_id: values.teacher_id,
        product_id: values.product_id || null,
        course_name: values.course_name.trim(),
        starts_at: new Date(values.starts_at).toISOString(),
        ends_at: new Date(values.ends_at).toISOString(),
        capacity: values.capacity,
        notes: values.notes ?? '',
      }
      if (schedule) {
        await apiClient.updateSchedule(storeId, schedule.id, payload)
      } else {
        await apiClient.createSchedule(storeId, payload)
      }
      await onSaved()
      onClose()
      void message.success(schedule ? '排课已更新' : '排课已创建')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      width={680}
      title={schedule ? '编辑排课' : '创建排课'}
      okText={schedule ? '保存' : '创建'}
      cancelText="取消"
      confirmLoading={isSaving}
      destroyOnHidden
      onOk={() => form.submit()}
      onCancel={onClose}
    >
      <Form<ScheduleFormValues>
        form={form}
        className="schedule-form"
        layout="vertical"
        onFinish={(values) => void save(values)}
      >
        <div className="form-grid form-grid--two">
          <Form.Item
            name="teacher_id"
            label="教师"
            rules={[{ required: true, message: '请选择教师' }]}
          >
            <Select
              placeholder="选择启用教师"
              options={teachers
                .filter((teacher) => teacher.is_active)
                .map((teacher) => ({ label: teacher.name, value: teacher.id }))}
            />
          </Form.Item>
          <Form.Item name="product_id" label="关联课程商品（可选）">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="可关联已发布商品"
              options={products.map((product) => ({
                label: product.name,
                value: product.id,
              }))}
              onChange={(productId) => {
                const product = products.find((item) => item.id === productId)
                if (product) {
                  form.setFieldValue('course_name', product.name)
                }
              }}
            />
          </Form.Item>
        </div>
        <Form.Item
          name="course_name"
          label="课程名称"
          rules={[{ required: true, message: '请输入课程名称' }]}
        >
          <Input maxLength={128} placeholder="排课展示名称" />
        </Form.Item>
        <div className="form-grid form-grid--two">
          <Form.Item
            name="starts_at"
            label="开始时间"
            rules={[{ required: true, message: '请选择开始时间' }]}
          >
            <Input type="datetime-local" />
          </Form.Item>
          <Form.Item
            name="ends_at"
            label="结束时间"
            rules={[{ required: true, message: '请选择结束时间' }]}
          >
            <Input type="datetime-local" />
          </Form.Item>
        </div>
        <Form.Item
          name="capacity"
          label="可约名额"
          rules={[{ required: true, message: '请输入名额' }]}
        >
          <InputNumber className="field-full" min={1} max={200} />
        </Form.Item>
        <Form.Item name="notes" label="到课说明">
          <Input.TextArea rows={3} maxLength={2000} showCount />
        </Form.Item>
      </Form>
    </Modal>
  )
}
