import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import {
    readWindowScrollPosition,
    rememberRouteScrollPosition,
    resolveRouteScrollPosition,
    shouldRetainRouteScroll,
} from './scrollRestoration'

const routes = [
    {
        path: '/',
        name: 'Home',
        component: Home,
    },
    {
        path: '/discover',
        name: 'Discover',
        component: () => import('../views/Discover.vue'), },
    {
        path: '/works',
        name: 'Gallery',
        component: () => import('../views/Gallery.vue'),
    },
    {
        path: '/packages',
        name: 'Packages',
        component: () => import('../views/Packages.vue'),
    },
    {
        path: '/projects',
        name: 'Projects',
        component: () => import('../views/Projects.vue'),
    },
    {
        path: '/projects/new',
        name: 'ProjectCreate',
        component: () => import('../views/ProjectCreate.vue'),
    },
    {
        path: '/projects/:projectId/edit',
        name: 'ProjectEdit',
        component: () => import('../views/ProjectCreate.vue'),
    },
    {
        path: '/projects/:projectId',
        name: 'ProjectDetail',
        component: () => import('../views/ProjectDetail.vue'),
    },
    {
        path: '/projects/:projectId/apply',
        name: 'ProjectApply',
        component: () => import('../views/ProjectApply.vue'),
    },
    {
        path: '/my-projects',
        name: 'MyProjects',
        component: () => import('../views/MyProjects.vue'),
    },
    {
        path: '/my-applications',
        name: 'MyApplications',
        component: () => import('../views/MyApplications.vue'),
    },
    {
        path: '/package/:packageId',
        name: 'PackageDetail',
        component: () => import('../views/PackageDetail.vue'),
    },
    {
        path: '/my-packages',
        name: 'MyPackages',
        component: () => import('../views/MyPackages.vue'),
    },
    {
        path: '/packages/new',
        name: 'PackageCreate',
        component: () => import('../views/PackageCreate.vue'),
    },
    {
        path: '/work/:workId',
        name: 'WorkDetail',
        component: () => import('../views/WorkDetail.vue'),
    },
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/Login.vue'),
    },
    {
        path: '/register',
        name: 'Register',
        component: () => import('../views/Register.vue'),
    },
    {
        path: '/photographer/:userId',
        name: 'PhotographerDetail',
        component: () => import('../views/PhotographerDetail.vue'),
    },
    {
        path: '/booking/:userId',
        name: 'Booking',
        component: () => import('../views/Booking.vue'),
    },
    {
        path: '/my-orders',
        name: 'MyOrders',
        component: () => import('../views/MyOrders.vue'),
    },
    {
        path: '/orders/:orderId',
        name: 'OrderDetail',
        component: () => import('../views/OrderDetail.vue'),
    },
    {
        path: '/messages',
        name: 'Messages',
        component: () => import('../views/Messages.vue'),
    },
    {
        path: '/notifications',
        name: 'Notifications',
        component: () => import('../views/Notifications.vue'),
    },
    {
        path: '/ai-assistant',
        name: 'AIAssistant',
        component: () => import('../views/AIAssistant.vue'),
    },
    {
        path: '/profile',
        name: 'Profile',
        component: () => import('../views/Profile.vue'),
    },
    {
        path: '/favorites',
        name: 'Favorites',
        component: () => import('../views/Favorites.vue'),
    },
    {
        path: '/dashboard',
        name: 'PhotographerDashboard',
        component: () => import('../views/PhotographerDashboard.vue'),
    },
    {
        path: '/upload-work',
        name: 'UploadWork',
        component: () => import('../views/UploadWork.vue'),
    },
    {
        path: '/follow-list/:userId',
        name: 'FollowList',
        component: () => import('../views/FollowList.vue'),
    },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
    scrollBehavior(to, _from, savedPosition) {
        return resolveRouteScrollPosition(to, savedPosition) || { top: 0, left: 0, behavior: 'auto' }
    },
})

router.beforeEach((_to, from) => {
    if (shouldRetainRouteScroll(from)) {
        rememberRouteScrollPosition(from, readWindowScrollPosition())
    }
})

export default router
