import api from '@/utils/api'

// 作品收藏
export const toggleFavorite = (workId, photographerId, workData) =>
  api.post('/favorites/toggle', {
    work_id: workId,
    photographer_id: photographerId,
    work_data: workData,
  })

export const getUserFavorites = (skip = 0, limit = 60) =>
  api.get('/favorites', { params: { skip, limit } })

export const getBatchFavoriteStatus = (ids) =>
  api.get('/favorites/status', {
    params: { ids: ids.join(',') },
    skipErrorHandler: true,
  })

// 方案收藏
export const togglePackageFavorite = (packageId, photographerId, packageData) =>
  api.post('/favorites/toggle', {
    package_id: packageId,
    photographer_id: photographerId,
    package_data: packageData,
  })

export const getUserPackageFavorites = (skip = 0, limit = 60) =>
  api.get('/favorites/packages', { params: { skip, limit } })

export const getBatchPackageFavoriteStatus = (ids) =>
  api.get('/favorites/packages/status', {
    params: { ids: ids.join(',') },
    skipErrorHandler: true,
  })
