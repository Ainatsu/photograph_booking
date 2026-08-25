import api from '../utils/api'

export function getProjects(params = {}) {
  return api.get('/projects/', { params })
}

export function createProject(data) {
  return api.post('/projects/', data)
}

export function getMyProjects(params = {}) {
  return api.get('/projects/my', { params })
}

export function getProjectDetail(projectId) {
  return api.get(`/projects/${projectId}`)
}

export function updateProject(projectId, data) {
  return api.put(`/projects/${projectId}`, data)
}

export function publishProject(projectId) {
  return api.put(`/projects/${projectId}/publish`)
}

export function closeProject(projectId, reason = '') {
  return api.put(`/projects/${projectId}/close`, { reason })
}

export function getProjectApplications(projectId) {
  return api.get(`/projects/${projectId}/applications`)
}

export function applyProject(projectId, data) {
  return api.post(`/projects/${projectId}/applications`, data)
}

export function updateMyApplication(projectId, data) {
  return api.put(`/projects/${projectId}/applications/me`, data)
}

export function withdrawMyApplication(projectId) {
  return api.put(`/projects/${projectId}/applications/me/withdraw`)
}

export function selectProjectApplication(projectId, applicationId) {
  return api.post(`/projects/${projectId}/applications/${applicationId}/select`)
}

export function getMyApplications(params = {}) {
  return api.get('/projects/my-applications', { params })
}
