import { createRouter, createWebHistory } from '@ionic/vue-router'
import type { RouteRecordRaw } from 'vue-router'
import TabsLayout from '@/layouts/TabsLayout.vue'

/**
 * 全量路由表 —— 与 PAGES.md §4 逐条对应（41 条）。
 *
 * 已经实现视觉的页面指向真实组件；尚未实现的统一指向 PlaceholderPage，
 * 通过 props 传标题。**不要**把未实现的路径从表里删掉：Vue Router 无匹配时
 * 会渲染空白页，静默吞掉导航，比一个明确的占位页难排查得多。
 *
 * 替换顺序见 PAGES.md §9。
 */
const placeholder = () => () => import('@/pages/PlaceholderPage.vue')

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/tabs/discover',
  },
  {
    path: '/tabs',
    component: TabsLayout,
    children: [
      { path: '', redirect: '/tabs/discover' },
      {
        path: 'discover',
        name: 'discover',
        component: () => import('@/pages/DiscoverPage.vue'),
      },
      {
        path: 'showcase',
        name: 'showcase',
        component: () => import('@/pages/ShowcasePage.vue'),
      },
      // 第三个 Tab 按钮实际打开 PublishActionSheet，不走导航；此路由保留是为了
      // 让直接输入 URL 仍可到达。决定见 PAGES.md §2.1。
      {
        path: 'publish',
        name: 'publish',
        component: () => import('@/pages/PublishPage.vue'),
      },
      {
        path: 'messages',
        name: 'messages',
        component: () => import('@/pages/MessagesPage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/pages/ProfilePage.vue'),
      },
    ],
  },

  // ── 内容与详情 ──
  {
    path: '/works/:workId',
    name: 'work-detail',
    component: () => import('@/pages/WorkDetailPage.vue'),
  },
  {
    path: '/works/:workId/edit',
    name: 'work-edit',
    component: placeholder(),
    props: { title: '编辑作品' },
    meta: { requiresAuth: true },
  },
  {
    path: '/works/gallery',
    name: 'works-gallery',
    component: placeholder(),
    props: { title: '作品图库' },
    meta: { requiresAuth: true },
  },
  {
    path: '/photographers/:userId',
    name: 'photographer-detail',
    component: () => import('@/pages/PhotographerDetailPage.vue'),
  },
  {
    path: '/users/:userId/works',
    name: 'user-works',
    component: placeholder(),
    props: { title: '用户作品' },
  },
  {
    path: '/users/:userId/packages',
    name: 'user-packages',
    component: placeholder(),
    props: { title: '用户方案' },
  },
  {
    path: '/users/:userId/projects',
    name: 'user-projects',
    component: placeholder(),
    props: { title: '用户企划' },
  },
  {
    path: '/packages/:packageId',
    name: 'package-detail',
    component: () => import('@/pages/PackageDetailPage.vue'),
  },
  {
    path: '/projects/:projectId',
    name: 'project-detail',
    component: placeholder(),
    props: { title: '企划详情' },
  },

  // ── 发布与经营 ──
  {
    path: '/publish/work',
    name: 'publish-work',
    component: () => import('@/pages/WorkPublishPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/publish/package',
    name: 'publish-package',
    component: () => import('@/pages/PackagePublishPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/publish/project',
    name: 'publish-project',
    component: () => import('@/pages/ProjectPublishPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/packages/:packageId/edit',
    name: 'package-edit',
    component: () => import('@/pages/PackagePublishPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/packages/manage',
    name: 'package-management',
    component: placeholder(),
    props: { title: '方案管理' },
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/:projectId/edit',
    name: 'project-edit',
    component: () => import('@/pages/ProjectPublishPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/manage',
    name: 'project-management',
    component: placeholder(),
    props: { title: '企划与应邀管理' },
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/:projectId/apply',
    name: 'project-apply',
    component: placeholder(),
    props: { title: '应邀报价' },
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/:projectId/candidates',
    name: 'project-candidates',
    component: placeholder(),
    props: { title: '候选人比较' },
    meta: { requiresAuth: true },
  },
  {
    path: '/photographer/dashboard',
    name: 'photographer-dashboard',
    component: placeholder(),
    props: { title: '摄影师看板' },
    meta: { requiresAuth: true },
  },
  {
    path: '/photographer/settings',
    name: 'photographer-settings',
    component: placeholder(),
    props: { title: '档期与服务能力' },
    meta: { requiresAuth: true },
  },

  // ── 账号与身份 ──
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/pages/RegisterPage.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/account/settings',
    name: 'account-settings',
    component: () => import('@/pages/AccountSettingsPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/photographer/application',
    name: 'photographer-application',
    component: placeholder(),
    props: { title: '摄影师认证' },
    meta: { requiresAuth: true },
  },

  // ── 预约与订单 ──
  {
    path: '/booking/:userId?',
    name: 'booking',
    component: placeholder(),
    props: { title: '预约下单' },
    meta: { requiresAuth: true },
  },
  {
    path: '/orders',
    name: 'orders',
    component: placeholder(),
    props: { title: '订单队列' },
    meta: { requiresAuth: true },
  },
  // path 与 name 受深链契约约束，见 PAGES.md §7
  {
    path: '/orders/:orderId',
    name: 'order-detail',
    component: placeholder(),
    props: { title: '订单详情' },
    meta: { requiresAuth: true },
  },

  // ── 消息与通知 ──
  {
    path: '/messages/:userId',
    name: 'conversation',
    component: placeholder(),
    props: { title: '会话' },
    meta: { requiresAuth: true },
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: placeholder(),
    props: { title: '通知中心' },
    meta: { requiresAuth: true },
  },

  // ── 社交与灵感 ──
  {
    path: '/social',
    name: 'social',
    component: placeholder(),
    props: { title: '关注与粉丝' },
    meta: { requiresAuth: true },
  },
  {
    path: '/inspirations',
    name: 'inspirations',
    component: placeholder(),
    props: { title: '灵感仓库' },
    meta: { requiresAuth: true },
  },
  {
    path: '/inspirations/new',
    name: 'inspiration-new',
    component: placeholder(),
    props: { title: '新建灵感' },
    meta: { requiresAuth: true },
  },
  {
    path: '/inspirations/:inspirationId/edit',
    name: 'inspiration-edit',
    component: placeholder(),
    props: { title: '编辑灵感' },
    meta: { requiresAuth: true },
  },
  {
    path: '/inspirations/:inspirationId',
    name: 'inspiration-detail',
    component: placeholder(),
    props: { title: '灵感详情' },
    meta: { requiresAuth: true },
  },

  // ── 搜索与 AI ──
  {
    path: '/search',
    name: 'search',
    component: () => import('@/pages/SearchResultsPage.vue'),
  },
  {
    path: '/ai/assistant',
    name: 'ai-assistant',
    component: placeholder(),
    props: { title: 'AI 助手' },
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// 权限只在路由层做粗粒度拦截，服务端才是授权的最终依据，见 PAGES.md §5。
router.beforeEach((to) => {
  const hasToken = Boolean(localStorage.getItem('token'))
  if (to.meta.requiresAuth && !hasToken) {
    return {
      name: 'login',
      query: { redirect: to.fullPath },
    }
  }
  if (to.meta.guestOnly && hasToken) return { name: 'profile' }
  return true
})

export default router
