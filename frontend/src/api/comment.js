import api from '@/utils/api'

export const getComments = (targetType, targetId, skip = 0, limit = 20) =>
  api.get('/comments', {
    params: {
      target_type: targetType,
      target_id: targetId,
      skip,
      limit,
    },
    skipErrorHandler: true,
  })

export const createComment = (targetType, targetId, content) =>
  api.post('/comments', {
    target_type: targetType,
    target_id: targetId,
    content,
  })
