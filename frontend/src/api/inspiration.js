import api from '../utils/api'

export const getInspirations = (params = {}) => api.get('/inspirations/', { params })
export const getInspirationMap = (params = {}) => api.get('/inspirations/map', { params })
export const getInspiration = (id) => api.get(`/inspirations/${id}`)
export const createInspiration = (data) => api.post('/inspirations/', data)
export const updateInspiration = (id, data) => api.put(`/inspirations/${id}`, data)
export const deleteInspiration = (id) => api.delete(`/inspirations/${id}`)

export const uploadInspirationImage = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/inspirations/upload-images', form, { headers: { 'Content-Type': 'multipart/form-data' } })
}
