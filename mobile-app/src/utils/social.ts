import type { PackageOffer, WorkItem } from '@/types/discovery'
import type { LikedWorkItem } from '@/types/engagement'
import type { FavoritePackageItem, FavoriteWorkItem } from '@/types/social'

function socialWorkToWork(item: FavoriteWorkItem | LikedWorkItem): WorkItem {
  const snapshot = item.work_data || {}
  return {
    ...snapshot,
    id: item.work_id,
    photographer_id: item.photographer_id,
    user_id: snapshot.user_id || item.photographer_id,
    user_display_name: snapshot.user_display_name || item.photographer_name,
    user_avatar_url: snapshot.user_avatar_url || item.photographer_avatar,
  }
}

export function favoriteWorkToWork(item: FavoriteWorkItem): WorkItem {
  return socialWorkToWork(item)
}

export function likedWorkToWork(item: LikedWorkItem): WorkItem {
  return socialWorkToWork(item)
}

export function favoritePackageToOffer(item: FavoritePackageItem): PackageOffer {
  const snapshot = item.package_data || {}
  const price = Number(snapshot.price || 0)
  return {
    ...snapshot,
    id: item.package_id,
    price: Number.isFinite(price) ? price : 0,
    photographer_id: item.photographer_id,
    photographer_name: snapshot.photographer_name || item.photographer_name,
    photographer_avatar: snapshot.photographer_avatar || item.photographer_avatar,
  }
}
