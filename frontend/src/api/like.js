import api from '@/utils/api'

export const setLikeState = (targetType, targetId, liked) =>
  api.post('/likes/set', { target_type: targetType, target_id: targetId }, { params: { liked } })

export const getLikeSummary = (targetType, ids) =>
  api.get('/likes/summary', {
    params: { target_type: targetType, ids: ids.join(',') },
    skipErrorHandler: true,
  })

export const getUserLikedWorks = (skip = 0, limit = 60) =>
  api.get('/likes/works', { params: { skip, limit } })
