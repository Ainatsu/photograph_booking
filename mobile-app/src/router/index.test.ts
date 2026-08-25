import { describe, expect, it } from 'vitest'
import router from './index'

describe('mobile navigation', () => {
  it('exposes the five requested primary destinations', () => {
    const names = new Set(router.getRoutes().map((route) => route.name))
    expect(names.has('discover')).toBe(true)
    expect(names.has('showcase')).toBe(true)
    expect(names.has('publish')).toBe(true)
    expect(names.has('messages')).toBe(true)
    expect(names.has('profile')).toBe(true)
  })

  it('keeps detail screens deep-linkable', () => {
    const names = new Set(router.getRoutes().map((route) => route.name))
    expect(names.has('work-detail')).toBe(true)
    expect(names.has('photographer-detail')).toBe(true)
    expect(names.has('package-detail')).toBe(true)
    expect(names.has('project-detail')).toBe(true)
    expect(names.has('project-candidates')).toBe(true)
    expect(names.has('project-apply')).toBe(true)
    expect(names.has('work-edit')).toBe(true)
  })

  it('exposes authentication and the first customer transaction routes', () => {
    const names = new Set(router.getRoutes().map((route) => route.name))
    expect(names.has('login')).toBe(true)
    expect(names.has('register')).toBe(true)
    expect(names.has('booking')).toBe(true)
    expect(names.has('orders')).toBe(true)
    expect(names.has('order-detail')).toBe(true)
    expect(names.has('conversation')).toBe(true)
  })

  it('exposes authenticated publishing routes for all three resource types', () => {
    const routes = router.getRoutes()
    const names = new Set(routes.map((route) => route.name))
    expect(names.has('publish-project')).toBe(true)
    expect(names.has('publish-work')).toBe(true)
    expect(names.has('publish-package')).toBe(true)
    expect(routes.find((route) => route.name === 'publish-project')?.meta.requiresAuth).toBe(true)
    expect(routes.find((route) => route.name === 'publish-work')?.meta.requiresAuth).toBe(true)
    expect(routes.find((route) => route.name === 'publish-package')?.meta.requiresAuth).toBe(true)
  })

  it('exposes the authenticated favorites and follows center', () => {
    const route = router.getRoutes().find((item) => item.name === 'social')
    expect(route?.path).toBe('/social')
    expect(route?.meta.requiresAuth).toBe(true)
  })

  it('protects the photographer project-application form', () => {
    const route = router.getRoutes().find((item) => item.name === 'project-apply')
    expect(route?.path).toBe('/projects/:projectId/apply')
    expect(route?.meta.requiresAuth).toBe(true)
  })

  it('exposes authenticated project management and edit routes', () => {
    const management = router.getRoutes().find((item) => item.name === 'project-management')
    const edit = router.getRoutes().find((item) => item.name === 'project-edit')
    const candidates = router.getRoutes().find((item) => item.name === 'project-candidates')
    expect(management?.path).toBe('/projects/manage')
    expect(management?.meta.requiresAuth).toBe(true)
    expect(edit?.path).toBe('/projects/:projectId/edit')
    expect(edit?.meta.requiresAuth).toBe(true)
    expect(candidates?.path).toBe('/projects/:projectId/candidates')
    expect(candidates?.meta.requiresAuth).toBe(true)
  })

  it('protects the work edit route', () => {
    const edit = router.getRoutes().find((item) => item.name === 'work-edit')
    expect(edit?.path).toBe('/works/:workId/edit')
    expect(edit?.meta.requiresAuth).toBe(true)
  })

  it('exposes authenticated package management and edit routes', () => {
    const management = router.getRoutes().find((item) => item.name === 'package-management')
    const edit = router.getRoutes().find((item) => item.name === 'package-edit')
    expect(management?.path).toBe('/packages/manage')
    expect(management?.meta.requiresAuth).toBe(true)
    expect(edit?.path).toBe('/packages/:packageId/edit')
    expect(edit?.meta.requiresAuth).toBe(true)
  })

  it('exposes authenticated photographer availability and service settings', () => {
    const route = router.getRoutes().find((item) => item.name === 'photographer-settings')
    expect(route?.path).toBe('/photographer/settings')
    expect(route?.meta.requiresAuth).toBe(true)
  })

  it('exposes the authenticated photographer application and status page', () => {
    const route = router.getRoutes().find((item) => item.name === 'photographer-application')
    expect(route?.path).toBe('/photographer/application')
    expect(route?.meta.requiresAuth).toBe(true)
  })

  it('protects personal profile and account security settings', () => {
    const route = router.getRoutes().find((item) => item.name === 'account-settings')
    expect(route?.path).toBe('/account/settings')
    expect(route?.meta.requiresAuth).toBe(true)
  })

  it('exposes public read-only content lists for other users', () => {
    const routes = router.getRoutes()
    const works = routes.find((item) => item.name === 'user-works')
    const packages = routes.find((item) => item.name === 'user-packages')
    const projects = routes.find((item) => item.name === 'user-projects')
    expect(works?.path).toBe('/users/:userId/works')
    expect(packages?.path).toBe('/users/:userId/packages')
    expect(projects?.path).toBe('/users/:userId/projects')
    expect(works?.meta.requiresAuth).toBeUndefined()
    expect(packages?.meta.requiresAuth).toBeUndefined()
    expect(projects?.meta.requiresAuth).toBeUndefined()
  })

  it('exposes the authenticated notification center', () => {
    const route = router.getRoutes().find((item) => item.name === 'notifications')
    expect(route?.path).toBe('/notifications')
    expect(route?.meta.requiresAuth).toBe(true)
  })
})
