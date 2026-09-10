import type { PackageOffer, WorkItem } from '@/types/discovery'

export interface FavoriteWorkItem {
  work_id: string
  work_data?: Partial<WorkItem> | null
  photographer_id: number
  photographer_name?: string | null
  photographer_avatar?: string | null
  created_at?: string | null
}

export interface FavoritePackageItem {
  package_id: string
  package_data?: Partial<PackageOffer> | null
  photographer_id: number
  photographer_name?: string | null
  photographer_avatar?: string | null
  created_at?: string | null
}

export interface FavoriteListResponse<T> {
  items: T[]
  total: number
}

export interface FollowListItem {
  user_id: number
  display_name?: string | null
  avatar_url?: string | null
  bio?: string | null
  role?: string | null
  is_followed: boolean
  followed_at?: string | null
}

export interface FollowListResponse {
  items: FollowListItem[]
  total: number
}

export interface FollowCounts {
  follower_count: number
  following_count: number
}

export interface FollowToggleResponse extends FollowCounts {
  following: boolean
}
