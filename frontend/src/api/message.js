import api from '../utils/api'

export function getContacts() {
    return api.get('/messages/contacts')
}

export function getContact(userId) {
    return api.get(`/messages/contact/${userId}`)
}

export function getConversation(otherUserId, params = {}) {
    return api.get(`/messages/conversation/${otherUserId}`, { params })
}

export function sendMessage(data) {
    return api.post('/messages/', data)
}

export function getUnreadCount() {
    return api.get('/messages/unread-count')
}

export function markRead(otherUserId) {
    return api.put(`/messages/read/${otherUserId}`)
}
