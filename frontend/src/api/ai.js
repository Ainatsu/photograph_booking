import api from '../utils/api'

export function createAIConversation(data = {}) {
  return api.post('/ai/conversations', data)
}

export function getAIConversations(params = {}) {
  return api.get('/ai/conversations', { params })
}

export function searchAIConversations(params = {}) {
  return api.get('/ai/conversations/search', { params })
}

export function forkAIConversation(conversationId, data = {}) {
  return api.post(`/ai/conversations/${conversationId}/fork`, data)
}

export function getAIConversationFolders() {
  return api.get('/ai/conversation-folders')
}

export function createAIConversationFolder(data) {
  return api.post('/ai/conversation-folders', data)
}

export function setAIConversationFolder(conversationId, folderId = null) {
  return api.post(`/ai/conversations/${conversationId}/folder`, null, { params: { folder_id: folderId } })
}

export function updateAIConversation(conversationId, data) {
  return api.patch(`/ai/conversations/${conversationId}`, data)
}

export function getAIConversationToolPolicy(conversationId) {
  return api.get(`/ai/conversations/${conversationId}/tool-policy`)
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
