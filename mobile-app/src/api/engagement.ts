import api from './client'
import type {
  CommentItem,
  CommentListResponse,
  EngagementTargetType,
  LikedWorkListResponse,
  LikeSummary,
} from '@/types/engagement'

export async function getBatchLikeCounts(
  targetType: EngagementTargetType,
  ids: string[],
): Promise<Record<string, number>> {
  if (!ids.length) return {}
  const { data } = await api.get<Record<string, number>>('/likes/count', {
    params: { target_type: targetType, ids: ids.join(',') },
  })
  return data
}

export async function getLikeSummary(
  targetType: EngagementTargetType,
  targetId: string,
): Promise<LikeSummary> {
  const { data } = await api.get<{ items?: Record<string, LikeSummary> }>('/likes/summary', {
    params: { target_type: targetType, ids: targetId },
  })
  return data.items?.[targetId] || { liked: false, count: 0 }
}

export async function toggleLike(
  targetType: EngagementTargetType,
  targetId: string,
): Promise<LikeSummary> {
  const { data } = await api.post<LikeSummary>('/likes/toggle', {
    target_type: targetType,
    target_id: targetId,
  })
  return data
}

export async function getComments(
  targetType: EngagementTargetType,
  targetId: string,
  skip = 0,
  limit = 20,
): Promise<CommentListResponse> {
  const { data } = await api.get<CommentListResponse>('/comments', {
    params: { target_type: targetType, target_id: targetId, skip, limit },
  })
  return data
}

export async function createComment(
  targetType: EngagementTargetType,
  targetId: string,
  content: string,
): Promise<CommentItem> {
  const { data } = await api.post<CommentItem>('/comments', {
    target_type: targetType,
    target_id: targetId,
    content,
  })
  return data
}

export async function getLikedWorks(): Promise<LikedWorkListResponse> {
  const { data } = await api.get<LikedWorkListResponse>('/likes/works', {
    params: { skip: 0, limit: 200 },
  })
  return data
}
