import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import Register from '../../views/Register.vue'

const { mockPost, mockRequest, mockConfirm, mockAvailability } = vi.hoisted(() => ({
  mockPost: vi.fn(() => Promise.resolve({ data: {} })),
  mockRequest: vi.fn(() => Promise.resolve({ data: { challenge_id: 'challenge-1' } })),
  mockConfirm: vi.fn(() => Promise.resolve({ data: { verification_token: 'verification-token' } })),
  mockAvailability: vi.fn(() => Promise.resolve({ data: { available: true } })),
}))

vi.mock('../../utils/api', () => ({ default: { post: (...args) => mockPost(...args) } }))
vi.mock('../../api/auth', () => ({ default: {
  requestVerification: (...args) => mockRequest(...args),
  confirmVerification: (...args) => mockConfirm(...args),
  checkUsernameAvailability: (...args) => mockAvailability(...args),
} }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

describe('Register', () => {
  beforeEach(() => vi.clearAllMocks())
  const mountRegister = () => mount(Register, { global: { stubs: {
    'el-form': { template: '<form><slot /></form>' },
    'el-form-item': { template: '<div><slot /></div>' },
    'el-input': { template: '<input />', props: ['modelValue', 'type', 'placeholder'] },
    'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
    'router-link': { template: '<a><slot /></a>' },
  } } })

  it('keeps phone verification optional until a phone is entered', () => {
    const wrapper = mountRegister()
    expect(wrapper.findAll('input').length).toBe(5)
    expect(wrapper.text()).toContain('邮箱与手机号可稍后绑定')
    expect(wrapper.text()).not.toContain('短信验证码')
  })

  it('renders login link and registration action', () => {
    const wrapper = mountRegister()
    expect(wrapper.find('a').exists()).toBe(true)
    expect(wrapper.text()).toContain('注册')
  })
})
