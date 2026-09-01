import api from '../utils/api'

export function createAIConversation(data = {}) {
  return api.post('/ai/conversations', data)
}

export function getAIConversations(params = {}) {
  return api.get('/ai/conversations', { params })
}

export function getAIMessages(conversationId, params = {}) {
  return api.get(`/ai/conversations/${conversationId}/messages`, { params })
}

export function sendAIMessage(conversationId, data) {
  return api.post(`/ai/conversations/${conversationId}/messages`, data, {
    timeout: 70000,
  })
}

export function uploadAIImage(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/ai/uploads', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    skipErrorHandler: true,
  })
}

export function getImageGeneration(jobId) {
  return api.get(`/ai/image-generations/${jobId}`)
}

export function retryImageGeneration(jobId) {
  return api.post(`/ai/image-generations/${jobId}/retry`)
}

export function regenerateImageGeneration(jobId) {
  return api.post(`/ai/image-generations/${jobId}/regenerate`)
}

export function cancelImageGeneration(jobId) {
  return api.post(`/ai/image-generations/${jobId}/cancel`)
}
