import api from '../utils/api'

export const requestVerification = (payload) =>
  api.post('/auth/verifications/request', payload)

export const confirmVerification = (payload) =>
  api.post('/auth/verifications/confirm', payload)

export const checkUsernameAvailability = (username) =>
  api.get('/users/username-availability', { params: { username } })

export default {
  requestVerification,
  confirmVerification,
  checkUsernameAvailability,
}
