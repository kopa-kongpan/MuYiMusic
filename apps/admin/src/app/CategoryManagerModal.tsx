import type { CategoryRead } from '@muyimusic/api-client'
import { App as AntdApp, Button, Input, InputNumber, Modal, Switch, Tooltip } from 'antd'
import { ArrowDown, ArrowUp, Check, Pencil, Plus, X } from 'lucide-react'
import { useState } from 'react'

import { apiClient } from './api'

interface CategoryManagerModalProps {
  open: boolean
  storeId: string
  storeName: string
  categories: CategoryRead[]
  onClose: () => void
  onSaved: () => Promise<void>
}

interface CategoryDraft {
  name: string
  sortOrder: number
}

export function CategoryManagerModal({
  open,
  storeId,
  storeName,
  categories,
  onClose,
  onSaved,
}: CategoryManagerModalProps) {
  const { message } = AntdApp.useApp()
  const [draft, setDraft] = useState<CategoryDraft>({ name: '', sortOrder: 0 })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  const [savingId, setSavingId] = useState<string | null>(null)

  async function createCategory() {
    const name = draft.name.trim()
    if (!name) {
      void message.warning('请输入分类名称')
      return
    }
    setSavingId('new')
    try {
      await apiClient.createCategory(storeId, {
        name,
        sort_order: draft.sortOrder,
        is_enabled: true,
      })
      setDraft({ name: '', sortOrder: 0 })
      await onSaved()
      void message.success('分类已创建')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '创建失败')
    } finally {
      setSavingId(null)
    }
  }

  async function saveName(category: CategoryRead) {
    const name = editingName.trim()
    if (!name) {
      void message.warning('分类名称不能为空')
      return
    }
    setSavingId(category.id)
    try {
      await apiClient.updateCategory(storeId, category.id, { name })
      setEditingId(null)
      await onSaved()
      void message.success('分类已更新')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '更新失败')
    } finally {
      setSavingId(null)
    }
  }

  async function toggleCategory(category: CategoryRead, isEnabled: boolean) {
    setSavingId(category.id)
    try {
      await apiClient.updateCategory(storeId, category.id, {
        is_enabled: isEnabled,
      })
      await onSaved()
      void message.success(isEnabled ? '分类已启用' : '分类已停用')
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '操作失败')
    } finally {
      setSavingId(null)
    }
  }

  async function moveCategory(index: number, direction: -1 | 1) {
    const targetIndex = index + direction
    if (targetIndex < 0 || targetIndex >= categories.length) {
      return
    }
    const reordered = [...categories]
    const [moved] = reordered.splice(index, 1)
    if (!moved) {
      return
    }
    reordered.splice(targetIndex, 0, moved)
    setSavingId(moved.id)
    try {
      await apiClient.reorderCategories(storeId, {
        items: reordered.map((category, itemIndex) => ({
          id: category.id,
          sort_order: (itemIndex + 1) * 10,
        })),
      })
      await onSaved()
    } catch (error) {
      void message.error(error instanceof Error ? error.message : '排序失败')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <Modal
      open={open}
      title={`课程分类 · ${storeName}`}
      width={680}
      footer={null}
      destroyOnHidden
      onCancel={onClose}
      afterOpenChange={(isOpen) => {
        if (isOpen) {
          setEditingId(null)
          setDraft({ name: '', sortOrder: 0 })
        }
      }}
    >
      <div className="category-create-row">
        <Input
          value={draft.name}
          maxLength={64}
          placeholder="新分类名称"
          onChange={(event) =>
            setDraft((current) => ({ ...current, name: event.target.value }))
          }
          onPressEnter={() => void createCategory()}
        />
        <InputNumber
          value={draft.sortOrder}
          min={0}
          max={9999}
          aria-label="新分类顺序"
          onChange={(value) =>
            setDraft((current) => ({ ...current, sortOrder: value ?? 0 }))
          }
        />
        <Button
          type="primary"
          loading={savingId === 'new'}
          icon={<Plus size={17} aria-hidden="true" />}
          onClick={() => void createCategory()}
        >
          新建
        </Button>
      </div>

      <div className="category-list">
        {categories.length === 0 ? (
          <div className="category-empty">暂无分类</div>
        ) : (
          categories.map((category, index) => (
            <div className="category-row" key={category.id}>
              <div className="category-order-actions">
                <Tooltip title="上移">
                  <Button
                    type="text"
                    size="small"
                    disabled={index === 0}
                    icon={<ArrowUp size={16} aria-hidden="true" />}
                    aria-label={`上移${category.name}`}
                    onClick={() => void moveCategory(index, -1)}
                  />
                </Tooltip>
                <Tooltip title="下移">
                  <Button
                    type="text"
                    size="small"
                    disabled={index === categories.length - 1}
                    icon={<ArrowDown size={16} aria-hidden="true" />}
                    aria-label={`下移${category.name}`}
                    onClick={() => void moveCategory(index, 1)}
                  />
                </Tooltip>
              </div>
              {editingId === category.id ? (
                <Input
                  autoFocus
                  value={editingName}
                  maxLength={64}
                  onChange={(event) => setEditingName(event.target.value)}
                  onPressEnter={() => void saveName(category)}
                />
              ) : (
                <div className="category-name">
                  <strong>{category.name}</strong>
                  <span>顺序 {category.sort_order}</span>
                </div>
              )}
              <Switch
                size="small"
                checked={category.is_enabled}
                loading={savingId === category.id}
                aria-label={`${category.is_enabled ? '停用' : '启用'}${category.name}`}
                onChange={(checked) => void toggleCategory(category, checked)}
              />
              {editingId === category.id ? (
                <div className="table-actions">
                  <Tooltip title="保存">
                    <Button
                      type="text"
                      icon={<Check size={17} aria-hidden="true" />}
                      aria-label={`保存${category.name}`}
                      onClick={() => void saveName(category)}
                    />
                  </Tooltip>
                  <Tooltip title="取消">
                    <Button
                      type="text"
                      icon={<X size={17} aria-hidden="true" />}
                      aria-label="取消编辑"
                      onClick={() => setEditingId(null)}
                    />
                  </Tooltip>
                </div>
              ) : (
                <Tooltip title="修改名称">
                  <Button
                    type="text"
                    icon={<Pencil size={17} aria-hidden="true" />}
                    aria-label={`编辑${category.name}`}
                    onClick={() => {
                      setEditingId(category.id)
                      setEditingName(category.name)
                    }}
                  />
                </Tooltip>
              )}
            </div>
          ))
        )}
      </div>
    </Modal>
  )
}
