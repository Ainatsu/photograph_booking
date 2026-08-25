import api from '@/utils/api'

export const toggleFollow = (userId) =>
  api.post(`/follows/toggle/${userId}`)

export const getFollowStatus = (userId) =>
  api.get(`/follows/status/${userId}`)

export const getFollowCounts = (userId) =>
  api.get(`/follows/counts/${userId}`)

export const getFollowers = (userId, params = {}) =>
  api.get(`/follows/followers/${userId}`, { params })

export const getFollowing = (userId, params = {}) =>
  api.get(`/follows/following/${userId}`, { params })