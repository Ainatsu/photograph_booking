import api from '../utils/api'

export function getRecommendedWorks(params = {}) {
  return api.get('/recommendations/works', { params })
}

export function getRecommendedPackages(params = {}) {
  return api.get('/recommendations/packages', { params })
}

export function getRecommendedProjects(params = {}) {
  return api.get('/recommendations/projects', { params })
}

export function trackRecommendationEvents(events) {
  return api.post('/recommendations/events/batch', { events }, { skipErrorHandler: true })
}
