import api from '../utils/api'

export function getNotifications(params = {}) {
    return api.get('/notifications/', { params })
}

export function getNotificationUnreadCount() {
    return api.get('/notifications/unread-count')
}

export function markNotificationRead(notificationId) {
    return api.put(`/notifications/${notificationId}/read`)
}

export function markAllNotificationsRead() {
    return api.put('/notifications/read-all')
}
