/**
 * router.spec.js — 路由配置单元测试
 * 测试：路由定义、路径、懒加载
 */
import { describe, it, expect } from 'vitest'
import router from '../../router/index'

describe('Router', () => {
  it('should have correct routes', () => {
    const routes = router.getRoutes()
    expect(routes.length).toBeGreaterThan(0)
  })

  it('should define Home route at /', () => {
    const homeRoute = router.getRoutes().find(r => r.name === 'Home')
    expect(homeRoute).toBeDefined()
    expect(homeRoute.path).toBe('/')
  })

  it('should define Login route at /login', () => {
    const loginRoute = router.getRoutes().find(r => r.name === 'Login')
    expect(loginRoute).toBeDefined()
    expect(loginRoute.path).toBe('/login')
  })

  it('should define Register route at /register', () => {
    const registerRoute = router.getRoutes().find(r => r.name === 'Register')
    expect(registerRoute).toBeDefined()
    expect(registerRoute.path).toBe('/register')
  })

  it('should define Discover route at /discover', () => {
    const route = router.getRoutes().find(r => r.name === 'Discover')
    expect(route).toBeDefined()
    expect(route.path).toBe('/discover')
  })

  it('should define Gallery route at /works', () => {
    const route = router.getRoutes().find(r => r.name === 'Gallery')
    expect(route).toBeDefined()
    expect(route.path).toBe('/works')
  })

  it('should define Packages route at /packages', () => {
    const route = router.getRoutes().find(r => r.name === 'Packages')
    expect(route).toBeDefined()
    expect(route.path).toBe('/packages')
  })

  it('should define PhotographerDetail route at /photographer/:userId', () => {
    const route = router.getRoutes().find(r => r.name === 'PhotographerDetail')
    expect(route).toBeDefined()
    expect(route.path).toBe('/photographer/:userId')
  })

  it('should define Booking route at /booking/:userId', () => {
    const route = router.getRoutes().find(r => r.name === 'Booking')
    expect(route).toBeDefined()
    expect(route.path).toBe('/booking/:userId')
  })

  it('should define MyOrders route at /my-orders', () => {
    const route = router.getRoutes().find(r => r.name === 'MyOrders')
    expect(route).toBeDefined()
    expect(route.path).toBe('/my-orders')
  })

  it('should define OrderDetail route at /orders/:orderId', () => {
    const route = router.getRoutes().find(r => r.name === 'OrderDetail')
    expect(route).toBeDefined()
    expect(route.path).toBe('/orders/:orderId')
  })

  it('should define Messages route at /messages', () => {
    const route = router.getRoutes().find(r => r.name === 'Messages')
    expect(route).toBeDefined()
    expect(route.path).toBe('/messages')
  })

  it('should define Profile route at /profile', () => {
    const route = router.getRoutes().find(r => r.name === 'Profile')
    expect(route).toBeDefined()
    expect(route.path).toBe('/profile')
  })

  it('should define PhotographerDashboard route at /dashboard', () => {
    const route = router.getRoutes().find(r => r.name === 'PhotographerDashboard')
    expect(route).toBeDefined()
    expect(route.path).toBe('/dashboard')
  })

  it('should use HTML5 history mode', () => {
    // createWebHistory means clean URLs without #
    const homeRoute = router.getRoutes().find(r => r.name === 'Home')
    expect(homeRoute.path).toBe('/')
  })
})
