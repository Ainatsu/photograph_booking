import { afterEach, describe, expect, it, vi } from 'vitest'

import { applyTheme, getInitialTheme, toggleTheme } from './theme'

describe('theme preferences', () => {
  afterEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.removeAttribute('style')
    vi.unstubAllGlobals()
  })

  it('prefers a stored theme over the system preference', () => {
    window.localStorage.setItem('photographer-booking-theme', 'light')
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })))

    expect(getInitialTheme()).toBe('light')
  })

  it('applies and persists a selected theme', () => {
    applyTheme('light')

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(window.localStorage.getItem('photographer-booking-theme')).toBe('light')
  })

  it('toggles between dark and light', () => {
    expect(toggleTheme('dark')).toBe('light')
    expect(toggleTheme('light')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
