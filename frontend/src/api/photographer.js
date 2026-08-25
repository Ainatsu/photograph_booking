import api from '../utils/api'

export function getPhotographerList(params = {}) {
    return api.get('/photographers/profiles', { params })
}

export function getPhotographerDetail(userId) {
    return api.get(`/photographers/profile/${userId}`, { skipErrorHandler: true })
}

export function getPhotographerAvailableSlots(userId, params = {}) {
    return api.get(`/photographers/${userId}/available-slots`, { params })
}

export function getAllWorks(params = {}) {
    return api.get('/photographers/works', { params })
}

export function getAllPackages() {
    return api.get('/photographers/packages')
}

export function getPackageDetail(packageId) {
    return api.get(`/photographers/packages/${packageId}`)
}

export function getWorkDetail(workId) {
    return api.get(`/photographers/works/${workId}`)
}
