import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { applyTheme, getInitialTheme, getStoredTheme, toggleTheme } from './theme'

const THEME_KEY = 'photographer-booking-theme'

function mockSystemTheme(dark: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: dark && query.includes('dark'),
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }))
}

function removeSystemThemeSupport() {
  vi.stubGlobal('matchMedia', undefined)
}

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  document.querySelector('meta[name="theme-color"]')?.remove()
  const meta = document.createElement('meta')
  meta.setAttribute('name', 'theme-color')
  meta.setAttribute('content', '#FFFFFF')
  document.head.appendChild(meta)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('getStoredTheme', () => {
  it('没有存储值时返回 null', () => {
    expect(getStoredTheme()).toBeNull()
  })

  it('存储了合法值时原样返回', () => {
    window.localStorage.setItem(THEME_KEY, 'dark')
    expect(getStoredTheme()).toBe('dark')
  })

  it('存储值被篡改时忽略它，返回 null', () => {
    window.localStorage.setItem(THEME_KEY, 'solarized')
    expect(getStoredTheme()).toBeNull()
  })
})

describe('getInitialTheme', () => {
  it('没有存储值时跟随系统深色偏好', () => {
    mockSystemTheme(true)
    expect(getInitialTheme()).toBe('dark')
  })

  it('没有存储值且系统为浅色时返回浅色', () => {
    mockSystemTheme(false)
    expect(getInitialTheme()).toBe('light')
  })

  it('存储值优先于系统偏好', () => {
    mockSystemTheme(true)
    window.localStorage.setItem(THEME_KEY, 'light')
    expect(getInitialTheme()).toBe('light')
  })

  it('环境不支持 matchMedia 时回退到浅色，不抛错', () => {
    removeSystemThemeSupport()
    expect(getInitialTheme()).toBe('light')
  })
})

describe('applyTheme', () => {
  it('写入 data-theme 与原生控件配色，并持久化', () => {
    applyTheme('dark')

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(window.localStorage.getItem(THEME_KEY)).toBe('dark')
  })

  it('同步更新移动浏览器顶栏颜色', () => {
    applyTheme('dark')
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute('content')).toBe('#000000')

    applyTheme('light')
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute('content')).toBe('#FFFFFF')
  })

  it('返回传入的主题，便于调用方链式使用', () => {
    expect(applyTheme('light')).toBe('light')
  })
})

describe('toggleTheme', () => {
  it('在明暗之间来回切换', () => {
    expect(toggleTheme('light')).toBe('dark')
    expect(toggleTheme('dark')).toBe('light')
  })

  it('切换结果会落盘', () => {
    toggleTheme('light')
    expect(getStoredTheme()).toBe('dark')
  })
})
