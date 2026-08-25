import api from '@/utils/api'

export const getMyPhotographerApplication = () =>
  api.get('/photographer-applications/me', { skipErrorHandler: true })

export const submitPhotographerApplication = (data) =>
  api.post('/photographer-applications/me', data)
