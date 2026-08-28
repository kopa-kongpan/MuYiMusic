import type { FranchisePageUpdate } from '@muyimusic/api-client'
import { useQuery } from '@tanstack/react-query'
import { Alert, App as AntdApp, Button, Card, Form, Input, Select, Switch } from 'antd'
import { Handshake, Save } from 'lucide-react'
import { useEffect, useState } from 'react'

import { apiClient } from './api'

const { TextArea } = Input

const defaults: FranchisePageUpdate = {
  title: '携手木易音乐，共创音乐教育新未来',
  introduction: '我们期待与认同音乐教育价值的伙伴共同成长。',
  advantages: '成熟的课程体系\n专业的师资培养\n持续的品牌运营支持',
  support_policy: '选址与筹备支持\n课程及教学支持\n运营与市场推广支持',
  application_process: '提交合作意向\n合作顾问沟通\n项目评估\n签约与开店筹备',
  contact_name: '加盟顾问',
  contact_phone: '',
  contact_wechat: null,
  is_published: false,
}

export function FranchisePage() {
  const { message } = AntdApp.useApp()
  const [form] = Form.useForm<FranchisePageUpdate>()
  const [storeId, setStoreId] = useState<string>()
  const [saving, setSaving] = useState(false)
  const storesQuery = useQuery({
    queryKey: ['admin-stores-for-franchise'],
    queryFn: () => apiClient.listAdminStores({ pageSize: 100 }),
  })
  const activeStoreId = storeId ?? storesQuery.data?.items[0]?.id
  const pageQuery = useQuery({
    queryKey: ['admin-franchise', activeStoreId],
    queryFn: () => apiClient.getFranchisePage(activeStoreId!),
    enabled: Boolean(activeStoreId),
  })

  useEffect(() => {
    if (!activeStoreId || pageQuery.isLoading) return
    form.setFieldsValue(pageQuery.data ?? defaults)
  }, [activeStoreId, form, pageQuery.data, pageQuery.isLoading])

  async function save(values: FranchisePageUpdate) {
    if (!activeStoreId) return
    setSaving(true)
    try {
      await apiClient.updateFranchisePage(activeStoreId, values)
      await pageQuery.refetch()
      void message.success(values.is_published ? '加盟合作页面已保存并发布' : '加盟合作页面草稿已保存')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-stack franchise-admin-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow"><Handshake size={15} /> 门店展示</span>
          <h1>加盟合作</h1>
          <p>维护小程序加盟合作页面内容；每个门店可独立配置并发布。</p>
        </div>
        <Select
          className="store-selector"
          loading={storesQuery.isLoading}
          value={activeStoreId}
          placeholder="选择门店"
          options={storesQuery.data?.items.map((store) => ({ value: store.id, label: store.name }))}
          onChange={setStoreId}
        />
      </div>
      {pageQuery.isError ? <Alert type="error" showIcon message="加盟合作内容加载失败" /> : null}
      <Card loading={pageQuery.isLoading}>
        <Form form={form} layout="vertical" initialValues={defaults} onFinish={(values) => void save(values)}>
          <Form.Item name="title" label="页面主标题" rules={[{ required: true, message: '请输入页面主标题' }]}>
            <Input maxLength={128} showCount />
          </Form.Item>
          <Form.Item name="introduction" label="品牌与合作介绍" rules={[{ required: true, message: '请输入合作介绍' }]}>
            <TextArea rows={4} maxLength={5000} showCount />
          </Form.Item>
          <Form.Item name="advantages" label="合作优势" extra="每行一项，小程序中按条目展示" rules={[{ required: true, message: '请输入合作优势' }]}>
            <TextArea rows={5} maxLength={5000} showCount />
          </Form.Item>
          <Form.Item name="support_policy" label="支持政策" extra="每行一项" rules={[{ required: true, message: '请输入支持政策' }]}>
            <TextArea rows={5} maxLength={5000} showCount />
          </Form.Item>
          <Form.Item name="application_process" label="申请流程" extra="每行一个步骤" rules={[{ required: true, message: '请输入申请流程' }]}>
            <TextArea rows={5} maxLength={5000} showCount />
          </Form.Item>
          <div className="franchise-contact-grid">
            <Form.Item name="contact_name" label="联系人" rules={[{ required: true, message: '请输入联系人' }]}><Input maxLength={64} /></Form.Item>
            <Form.Item name="contact_phone" label="联系电话" rules={[{ required: true, message: '请输入联系电话' }]}><Input maxLength={32} /></Form.Item>
            <Form.Item name="contact_wechat" label="联系微信"><Input maxLength={64} /></Form.Item>
          </div>
          <Form.Item name="is_published" label="发布状态" valuePropName="checked"><Switch checkedChildren="已发布" unCheckedChildren="草稿" /></Form.Item>
          <Button type="primary" htmlType="submit" loading={saving} icon={<Save size={16} />}>保存加盟合作页面</Button>
        </Form>
      </Card>
    </div>
  )
}
