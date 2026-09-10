import api from './client'
import type { PackageOffer, WorkItem } from '@/types/discovery'
import type {
  FavoriteListResponse,
  FavoritePackageItem,
  FavoriteWorkItem,
  FollowCounts,
  FollowListResponse,
  FollowToggleResponse,
} from '@/types/social'

export async function getWorkFavoriteStatus(workId: string): Promise<boolean> {
  const { data } = await api.get<Record<string, boolean>>('/favorites/status', {
    params: { ids: workId },
  })
  return Boolean(data[workId])
}

export async function toggleWorkFavorite(
  work: WorkItem,
  photographerId: number,
): Promise<boolean> {
  const { data } = await api.post<{ favorited: boolean }>('/favorites/toggle', {
    work_id: work.id,
    photographer_id: photographerId,
    work_data: { ...work },
  })
  return data.favorited
}

export async function getWorkFavorites(): Promise<FavoriteListResponse<FavoriteWorkItem>> {
  const { data } = await api.get<FavoriteListResponse<FavoriteWorkItem>>('/favorites', {
    params: { skip: 0, limit: 200 },
  })
  return data
}

export async function getPackageFavoriteStatus(packageId: string): Promise<boolean> {
  const { data } = await api.get<Record<string, boolean>>('/favorites/packages/status', {
    params: { ids: packageId },
  })
  return Boolean(data[packageId])
}

export async function togglePackageFavorite(
  offer: PackageOffer,
  photographerId: number,
): Promise<boolean> {
  const { data } = await api.post<{ favorited: boolean }>('/favorites/toggle', {
    package_id: offer.id,
    photographer_id: photographerId,
    package_data: { ...offer },
  })
  return data.favorited
}

export async function getPackageFavorites(): Promise<FavoriteListResponse<FavoritePackageItem>> {
  const { data } = await api.get<FavoriteListResponse<FavoritePackageItem>>('/favorites/packages', {
    params: { skip: 0, limit: 200 },
  })
  return data
}

export async function getFollowStatus(userId: number): Promise<boolean> {
  const { data } = await api.get<{ following: boolean }>(`/follows/status/${userId}`)
  return data.following
}

export async function toggleFollow(userId: number): Promise<FollowToggleResponse> {
  const { data } = await api.post<FollowToggleResponse>(`/follows/toggle/${userId}`)
  return data
}

export async function getFollowCounts(userId: number): Promise<FollowCounts> {
  const { data } = await api.get<FollowCounts>(`/follows/counts/${userId}`)
  return data
}

export async function getFollowing(userId: number): Promise<FollowListResponse> {
  const { data } = await api.get<FollowListResponse>(`/follows/following/${userId}`, {
    params: { skip: 0, limit: 100 },
  })
  return data
}

export async function getFollowers(userId: number): Promise<FollowListResponse> {
  const { data } = await api.get<FollowListResponse>(`/follows/followers/${userId}`, {
    params: { skip: 0, limit: 100 },
  })
  return data
}
