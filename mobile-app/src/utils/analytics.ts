/**
 * 通用分析事件系统
 * 
 * 用于上报用户行为事件，帮助优化推荐和转化漏斗。
 * 仅在上报失败时静默降级，不阻塞业务逻辑。
 */

// 事件类型常量
export const AnalyticsEvent = {
  // 页面浏览
  PAGE_VIEW: 'page_view',
  
  // 交互事件
  BUTTON_CLICK: 'button_click',
  LINK_CLICK: 'link_click',
  TAB_SWITCH: 'tab_switch',
  
  // 表单事件
  FORM_SUBMIT: 'form_submit',
  FORM_SAVE_DRAFT: 'form_save_draft',
  
  // 搜索事件
  SEARCH: 'search',
  
  // 内容事件
  CONTENT_SHARE: 'content_share',
  CONTENT_VIEW: 'content_view',
}

interface AnalyticsPayload {
  event: string
  properties?: Record<string, unknown>
  timestamp?: string
}

// 事件队列 - 批量提交
let eventQueue: AnalyticsPayload[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null

const FLUSH_INTERVAL = 5000  // 5 秒刷新一次
const BATCH_SIZE = 20         // 每批最多 20 条

/**
 * 上报一个分析事件
 */
export function trackEvent(event: string, properties?: Record<string, unknown>): void {
  const payload: AnalyticsPayload = {
    event,
    properties,
    timestamp: new Date().toISOString(),
  }
  
  eventQueue.push(payload)
  scheduleFlush()
}

/**
 * 上报页面浏览事件
 */
export function trackPageView(pageName: string, properties?: Record<string, unknown>): void {
  trackEvent(AnalyticsEvent.PAGE_VIEW, { page_name: pageName, ...properties })
}

/**
 * 上报搜索事件
 */
export function trackSearch(query: string, resultCount: number): void {
  trackEvent(AnalyticsEvent.SEARCH, { query, result_count: resultCount })
}

/**
 * 上报按钮点击事件
 */
export function trackButtonClick(buttonName: string, pageName?: string): void {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: buttonName, page_name: pageName })
}

async function flushEvents(): Promise<void> {
  if (eventQueue.length === 0) return
  
  const events = eventQueue.splice(0, BATCH_SIZE)
  try {
    // 发送到后端的通用事件收集端点
    // 后端可能没有专门的事件收集端点，使用推荐事件端点作为 fallback
    const api = (await import('@/api/client')).default
    await api.post('/recommendations/events/batch', {
      events: events.map(e => ({
        event_type: e.event,
        target_type: 'analytics',
        target_id: '0',
        metadata: e.properties || {},
      })),
    }, { skipErrorHandler: true } as any)
  } catch {
    // 静默降级
  } finally {
    if (eventQueue.length > 0) {
      scheduleFlush()
    }
  }
}

function scheduleFlush(): void {
  if (flushTimer !== null) return
  flushTimer = setTimeout(() => {
    flushTimer = null
    void flushEvents()
  }, FLUSH_INTERVAL)
}

// 页面卸载时尝试刷新事件
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    if (eventQueue.length > 0) {
      // 同步发送剩余事件
      try {
        const beaconEvents = eventQueue.map(e => ({
          event_type: e.event,
          target_type: 'analytics',
          target_id: '0',
          metadata: e.properties || {},
        }))
        navigator.sendBeacon?.('/recommendations/events/batch', 
          JSON.stringify({ events: beaconEvents }))
      } catch { /* noop */ }
    }
  })
}
