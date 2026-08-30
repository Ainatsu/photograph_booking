import { createRouter, createWebHistory } from '@ionic/vue-router'
import type { RouteRecordRaw } from 'vue-router'
import TabsLayout from '@/layouts/TabsLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/tabs/discover',
  },
  {
    path: '/tabs',
    component: TabsLayout,
    children: [
      {
        path: '',
        redirect: '/tabs/discover',
      },
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
  {
    path: '/works/:workId',
    name: 'work-detail',
    component: () => import('@/pages/WorkDetailPage.vue'),
  },
  {
    path: '/works/:workId/edit',
    name: 'work-edit',
    component: () => import('@/pages/WorkEditPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/works/gallery',
    name: 'works-gallery',
    component: () => import('@/pages/WorksGalleryPage.vue'),
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
    component: () => import('@/pages/UserWorksPage.vue'),
  },
  {
    path: '/users/:userId/packages',
    name: 'user-packages',
    component: () => import('@/pages/UserPackagesPage.vue'),
  },
  {
    path: '/users/:userId/projects',
    name: 'user-projects',
    component: () => import('@/pages/UserProjectsPage.vue'),
  },
  {
    path: '/photographer/dashboard',
    name: 'photographer-dashboard',
    component: () => import('@/pages/PhotographerDashboardPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/photographer/settings',
    name: 'photographer-settings',
    component: () => import('@/pages/PhotographerSettingsPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/photographer/application',
    name: 'photographer-application',
    component: () => import('@/pages/PhotographerApplicationPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/account/settings',
    name: 'account-settings',
    component: () => import('@/pages/AccountSettingsPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/packages/manage',
    name: 'package-management',
    component: () => import('@/pages/PackageManagementPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/packages/:packageId/edit',
    name: 'package-edit',
    component: () => import('@/pages/PackagePublishPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/packages/:packageId',
    name: 'package-detail',
    component: () => import('@/pages/PackageDetailPage.vue'),
  },
  {
    path: '/projects/manage',
    name: 'project-management',
    component: () => import('@/pages/ProjectManagementPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/:projectId',
    name: 'project-detail',
    component: () => import('@/pages/ProjectDetailPage.vue'),
  },
  {
    path: '/projects/:projectId/edit',
    name: 'project-edit',
    component: () => import('@/pages/ProjectPublishPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/:projectId/candidates',
    name: 'project-candidates',
    component: () => import('@/pages/ProjectCandidatesPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/:projectId/apply',
    name: 'project-apply',
    component: () => import('@/pages/ProjectApplyPage.vue'),
    meta: { requiresAuth: true },
  },
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
    path: '/booking/:userId?',
    name: 'booking',
    component: () => import('@/pages/BookingPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/orders',
    name: 'orders',
    component: () => import('@/pages/OrdersPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/orders/:orderId',
    name: 'order-detail',
    component: () => import('@/pages/OrderDetailPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('@/pages/NotificationsPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/messages/:userId',
    name: 'conversation',
    component: () => import('@/pages/ConversationPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/publish/project',
    name: 'publish-project',
    component: () => import('@/pages/ProjectPublishPage.vue'),
    meta: { requiresAuth: true },
  },
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
    path: '/ai/assistant',
    name: 'ai-assistant',
    component: () => import('@/pages/AIAssistantPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/pages/SearchResultsPage.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/social',
    name: 'social',
    component: () => import('@/pages/SocialPage.vue'),
    meta: { requiresAuth: true },
  },
  { path: '/inspirations', name: 'inspirations', component: () => import('@/pages/InspirationsPage.vue'), meta: { requiresAuth: true } },
  { path: '/inspirations/new', name: 'inspiration-new', component: () => import('@/pages/InspirationEditPage.vue'), meta: { requiresAuth: true } },
  { path: '/inspirations/:inspirationId/edit', name: 'inspiration-edit', component: () => import('@/pages/InspirationEditPage.vue'), meta: { requiresAuth: true } },
  { path: '/inspirations/:inspirationId', name: 'inspiration-detail', component: () => import('@/pages/InspirationDetailPage.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

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
