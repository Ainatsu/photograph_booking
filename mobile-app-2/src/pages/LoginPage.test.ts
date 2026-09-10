import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginPage from './LoginPage.vue'
import { getCurrentUser, loginAccount } from '@/api/auth'

vi.mock('@/api/auth', () => ({
  loginAccount: vi.fn(),
  getCurrentUser: vi.fn(),
}))

const loginAccountMock = vi.mocked(loginAccount)
const getCurrentUserMock = vi.mocked(getCurrentUser)

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: { template: '<div />' } },
      { path: '/register', name: 'register', component: { template: '<div />' } },
      { path: '/tabs/profile', name: 'profile', component: { template: '<div />' } },
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
    ],
  })
}

async function mountLogin(initialPath = '/login') {
  const router = makeRouter()
  await router.push(initialPath)
  await router.isReady()

  const wrapper = mount(LoginPage, {
    global: {
      plugins: [router],
      // Ionic 容器组件在 jsdom 里没有真实布局，stub 掉后仍会渲染默认插槽内容
      stubs: {
        DetailHeader: true,
        IonPage: true,
        'ion-page': true,
        IonContent: true,
        'ion-content': true,
        IonSpinner: true,
        'ion-spinner': true,
      },
    },
  })

  return { wrapper, router }
}

beforeEach(() => {
  window.localStorage.clear()
  setActivePinia(createPinia())
  loginAccountMock.mockReset()
  getCurrentUserMock.mockReset()
})

describe('字段校验', () => {
  /**
   * submit() 里是 `!validateAccount() || !validatePassword()`，短路求值：
   * 账号为空时密码校验根本不会执行。这是参照实现的既有行为，属于"换皮不改行为"的范围，
   * 所以用测试把它钉住，而不是顺手"修好"。
   */
  it('账号与密码都为空时提交，先只报账号错误且不发请求', async () => {
    const { wrapper } = await mountLogin()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('.field-error').map((node) => node.text()))
      .toEqual(['请输入用户名、邮箱或手机号。'])
    expect(loginAccountMock).not.toHaveBeenCalled()
  })

  it('补上账号后再次提交，才报出密码错误', async () => {
    const { wrapper } = await mountLogin()

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await wrapper.get('#login-account').setValue('linyi')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('.field-error').map((node) => node.text()))
      .toEqual(['请输入密码。'])
    expect(loginAccountMock).not.toHaveBeenCalled()
  })

  it('失焦时即刻校验单个字段', async () => {
    const { wrapper } = await mountLogin()

    await wrapper.get('#login-password').setValue('secret')
    await wrapper.get('#login-password').trigger('blur')
    await flushPromises()

    expect(wrapper.findAll('.field-error')).toHaveLength(0)

    await wrapper.get('#login-account').trigger('blur')
    await flushPromises()

    expect(wrapper.findAll('.field-error').map((node) => node.text()))
      .toEqual(['请输入用户名、邮箱或手机号。'])
  })

  it('只填账号时只报密码错误', async () => {
    const { wrapper } = await mountLogin()

    await wrapper.get('#login-account').setValue('linyi')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const errors = wrapper.findAll('.field-error').map((node) => node.text())
    expect(errors).toEqual(['请输入密码。'])
  })

  it('账号只有空白字符时按未填写处理', async () => {
    const { wrapper } = await mountLogin()

    await wrapper.get('#login-account').setValue('   ')
    await wrapper.get('#login-password').setValue('secret')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('.field-error').map((node) => node.text()))
      .toContain('请输入用户名、邮箱或手机号。')
    expect(loginAccountMock).not.toHaveBeenCalled()
  })

  it('校验错误标记在对应字段上，供屏幕阅读器关联', async () => {
    const { wrapper } = await mountLogin()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const account = wrapper.get('#login-account')
    expect(account.attributes('aria-invalid')).toBe('true')
    expect(account.attributes('aria-describedby')).toBe('login-account-error')
  })
})

describe('提交', () => {
  it('成功后跳转到 redirect 指定的站内路径', async () => {
    loginAccountMock.mockResolvedValue('fresh-token')
    getCurrentUserMock.mockResolvedValue({
      id: 1,
      display_name: '林一',
      role: 'customer',
      is_active: true,
    })

    const { wrapper, router } = await mountLogin('/login?redirect=%2Forders')

    await wrapper.get('#login-account').setValue('linyi')
    await wrapper.get('#login-password').setValue('secret')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(loginAccountMock).toHaveBeenCalledWith('linyi', 'secret')
    expect(router.currentRoute.value.path).toBe('/orders')
  })

  it('没有 redirect 时回落到我的页面', async () => {
    loginAccountMock.mockResolvedValue('fresh-token')
    getCurrentUserMock.mockResolvedValue({
      id: 1,
      display_name: '林一',
      role: 'customer',
      is_active: true,
    })

    const { wrapper, router } = await mountLogin()

    await wrapper.get('#login-account').setValue('linyi')
    await wrapper.get('#login-password').setValue('secret')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/tabs/profile')
  })

  it('拒绝协议相对地址，避免开放跳转', async () => {
    loginAccountMock.mockResolvedValue('fresh-token')
    getCurrentUserMock.mockResolvedValue({
      id: 1,
      display_name: '林一',
      role: 'customer',
      is_active: true,
    })

    const { wrapper, router } = await mountLogin('/login?redirect=%2F%2Fevil.example')

    await wrapper.get('#login-account').setValue('linyi')
    await wrapper.get('#login-password').setValue('secret')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/tabs/profile')
  })

  it('登录失败时展示错误文案且不跳转', async () => {
    loginAccountMock.mockRejectedValue(new Error('账号或密码不正确'))

    const { wrapper, router } = await mountLogin()

    await wrapper.get('#login-account').setValue('linyi')
    await wrapper.get('#login-password').setValue('wrong')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('.request-error').text()).toContain('账号或密码不正确')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('提交过程中按钮禁用并显示进行中文案', async () => {
    let release: (value: string) => void = () => undefined
    loginAccountMock.mockReturnValue(new Promise<string>((resolve) => {
      release = resolve
    }))

    const { wrapper } = await mountLogin()

    await wrapper.get('#login-account').setValue('linyi')
    await wrapper.get('#login-password').setValue('secret')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const button = wrapper.get('.submit-button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toContain('登录中')

    release('fresh-token')
    getCurrentUserMock.mockRejectedValue(new Error('fail'))
    await flushPromises()
  })
})

describe('密码可见性', () => {
  it('默认隐藏，点击后变为明文并更新无障碍名称', async () => {
    const { wrapper } = await mountLogin()

    const password = wrapper.get('#login-password')
    expect(password.attributes('type')).toBe('password')
    expect(wrapper.get('.password-toggle').attributes('aria-label')).toBe('显示密码')

    await wrapper.get('.password-toggle').trigger('click')

    expect(wrapper.get('#login-password').attributes('type')).toBe('text')
    expect(wrapper.get('.password-toggle').attributes('aria-label')).toBe('隐藏密码')
  })
})
