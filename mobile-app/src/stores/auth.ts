import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getCurrentUser,
  loginAccount,
  registerAccount,
} from '@/api/auth'
import type { RegisterPayload, UserProfile } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<UserProfile | null>(null)
  const initializing = ref(false)
  const initialized = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))
  const isPhotographer = computed(() => user.value?.role === 'photographer')

  function setToken(nextToken: string) {
    token.value = nextToken
    if (nextToken) localStorage.setItem('token', nextToken)
    else localStorage.removeItem('token')
  }

  function clearSession() {
    setToken('')
    user.value = null
    initialized.value = true
  }

  function setUser(nextUser: UserProfile | null) {
    user.value = nextUser
  }

  async function loadCurrentUser() {
    if (!token.value) {
      user.value = null
      return null
    }
    user.value = await getCurrentUser()
    return user.value
  }

  async function initialize() {
    if (initialized.value || initializing.value) return
    initializing.value = true
    try {
      await loadCurrentUser()
    } catch {
      clearSession()
    } finally {
      initializing.value = false
      initialized.value = true
    }
  }

  async function login(identifier: string, password: string) {
    const accessToken = await loginAccount(identifier, password)
    setToken(accessToken)
    try {
      return await loadCurrentUser()
    } catch (error) {
      clearSession()
      throw error
    }
  }

  async function register(payload: RegisterPayload) {
    await registerAccount(payload)
    return login(payload.username, payload.password)
  }

  function logout() {
    clearSession()
  }

  return {
    token,
    user,
    initializing,
    initialized,
    isAuthenticated,
    isPhotographer,
    setToken,
    setUser,
    clearSession,
    loadCurrentUser,
    initialize,
    login,
    register,
    logout,
  }
})
