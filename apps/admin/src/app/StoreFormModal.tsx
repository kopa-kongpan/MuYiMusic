import type {
  StoreCreate,
  StoreRead,
  StoreStatus,
} from '@muyimusic/api-client'
import {
  App as AntdApp,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
} from 'antd'
import { useState } from 'react'

import { apiClient } from './api'

interface StoreFormModalProps {
  open: boolean
  store: StoreRead | null
  onClose: () => void
  onSaved: () => Promise<void>
}

interface StoreFormValues {
  name: string
  city: string
  district: string
  address: string
  phone: string
  latitude: number
  longitude: number
  status: StoreStatus
  sort_order: number
}

const initialValues: StoreFormValues = {
  name: '',
  city: '',
  district: '',
  address: '',
  phone: '',
  latitude: 22.543096,
  longitude: 114.057865,
  status: 'active',
  sort_order: 0,
}

export function StoreFormModal({
  open,
  store,
  onClose,
  onSaved,
}: StoreFormModalProps) {
  const [form] = Form.useForm<StoreFormValues>()
  const { message } = AntdApp.useApp()
  const [isSubmitting, setIsSubmitting] = useState(false)

  function prepareForm(isOpen: boolean) {
    if (!isOpen) {
      return
    }
    form.setFieldsValue(
      store
        ? {
            ...store,
            latitude: Number(store.latitude),
            longitude: Number(store.longitude),
          }
        : initialValues,
    )
  }

  async function submit(values: StoreFormValues) {
    setIsSubmitting(true)
    try {
      if (store) {
        await apiClient.updateStore(store.id, values)
      } else {
        await apiClient.createStore(values satisfies StoreCreate)
      }
      await onSaved()
      void message.success(store ? '门店信息已更新' : '门店已创建')
      form.resetFields()
      onClose()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal
      title={store ? '编辑门店' : '创建门店'}
      open={open}
      width={680}
      okText="保存"
      cancelText="取消"
      confirmLoading={isSubmitting}
      destroyOnHidden
      afterOpenChange={prepareForm}
      onOk={() => form.submit()}
      onCancel={onClose}
    >
      <Form<StoreFormValues>
        form={form}
        className="store-form"
        layout="vertical"
        requiredMark={false}
        preserve={false}
        onFinish={(values) => void submit(values)}
      >
        <div className="form-grid form-grid--two">
          <Form.Item
            name="name"
            label="门店名称"
            rules={[
              { required: true, message: '请输入门店名称' },
              { min: 2, max: 128, message: '请输入 2-128 个字符' },
            ]}
          >
            <Input placeholder="例如：慕义音乐南山店" />
          </Form.Item>
          <Form.Item
            name="phone"
            label="联系电话"
            rules={[{ required: true, message: '请输入联系电话' }]}
          >
            <Input placeholder="门店联系电话" />
          </Form.Item>
        </div>
        <div className="form-grid form-grid--two">
          <Form.Item
            name="city"
            label="城市"
            rules={[{ required: true, message: '请输入城市' }]}
          >
            <Input placeholder="例如：深圳市" />
          </Form.Item>
          <Form.Item name="district" label="区县">
            <Input placeholder="例如：南山区" />
          </Form.Item>
        </div>
        <Form.Item
          name="address"
          label="详细地址"
          rules={[
            { required: true, message: '请输入详细地址' },
            { min: 4, max: 500, message: '请输入 4-500 个字符' },
          ]}
        >
          <Input.TextArea rows={3} placeholder="街道、楼栋及门牌号" />
        </Form.Item>
        <div className="form-grid form-grid--two">
          <Form.Item
            name="latitude"
            label="纬度"
            rules={[{ required: true, message: '请输入纬度' }]}
          >
            <InputNumber className="field-full" min={-90} max={90} precision={6} />
          </Form.Item>
          <Form.Item
            name="longitude"
            label="经度"
            rules={[{ required: true, message: '请输入经度' }]}
          >
            <InputNumber
              className="field-full"
              min={-180}
              max={180}
              precision={6}
            />
          </Form.Item>
        </div>
        <div className="form-grid form-grid--two">
          <Form.Item name="status" label="营业状态" rules={[{ required: true }]}>
            <Select
              options={[
                { label: '营业中', value: 'active' },
                { label: '已停用', value: 'inactive' },
              ]}
            />
          </Form.Item>
          <Form.Item name="sort_order" label="展示顺序">
            <InputNumber className="field-full" min={0} max={9999} precision={0} />
          </Form.Item>
        </div>
      </Form>
    </Modal>
  )
}
