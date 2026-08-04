import type { ContentBlockRead, StoreRead } from '@muyimusic/api-client'
import { Drawer, Empty, Image, Tag } from 'antd'
import { ExternalLink, ImageIcon, Video } from 'lucide-react'

interface ContentPreviewDrawerProps {
  open: boolean
  store: StoreRead | null
  content: ContentBlockRead | null
  onClose: () => void
}

function formatTime(value: string | null): string {
  if (!value) {
    return '不限'
  }
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function ContentPreviewDrawer({
  open,
  store,
  content,
  onClose,
}: ContentPreviewDrawerProps) {
  return (
    <Drawer
      open={open}
      width={440}
      title="内容预览"
      destroyOnHidden
      onClose={onClose}
    >
      {content ? (
        <div className="content-preview">
          <div className="preview-store-line">
            <span>{store?.name}</span>
            <Tag color={content.status === 'enabled' ? 'success' : 'default'}>
              {content.status === 'enabled' ? '已启用' : '已停用'}
            </Tag>
          </div>

          <div className="preview-media">
            {content.block_type === 'image' && content.media_url ? (
              <Image src={content.media_url} alt={content.title} />
            ) : null}
            {content.block_type === 'video' && content.media_url ? (
              <video src={content.media_url} controls preload="metadata" />
            ) : null}
            {content.block_type !== 'shortcut' && !content.media_url ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="媒体暂不可预览"
              />
            ) : null}
            {content.block_type === 'shortcut' ? (
              <div className="shortcut-preview">
                <ExternalLink size={24} aria-hidden="true" />
                <strong>{content.title}</strong>
                <span>{content.jump_target}</span>
              </div>
            ) : null}
          </div>

          <dl className="preview-details">
            <div>
              <dt>标题</dt>
              <dd>{content.title}</dd>
            </div>
            <div>
              <dt>类型</dt>
              <dd>
                {content.block_type === 'image' ? (
                  <ImageIcon size={15} aria-hidden="true" />
                ) : content.block_type === 'video' ? (
                  <Video size={15} aria-hidden="true" />
                ) : (
                  <ExternalLink size={15} aria-hidden="true" />
                )}
                {content.block_type === 'image'
                  ? '图片'
                  : content.block_type === 'video'
                    ? '视频'
                    : '快捷入口'}
              </dd>
            </div>
            <div>
              <dt>展示时间</dt>
              <dd>
                {formatTime(content.starts_at)} 至 {formatTime(content.ends_at)}
              </dd>
            </div>
            <div>
              <dt>排序</dt>
              <dd>{content.sort_order}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </Drawer>
  )
}
