<template>
  <div id="app">
    <el-container class="app-shell">
      <header class="app-header">
        <div class="header-inner">
          <div class="header-left">
            <router-link to="/" class="logo" aria-label="好拍档首页">
              <img src="/tubiao.png" alt="好拍档" class="logo-icon" />
            </router-link>
            <nav class="nav-links" aria-label="主导航">
              <router-link to="/discover" class="nav-link" :class="{ active: route.path === '/discover' }">
                艺术家
              </router-link>
              <router-link to="/works" class="nav-link" :class="{ active: route.path === '/works' || route.path.startsWith('/work/') }">
                作品
              </router-link>
              <router-link to="/packages" class="nav-link" :class="{ active: route.path === '/packages' || route.path.startsWith('/package/') }">
                方案
              </router-link>
              <router-link to="/projects" class="nav-link" :class="{ active: isProjectsNavActive }">
                企划
              </router-link>
            </nav>
            <div class="search-wrapper" :class="{ 'search-expanded': searchExpanded }">
              <button class="search-trigger" @click="expandSearch" aria-label="搜索">
                <el-icon :size="20"><Search /></el-icon>
              </button>
              <el-input
                ref="searchInputRef"
                v-model="searchKeyword"
                placeholder="搜索作品、摄影师、方案或企划"
                class="header-search"
                clearable
                @keyup.enter="doSearch"
                @blur="collapseSearch"
              >
              </el-input>
            </div>
          </div>
          <div class="header-right">
            <template v-if="token">
              <el-avatar
                :size="40"
                :src="avatarSrc"
                class="nav-avatar"
                @click="$router.push('/profile')"
                :aria-label="'个人资料: ' + (displayName || '用户')"
              >
                {{ userNameFirstChar }}
              </el-avatar>
              <div class="nav-actions">
                <el-badge :value="unreadCount" :hidden="!unreadCount" class="msg-badge">
                  <button
                    class="icon-btn"
                    :class="{ active: route.path === '/messages' }"
                    @click="$router.push('/messages')"
                    aria-label="消息"
                  >
                    <el-icon :size="20"><ChatDotSquare /></el-icon>
                  </button>
                </el-badge>
                <el-badge :value="notificationUnreadCount" :hidden="!notificationUnreadCount" class="msg-badge">
                  <button
                    class="icon-btn"
                    :class="{ active: route.path === '/notifications' }"
                    @click="$router.push('/notifications')"
                    aria-label="订单通知"
                  >
                    <el-icon :size="20"><Bell /></el-icon>
                  </button>
                </el-badge>
                <button
                  class="icon-btn"
                  :class="{ active: route.path === '/ai-assistant' }"
                  @click="$router.push('/ai-assistant')"
                  aria-label="AI 助手 小龟J"
                >
                  <el-icon :size="20"><MagicStick /></el-icon>
                </button>
                <button class="icon-btn logout-btn" @click="logout" aria-label="退出登录">
                  <el-icon :size="20"><SwitchButton /></el-icon>
                </button>
              </div>
            </template>
            <template v-else>
              <router-link to="/login" class="nav-link">登录</router-link>
              <router-link to="/register" class="btn btn-primary btn-sm">注册</router-link>
            </template>
          </div>
        </div>
      </header>
      <main class="app-main">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['Packages', 'Gallery', 'Discover', 'Projects']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
      <AIContextEntry :enabled="Boolean(token)" />
      <BackToTop :style="backToTopStyle" />
    </el-container>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, LogOut as SwitchButton, MessageSquare as ChatDotSquare, Search, WandSparkles as MagicStick } from 'lucide-vue-next'
import { getUnreadCount } from './api/message'
import { getNotificationUnreadCount } from './api/notification'
import api from './utils/api'
import AIContextEntry from './components/AIContextEntry.vue'
import BackToTop from './components/BackToTop.vue'

const router = useRouter()
const route = useRoute()
const token = ref(localStorage.getItem('token'))
const unreadCount = ref(0)
const notificationUnreadCount = ref(0)
const avatarUrl = ref('')
const displayName = ref('')
const searchKeyword = ref('')
const searchExpanded = ref(false)
const searchInputRef = ref(null)

let unreadTimer = null

const customBg = ref(localStorage.getItem('custom_bg') || '')

const applyCustomBg = () => {
  customBg.value = localStorage.getItem('custom_bg') || ''
}

const getFullUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return url
}

const avatarSrc = computed(() => getFullUrl(avatarUrl.value))

const isProjectsNavActive = computed(() => (
  route.path.startsWith('/projects')
))

const userNameFirstChar = computed(() => {
  if (displayName.value) return displayName.value[0]
  return '?'
})

const isWorksPage = computed(() => route.path === '/works')

const backToTopStyle = computed(() => ({
  bottom: '40px',
  right: isWorksPage.value ? '106px' : '40px',
}))

const doSearch = () => {
  const q = searchKeyword.value.trim()
  if (!q) return
  router.push(`/works?q=${encodeURIComponent(q)}`)
  collapseSearch()
}

const expandSearch = () => {
  searchExpanded.value = true
  setTimeout(() => {
    searchInputRef.value?.focus()
  }, 100)
}

const collapseSearch = () => {
  if (!searchKeyword.value.trim()) {
    searchExpanded.value = false
  }
}

const fetchUnreadCount = async () => {
  if (!token.value) return
  try {
    const res = await getUnreadCount()
    unreadCount.value = res.data.count
  } catch {}
}

const fetchNotificationUnreadCount = async () => {
  if (!token.value) return
  try {
    const res = await getNotificationUnreadCount()
    notificationUnreadCount.value = res.data.count
  } catch {}
}

const fetchUserInfo = async () => {
  if (!token.value) return
  try {
    const res = await api.get('/users/me')
    avatarUrl.value = res.data.avatar_url || ''
    displayName.value = res.data.display_name || ''
  } catch {}
}

const syncFromStorage = () => {
  const t = localStorage.getItem('token')
  if (t !== token.value) {
    token.value = t
    fetchUnreadCount()
    fetchNotificationUnreadCount()
    if (t) fetchUserInfo()
    return true
  }
  return false
}

const setAuth = (t) => {
  token.value = t
  if (t) {
    localStorage.setItem('token', t)
  } else {
    localStorage.removeItem('token')
  }
}

const logout = () => {
  setAuth(null)
  unreadCount.value = 0
  notificationUnreadCount.value = 0
  avatarUrl.value = ''
  displayName.value = ''
  router.push('/login')
}

onMounted(() => {
  fetchUserInfo()
  fetchUnreadCount()
  fetchNotificationUnreadCount()
  unreadTimer = setInterval(() => {
    fetchUnreadCount()
    fetchNotificationUnreadCount()
  }, 10000)
  window.addEventListener('custom-bg-change', applyCustomBg)
})

onUnmounted(() => {
  clearInterval(unreadTimer)
  window.removeEventListener('custom-bg-change', applyCustomBg)
})

watch(() => route.fullPath, () => {
  const authChanged = syncFromStorage()
  if (!authChanged) fetchUnreadCount()
  if (!authChanged) fetchNotificationUnreadCount()
})
</script>

<style>
/* ============================================================
   全局样式 — E-Ink/Paper
   ============================================================ */

/* 隐藏滚动条但保留滚动功能 */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}

html, body {
  margin: 0;
  padding: 0;
  background: var(--color-paper);
}

#app {
  font-family: var(--font-sans);
  max-width: none;
  margin: 0;
  padding: 0;
  display: block;
  color: var(--color-ink);
}

.app-shell {
  width: 100%;
  min-width: 0;
  min-height: 100vh;
  flex-direction: column;
}

/* --- 导航栏 --- */
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  height: var(--header-height);
  background: var(--color-paper-light);
  border-bottom: var(--border-default);
}

.header-inner {
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 0 var(--content-gutter);
  height: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.header-left {
  min-width: 0;
}

.header-right {
  flex-shrink: 0;
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  text-decoration: none;
  margin-right: var(--space-3);
  flex-shrink: 0;
}

.logo-icon {
  height: 48px;
  width: auto;
  display: block;
}

/* 导航链接 */
.nav-links {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.nav-link {
  display: inline-flex;
  align-items: center;
  min-height: 48px;
  padding: 0 var(--space-4);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-ink-secondary);
  text-decoration: none;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: color 150ms ease, background-color 150ms ease;
  white-space: nowrap;
}

.nav-link:hover {
  color: var(--color-ink);
  background: var(--color-brand-light);
}

.nav-link.active {
  color: var(--color-brand);
  background: var(--color-brand-light);
}

/* 搜索 */
.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  margin-left: var(--space-3);
}

.search-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--tap-target-min);
  height: var(--tap-target-min);
  border: none;
  background: none;
  color: var(--color-ink-secondary);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: color 150ms ease, background-color 150ms ease;
  flex-shrink: 0;
}

.search-trigger:hover {
  color: var(--color-brand);
  background: var(--color-brand-light);
}

.search-wrapper .header-search {
  display: none;
  width: 240px;
}

.search-wrapper.search-expanded .search-trigger {
  display: none;
}

.search-wrapper.search-expanded .header-search {
  display: block;
}

.search-wrapper .header-search .el-input__wrapper {
  border-radius: var(--radius-md);
}

/* 导航操作按钮 */
.nav-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--tap-target-min);
  height: var(--tap-target-min);
  border: none;
  background: none;
  color: var(--color-ink-secondary);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: color 150ms ease, background-color 150ms ease;
}

.icon-btn:hover {
  color: var(--color-ink);
  background: var(--color-brand-light);
}

.icon-btn.active {
  color: var(--color-brand);
}

.logout-btn:hover {
  color: var(--color-danger);
  background: transparent;
}

.nav-avatar {
  cursor: pointer;
  flex-shrink: 0;
}

.msg-badge {
  line-height: 1;
}

/* --- 按钮基类 --- */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 500;
  border: var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
  text-decoration: none;
  min-height: var(--tap-target-min);
  min-width: var(--tap-target-min);
  padding: 0 var(--space-4);
  white-space: nowrap;
}

.btn-primary {
  background: var(--color-brand);
  color: #fff;
  border-color: var(--color-brand);
}

.btn-primary:hover {
  background: var(--color-brand-hover);
  border-color: var(--color-brand-hover);
}

.btn-primary:active {
  background: var(--color-brand-active);
  border-color: var(--color-brand-active);
}

.btn-sm {
  font-size: var(--text-xs);
  min-height: 32px;
  padding: 0 var(--space-3);
}

.header-right .btn-sm {
  min-height: var(--tap-target-min);
  padding: 0 var(--space-4);
  font-size: var(--text-sm);
}

/* --- 主内容区 --- */
.app-main {
  width: 100%;
  min-width: 0;
  flex: 1 0 auto;
  min-height: 100vh;
  padding-top: var(--header-height);
  background: var(--color-paper);
}

/* --- 响应式 --- */
@media (max-width: 900px) {
  .app-shell {
    --header-height: 64px;
  }

  .header-inner {
    padding: 0 var(--space-3);
  }

  .header-left,
  .header-right {
    gap: var(--space-2);
  }

  .nav-links {
    gap: var(--space-1);
  }

  .nav-link {
    padding: 0 var(--space-2);
    font-size: var(--text-sm);
    min-height: 44px;
  }

  .logo-icon {
    height: 38px;
  }

  .logo {
    margin-right: var(--space-1);
  }

  .search-wrapper {
    margin-left: var(--space-1);
  }

  .search-wrapper.search-expanded .header-search {
    width: 180px;
  }

  .nav-actions {
    gap: 0;
  }

  .icon-btn {
    width: 40px;
    height: 40px;
  }
}

@media (max-width: 640px) {
  .header-left {
    overflow-x: auto;
    overscroll-behavior-inline: contain;
    scrollbar-width: none;
  }

  .header-left::-webkit-scrollbar {
    display: none;
  }

  .nav-links,
  .search-wrapper {
    flex-shrink: 0;
  }

  .nav-link {
    padding: 0 var(--space-2);
  }

  .search-wrapper.search-expanded .header-search {
    width: 160px;
  }
}
</style>
