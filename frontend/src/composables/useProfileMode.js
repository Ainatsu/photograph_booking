import { ref } from 'vue'

export const PROFILE_MODE_CHANGE_EVENT = 'profile-mode-change'

const DEFAULT_MODE = 'customer'
const STORAGE_PREFIX = 'profileMode'
const VALID_MODES = new Set(['customer', 'photographer'])

const profileMode = ref(DEFAULT_MODE)
const activeUserId = ref(null)

export const normalizeProfileMode = (mode) => (VALID_MODES.has(mode) ? mode : DEFAULT_MODE)

const getStorageKey = (userId = activeUserId.value) => {
  return userId ? `${STORAGE_PREFIX}:${userId}` : STORAGE_PREFIX
}

const readStoredProfileMode = (userId = activeUserId.value) => {
  if (typeof localStorage === 'undefined') return ''
  const stored = localStorage.getItem(getStorageKey(userId))
  return VALID_MODES.has(stored) ? stored : ''
}

const persistProfileMode = (mode, userId = activeUserId.value) => {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(getStorageKey(userId), normalizeProfileMode(mode))
}

const notifyProfileModeChange = (mode) => {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return
  window.dispatchEvent(new CustomEvent(PROFILE_MODE_CHANGE_EVENT, { detail: { mode } }))
}

export const initProfileMode = ({ userId, role } = {}) => {
  activeUserId.value = userId || null
  const nextMode = readStoredProfileMode(activeUserId.value) || normalizeProfileMode(role)
  profileMode.value = nextMode
  return nextMode
}

export const setProfileMode = (mode) => {
  const nextMode = normalizeProfileMode(mode)
  profileMode.value = nextMode
  persistProfileMode(nextMode)
  notifyProfileModeChange(nextMode)
}

export const useProfileMode = () => ({
  profileMode,
  initProfileMode,
  setProfileMode,
  normalizeProfileMode,
})
