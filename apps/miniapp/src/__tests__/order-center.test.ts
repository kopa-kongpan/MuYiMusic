import { beforeEach, describe, expect, it, vi } from 'vitest'

const mock = vi.hoisted(() => ({
  request: vi.fn(),
  readUserSession: vi.fn(),
  clearUserSession: vi.fn(),
}))

vi.mock('@tarojs/taro', () => ({ default: { request: mock.request } }))
vi.mock('../store/user-session', () => ({
  readUserSession: mock.readUserSession,
  clearUserSession: mock.clearUserSession,
  saveUserSession: vi.fn(),
  updateUserSessionProfile: vi.fn(),
}))

describe('微信订单中心查询', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('MUYIMUSIC_API_BASE_URL', 'https://muyimusic.net')
    mock.readUserSession.mockReturnValue({ accessToken: 'test-user-token' })
  })

  it('携带本人身份按微信支付单号查询，不使用当前门店过滤', async () => {
    const { getMyOrder } = await import('../services/user')
    mock.request.mockResolvedValue({
      statusCode: 200,
      data: { order_no: 'O123' },
    })
    await expect(getMyOrder('P123')).resolves.toEqual({ order_no: 'O123' })
    expect(mock.request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: 'https://muyimusic.net/api/v1/app/me/orders/P123',
        header: { Authorization: 'Bearer test-user-token' },
        data: {},
      }),
    )
  })

  it('会话失效时清除登录态并显示服务端提示', async () => {
    const { getMyOrder } = await import('../services/user')
    mock.request.mockResolvedValue({
      statusCode: 401,
      data: { detail: '登录已失效' },
    })
    await expect(getMyOrder('P123')).rejects.toThrow('登录已失效')
    expect(mock.clearUserSession).toHaveBeenCalledOnce()
  })
})
