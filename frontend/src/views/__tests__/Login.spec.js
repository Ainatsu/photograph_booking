import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import Login from '../../views/Login.vue'

const { mockPost } = vi.hoisted(() => ({ mockPost: vi.fn(() => Promise.resolve({ data: { access_token: 'test-token' } })) }))
vi.mock('../../utils/api', () => ({ default: { post: (...args) => mockPost(...args) } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

describe('Login', () => {
  beforeEach(() => vi.clearAllMocks())
  const mountLogin = () => mount(Login, { global: { stubs: {
    'el-form': { template: '<form><slot /></form>' },
    'el-form-item': { template: '<div><slot /></div>' },
    'el-input': { template: '<input />', props: ['modelValue', 'type', 'placeholder'] },
    'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
    'router-link': { template: '<a><slot /></a>' },
  } } })

  it('shows one account field and password field', () => {
    const wrapper = mountLogin()
    expect(wrapper.findAll('input').length).toBe(2)
    expect(wrapper.text()).toContain('用户名、已验证邮箱或已验证手机号')
  })

  it('renders register link and login action', () => {
    const wrapper = mountLogin()
    expect(wrapper.find('a').exists()).toBe(true)
    expect(wrapper.text()).toContain('登录')
  })
})
