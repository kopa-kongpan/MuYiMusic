import { Alert, Tabs, Tag } from 'antd'
import { ArrowUpRight, BookOpen, Smartphone, Store } from 'lucide-react'
import { Link } from 'react-router-dom'

import { getAdminSession } from './session'

interface GuideItem {
  title: string
  description: string
  steps: string[]
  path?: string
  permission?: string
}

const webItems: GuideItem[] = [
  {
    title: '门店管理',
    description: '维护门店名称、地址、营业信息与启用状态。只有启用的门店会出现在用户的选店列表。',
    steps: ['进入「门店管理」查看或搜索门店', '新增或编辑信息后保存', '核对状态，并在小程序选店页确认展示'],
    path: '/stores',
  },
  {
    title: '首页内容与加盟合作',
    description: '按门店维护首页图片、视频、快捷入口和加盟合作介绍。',
    steps: ['先选择要运营的门店', '编辑内容并设置展示状态或发布时间', '预览首页内容，发布加盟合作页后检查用户端'],
    path: '/store-content',
    permission: 'store_content:manage',
  },
  {
    title: '课程商品与视频课程',
    description: '维护分类、课程商品、价格规格及视频课程课时，面向用户展示前检查商品状态。',
    steps: ['在「课程商品」建立分类与商品规格', '确认价格、图片和商品发布状态', '需要视频教学时，在「视频课程」维护课时与视频'],
    path: '/products',
    permission: 'products:manage',
  },
  {
    title: '排课与预约消课',
    description: '先维护教师和可约排课，再处理预约、到课、缺席与撤销。',
    steps: ['在「排课管理」维护教师与可约时段', '学员预约后到「预约与消课」查看记录', '核实实际到课情况后执行消课或缺席处理'],
    path: '/schedules',
    permission: 'schedules:manage',
  },
  {
    title: '用户、权益与消息',
    description: '按门店查询用户、订单与课程权益；消息投递页用于查看通知状态。',
    steps: ['在「用户与权益」搜索并打开用户详情', '核对订单与可用课时后再调整权益', '如需排查通知，在「消息投递」查看记录与失败原因'],
    path: '/users',
    permission: 'users:read',
  },
  {
    title: '运营账号',
    description: '平台管理员为运营人员分配角色、门店范围和菜单权限。',
    steps: ['进入「运营账号」创建或编辑账号', '按职责分配门店与权限', '让使用者重新登录后核对可见菜单'],
    path: '/admin-accounts',
    permission: 'admins:manage',
  },
]

const miniappItems: GuideItem[] = [
  {
    title: '选店与浏览',
    description: '首次打开时选择门店；可以按门店、城市或地址搜索。允许定位后，可按距离查看有位置数据的门店。',
    steps: ['在「选择门店」搜索或浏览', '点击门店进入首页', '通过首页、课程和加盟合作入口浏览内容'],
  },
  {
    title: '选课与支付',
    description: '在课程详情选择规格并加入购物车；结算前会重新核对商品和价格。支付需在微信小程序内完成。',
    steps: ['进入「课程」打开课程详情', '选择规格和数量，加入购物车', '确认金额后发起微信支付，在「我的订单」查看结果'],
  },
  {
    title: '预约与课程权益',
    description: '有对应课程权益后，可在「预约」选择可约时段；预约与扣课状态可在个人中心查看。',
    steps: ['登录并确认「我的课程」中的可用课时', '在「预约」选择日期和排课', '到「我的预约」查看、按页面规则取消预约'],
  },
  {
    title: '个人中心与视频学习',
    description: '「我的」集中展示订单、课程、预约、消息和教师工作台。视频播放取决于有效课程权益。',
    steps: ['在「我的」完成微信登录', '按需授权绑定手机号', '打开订单、课程、排课或消息查看个人记录'],
  },
  {
    title: '教师工作台',
    description: '教师可使用绑定码关联身份，查看当天预约与消息，并在页面允许时取消学员预约。',
    steps: ['在「我的」进入「教师工作台」', '首次使用时输入管理员提供的绑定码', '选择教师身份，查看当天预约与通知'],
  },
]

function GuideCards({ items }: { items: GuideItem[] }) {
  const permissions = getAdminSession()?.admin.permissions ?? []

  return (
    <div className="guide-grid">
      {items.map((item) => (
        <section className="guide-card" key={item.title}>
          <div className="guide-card-top">
            <h3>{item.title}</h3>
            {item.path && (!item.permission || permissions.includes(item.permission)) ? (
              <Link to={item.path} className="guide-card-link">
                打开功能 <ArrowUpRight size={15} aria-hidden="true" />
              </Link>
            ) : null}
          </div>
          <p>{item.description}</p>
          <ol>
            {item.steps.map((step) => <li key={step}>{step}</li>)}
          </ol>
        </section>
      ))}
    </div>
  )
}

export function GuidePage() {
  return (
    <main className="guide-page">
      <header className="guide-hero">
        <div className="guide-hero-icon"><BookOpen size={26} aria-hidden="true" /></div>
        <div>
          <span className="guide-eyebrow">MuYiMusic · 功能使用说明</span>
          <h1>使用指南</h1>
          <p>按角色找到入口和操作顺序，快速完成门店运营与小程序使用。</p>
        </div>
      </header>

      <Tabs
        className="guide-tabs"
        defaultActiveKey="web"
        items={[
          {
            key: 'web',
            label: <span className="guide-tab-label"><Store size={17} aria-hidden="true" /> Web 运营后台</span>,
            children: (
              <div className="guide-panel">
                <div className="guide-intro">
                  <div>
                    <h2>运营人员从这里开始</h2>
                    <p>登录后台后，建议依次完成门店信息、展示内容、商品与排课，再检查用户端效果。菜单与可管理门店由账号权限决定。</p>
                  </div>
                  <Tag color="green">运营人员</Tag>
                </div>
                <GuideCards items={webItems} />
                <Alert type="info" showIcon message="操作前请核对当前门店。商品、排课和内容通常按门店分别维护。" />
              </div>
            ),
          },
          {
            key: 'miniapp',
            label: <span className="guide-tab-label"><Smartphone size={17} aria-hidden="true" /> 微信小程序</span>,
            children: (
              <div className="guide-panel">
                <div className="guide-intro">
                  <div>
                    <h2>用户与教师使用流程</h2>
                    <p>用户先选店，再浏览和购买课程；拥有课程权益后可预约排课。教师通过个人中心进入工作台。</p>
                  </div>
                  <Tag color="blue">用户与教师</Tag>
                </div>
                <GuideCards items={miniappItems} />
                <Alert type="warning" showIcon message="微信支付、手机号授权和订阅消息依赖小程序版本及微信侧配置；浏览器 H5 不支持微信小程序支付。" />
              </div>
            ),
          },
        ]}
      />
    </main>
  )
}
