import api from '../utils/api'

export function trackAnalyticsEvent(data) {
  return api.post('/analytics/events', data, { skipErrorHandler: true })
}
