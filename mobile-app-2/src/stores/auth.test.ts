import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { getCurrentUser, loginAccount } from '@/api/auth'
import type { UserProfile } from '@/types/auth'

vi.mock('@/api/auth', () => ({
  loginAccount: vi.fn(),
  getCurrentUser: vi.fn(),
}))

const loginAccountMock = vi.mocked(loginAccount)
const getCurrentUserMock = vi.mocked(getCurrentUser)

function makeProfile(overrides: Partial<UserProfile> = {}): UserProfile {
  return {
    id: 7,
    display_name: '林一',
    role: 'customer',
    is_active: true,
    ...overrides,
  }
}

beforeEach(() => {
  window.localStorage.clear()
  setActivePinia(createPinia())
  loginAccountMock.mockReset()
  getCurrentUserMock.mockReset()
})

describe('初始状态', () => {
  it('本地没有 token 时视为未登录', () => {
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.user).toBeNull()
  })

  it('本地已有 token 时直接视为已登录，尚未拉取资料', () => {
    window.localStorage.setItem('token', 'stored-token')
    const auth = useAuthStore()

    expect(auth.isAuthenticated).toBe(true)
    expect(auth.user).toBeNull()
  })
})

describe('login', () => {
  it('成功后写入 token、落盘并加载资料', async () => {
    loginAccountMock.mockResolvedValue('fresh-token')
    getCurrentUserMock.mockResolvedValue(makeProfile())

    const auth = useAuthStore()
    const profile = await auth.login('linyi', 'secret')

    expect(loginAccountMock).toHaveBeenCalledWith('linyi', 'secret')
    expect(auth.token).toBe('fresh-token')
    expect(window.localStorage.getItem('token')).toBe('fresh-token')
    expect(profile).toEqual(makeProfile())
    expect(auth.user).toEqual(makeProfile())
  })

  it('拿到 token 但资料拉取失败时清空会话并抛出，不留下不可用的 token', async () => {
    loginAccountMock.mockResolvedValue('bad-token')
    getCurrentUserMock.mockRejectedValue(new Error('401'))

    const auth = useAuthStore()
    await expect(auth.login('linyi', 'secret')).rejects.toThrow('401')

    expect(auth.token).toBe('')
    expect(auth.user).toBeNull()
    expect(window.localStorage.getItem('token')).toBeNull()
  })

  it('登录接口本身失败时不改动已有会话', async () => {
    window.localStorage.setItem('token', 'existing-token')
    loginAccountMock.mockRejectedValue(new Error('bad credentials'))

    const auth = useAuthStore()
    await expect(auth.login('linyi', 'wrong')).rejects.toThrow('bad credentials')

    expect(auth.token).toBe('existing-token')
    expect(window.localStorage.getItem('token')).toBe('existing-token')
  })
})

describe('initialize', () => {
  it('有 token 时恢复会话并拉到资料', async () => {
    window.localStorage.setItem('token', 'stored-token')
    getCurrentUserMock.mockResolvedValue(makeProfile({ role: 'photographer' }))

    const auth = useAuthStore()
    await auth.initialize()

    expect(getCurrentUserMock).toHaveBeenCalledTimes(1)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.isPhotographer).toBe(true)
    expect(auth.initialized).toBe(true)
  })

  it('无 token 时不发请求', async () => {
    const auth = useAuthStore()
    await auth.initialize()

    expect(getCurrentUserMock).not.toHaveBeenCalled()
    expect(auth.initialized).toBe(true)
  })

  it('token 已失效时清空会话，不抛错', async () => {
    window.localStorage.setItem('token', 'expired-token')
    getCurrentUserMock.mockRejectedValue(new Error('401'))

    const auth = useAuthStore()
    await auth.initialize()

    expect(auth.isAuthenticated).toBe(false)
    expect(window.localStorage.getItem('token')).toBeNull()
  })

  it('重复调用只请求一次', async () => {
    window.localStorage.setItem('token', 'stored-token')
    getCurrentUserMock.mockResolvedValue(makeProfile())

    const auth = useAuthStore()
    await auth.initialize()
    await auth.initialize()

    expect(getCurrentUserMock).toHaveBeenCalledTimes(1)
  })
})

describe('角色判定', () => {
  it('role 为 photographer 时 isPhotographer 为真', async () => {
    loginAccountMock.mockResolvedValue('t')
    getCurrentUserMock.mockResolvedValue(makeProfile({ role: 'photographer' }))

    const auth = useAuthStore()
    await auth.login('a', 'b')

    expect(auth.isPhotographer).toBe(true)
  })

  it('客户角色为假', async () => {
    loginAccountMock.mockResolvedValue('t')
    getCurrentUserMock.mockResolvedValue(makeProfile({ role: 'customer' }))

    const auth = useAuthStore()
    await auth.login('a', 'b')

    expect(auth.isPhotographer).toBe(false)
  })
})

describe('logout', () => {
  it('清空 token、资料与本地存储，但保留 initialized 标记', async () => {
    loginAccountMock.mockResolvedValue('t')
    getCurrentUserMock.mockResolvedValue(makeProfile())

    const auth = useAuthStore()
    await auth.login('a', 'b')
    auth.logout()

    expect(auth.isAuthenticated).toBe(false)
    expect(auth.user).toBeNull()
    expect(window.localStorage.getItem('token')).toBeNull()
    expect(auth.initialized).toBe(true)
  })
})
