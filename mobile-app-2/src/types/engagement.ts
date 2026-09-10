import type { WorkItem } from '@/types/discovery'

export type EngagementTargetType = 'portfolio' | 'package'

export interface CommentItem {
  id: number
  user_id: number
  user_display_name?: string | null
  user_avatar_url?: string | null
  target_type: EngagementTargetType
  target_id: string
  content: string
  created_at?: string | null
}

export interface CommentListResponse {
  items: CommentItem[]
  total: number
}

export interface LikeSummary {
  liked: boolean
  count: number
}

export interface LikedWorkItem {
  work_id: string
  work_data?: Partial<WorkItem> | null
  photographer_id: number
  photographer_name?: string | null
  photographer_avatar?: string | null
  liked_at?: string | null
}

export interface LikedWorkListResponse {
  items: LikedWorkItem[]
  total: number
}
