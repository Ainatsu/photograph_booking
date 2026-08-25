/**
 * test-setup.js — 前端测试全局配置
 * 模拟浏览器环境和 Element Plus
 */
import { vi } from 'vitest'

// Mock Element Plus (避免元素加载问题)
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  ElMessageBox: {
    confirm: vi.fn(() => Promise.resolve()),
    alert: vi.fn(() => Promise.resolve()),
  },
}))

// Mock localStorage
const store = {}
global.localStorage = {
  getItem: vi.fn((key) => store[key] || null),
  setItem: vi.fn((key, value) => { store[key] = value }),
  removeItem: vi.fn((key) => { delete store[key] }),
  clear: vi.fn(() => { for (const k in store) delete store[k] }),
}

// Mock router
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRouter: () => ({
      push: vi.fn(),
      replace: vi.fn(),
      go: vi.fn(),
      back: vi.fn(),
    }),
    useRoute: () => ({
      path: '/',
      params: {},
      query: {},
    }),
  }
})

// Suppress Vue warnings in tests
global.console.warn = vi.fn()
