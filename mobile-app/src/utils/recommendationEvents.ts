import { trackRecommendationEvents, type RecommendationEvent } from '@/api/recommendations'

// 事件名沿用页面里的实体名（project_click），但落库的 target_type 与 Web 端保持一致（shoot_project）
const TARGET_TYPES: Record<string, string> = {
  project: 'shoot_project',
}

export interface TrackOptions {
  position?: number
  scene?: string
  // 缺省时后端会退化成当前登录用户，未登录的曝光/点击会被丢弃
  ownerUserId?: number
}

function buildEvent(
  entity: string,
  action: 'impression' | 'click',
  targetId: number | string,
  options: TrackOptions,
): RecommendationEvent {
  // 统一构造曝光与点击事件，确保两者使用相同的后端分类和归因字段。
  return {
    event_type: `${entity}_${action}`,
    target_type: TARGET_TYPES[entity] || entity,
    target_id: String(targetId),
    owner_user_id: options.ownerUserId,
    position: options.position,
    scene: options.scene,
  }
}

// 记录曝光事件
export function trackImpression(entity: string, targetId: number | string, options: TrackOptions = {}) {
  trackRecommendationEvents([buildEvent(entity, 'impression', targetId, options)])
}

// 记录点击事件
export function trackClick(entity: string, targetId: number | string, options: TrackOptions = {}) {
  trackRecommendationEvents([buildEvent(entity, 'click', targetId, options)])
}

// 批量记录多个事件
export function trackBatchEvents(events: RecommendationEvent[]) {
  trackRecommendationEvents(events)
}
