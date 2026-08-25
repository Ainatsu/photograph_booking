export type AppTheme = 'light' | 'dark'

const THEME_STORAGE_KEY = 'photographer-booking-theme'

function systemTheme(): AppTheme {
  // SSR 和单元测试环境可能没有 window 或 matchMedia。
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function getStoredTheme(): AppTheme | null {
  if (typeof window === 'undefined') return null
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY)
    // 忽略过期或被手动篡改的值，避免扩大 AppTheme 的合法范围。
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

export function getInitialTheme(): AppTheme {
  return getStoredTheme() || systemTheme()
}

export function applyTheme(theme: AppTheme): AppTheme {
  if (typeof document !== 'undefined') {
    // 同步更新 CSS 选择器、原生控件配色和移动浏览器顶栏颜色。
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      'content',
      theme === 'dark' ? '#000000' : '#F2F2F7',
    )
  }
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // The app still works when storage is unavailable (private browsing/webview).
    }
  }
  return theme
}

export function initializeTheme(): AppTheme {
  return applyTheme(getInitialTheme())
}

export function toggleTheme(theme: AppTheme): AppTheme {
  return applyTheme(theme === 'dark' ? 'light' : 'dark')
}
