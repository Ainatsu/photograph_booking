import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getCurrentUser, loginAccount, registerAccount } from '@/api/auth'
import type { RegisterPayload, UserProfile } from '@/types/auth'

/**
 * 会话状态。token 由这里独占读写，页面不得直接碰 localStorage。
 * 写法遵循 CODE.md §3.1：ref 存响应式状态，非响应式标记用普通变量。
 */
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

  async function loadCurrentUser(): Promise<UserProfile | null> {
    if (!token.value) {
      user.value = null
      return null
    }
    user.value = await getCurrentUser()
    return user.value
  }

  /**
   * 恢复会话：用已有 token 拉一次资料。应用挂载前 await 一次，
   * 页面不要重复调用（重复调用会直接返回，见下）。
   */
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
      // 拿到 token 却读不到资料，说明这个 token 不可用，不能留在本地。
      clearSession()
      throw error
    }
  }

  function logout() {
    clearSession()
  }

  /** 注册成功后直接用同一套凭据登录，省掉用户再输一次。 */
  async function register(payload: RegisterPayload) {
    await registerAccount(payload)
    return login(payload.username, payload.password)
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
