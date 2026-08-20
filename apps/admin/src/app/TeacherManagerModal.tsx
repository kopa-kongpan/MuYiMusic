import type { TeacherRead } from '@muyimusic/api-client'
import { App as AntdApp, Button, Empty, Form, Input, InputNumber, Modal, Switch } from 'antd'
import { KeyRound, Pencil, Plus, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { apiClient } from './api'

interface TeacherFormValues {
  name: string
  specialties: string
  bio: string
  sort_order: number
  is_active: boolean
}

interface TeacherManagerModalProps {
  open: boolean
  storeId: string
  storeName: string
  teachers: TeacherRead[]
  onClose: () => void
  onSaved: () => Promise<void>
}

export function TeacherManagerModal({
  open,
  storeId,
  storeName,
  teachers,
  onClose,
  onSaved,
}: TeacherManagerModalProps) {
  const { message } = AntdApp.useApp()
  const [form] = Form.useForm<TeacherFormValues>()
  const [editingTeacher, setEditingTeacher] = useState<TeacherRead | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  useEffect(() => {
    if (open && !editingTeacher) {
      form.setFieldsValue({
        name: '',
        specialties: '',
        bio: '',
        sort_order: 0,
        is_active: true,
      })
    }
  }, [editingTeacher, form, open])

  function editTeacher(teacher: TeacherRead) {
    setEditingTeacher(teacher)
    form.setFieldsValue({
      name: teacher.name,
      specialties: teacher.specialties,
      bio: teacher.bio,
      sort_order: teacher.sort_order,
      is_active: teacher.is_active,
    })
  }

  function resetEditor() {
    setEditingTeacher(null)
    form.setFieldsValue({
      name: '',
      specialties: '',
      bio: '',
      sort_order: 0,
      is_active: true,
    })
  }

  async function save(values: TeacherFormValues) {
    setIsSaving(true)
    try {
      if (editingTeacher) {
        await apiClient.updateTeacher(storeId, editingTeacher.id, values)
      } else {
        await apiClient.createTeacher(storeId, values)
      }
      await onSaved()
      resetEditor()
      void message.success(editingTeacher ? '教师资料已更新' : '教师已创建')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setIsSaving(false)
    }
  }

  async function toggleTeacher(teacher: TeacherRead, isActive: boolean) {
    setUpdatingId(teacher.id)
    try {
      await apiClient.updateTeacher(storeId, teacher.id, { is_active: isActive })
      await onSaved()
      void message.success(isActive ? '教师已启用' : '教师已停用')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '操作失败')
    } finally {
      setUpdatingId(null)
    }
  }

  async function createBindCode(teacher: TeacherRead) {
    setUpdatingId(teacher.id)
    try {
      const result = await apiClient.createTeacherBindCode(storeId, teacher.id)
      Modal.info({
        title: `${teacher.name} · 教师绑定码`,
        content: (
          <div className="teacher-bind-code">
            <strong>{result.code}</strong>
            <span>
              请教师在小程序“教师工作台”中输入；15 分钟内有效，使用一次后失效。
            </span>
          </div>
        ),
        okText: '知道了',
      })
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '绑定码生成失败')
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <Modal
      open={open}
      width={760}
      title={`教师管理 · ${storeName}`}
      footer={null}
      destroyOnHidden
      onCancel={onClose}
    >
      <Form<TeacherFormValues>
        form={form}
        className="teacher-editor"
        layout="vertical"
        onFinish={(values) => void save(values)}
      >
        <div className="teacher-form-grid">
          <Form.Item
            name="name"
            label="教师姓名"
            rules={[{ required: true, message: '请输入教师姓名' }]}
          >
            <Input maxLength={128} placeholder="例如：林老师" />
          </Form.Item>
          <Form.Item name="specialties" label="擅长方向">
            <Input maxLength={1000} placeholder="例如：钢琴、基础乐理" />
          </Form.Item>
          <Form.Item name="sort_order" label="排序">
            <InputNumber className="field-full" min={0} max={1_000_000} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </div>
        <Form.Item name="bio" label="教师简介">
          <Input.TextArea rows={2} maxLength={4000} showCount />
        </Form.Item>
        <div className="teacher-editor-actions">
          <Button
            type="primary"
            htmlType="submit"
            loading={isSaving}
            icon={
              editingTeacher ? (
                <Pencil size={16} aria-hidden="true" />
              ) : (
                <Plus size={16} aria-hidden="true" />
              )
            }
          >
            {editingTeacher ? '保存修改' : '新增教师'}
          </Button>
          {editingTeacher ? (
            <Button icon={<X size={16} aria-hidden="true" />} onClick={resetEditor}>
              取消编辑
            </Button>
          ) : null}
        </div>
      </Form>

      <div className="teacher-list">
        {teachers.length ? (
          teachers.map((teacher) => (
            <div className="teacher-row" key={teacher.id}>
              <div>
                <strong>{teacher.name}</strong>
                <span>{teacher.specialties || '暂未填写擅长方向'}</span>
              </div>
              <span>排序 {teacher.sort_order}</span>
              <Switch
                size="small"
                checked={teacher.is_active}
                loading={updatingId === teacher.id}
                aria-label={`${teacher.is_active ? '停用' : '启用'}${teacher.name}`}
                onChange={(checked) => void toggleTeacher(teacher, checked)}
              />
              <Button
                type="text"
                icon={<KeyRound size={16} aria-hidden="true" />}
                aria-label={`生成${teacher.name}的绑定码`}
                disabled={!teacher.is_active}
                loading={updatingId === teacher.id}
                onClick={() => void createBindCode(teacher)}
              />
              <Button
                type="text"
                icon={<Pencil size={16} aria-hidden="true" />}
                aria-label={`编辑${teacher.name}`}
                onClick={() => editTeacher(teacher)}
              />
            </div>
          ))
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无教师" />
        )}
      </div>
    </Modal>
  )
}
