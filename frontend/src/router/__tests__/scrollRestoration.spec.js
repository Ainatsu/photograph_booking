import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearRouteScrollPositions,
  rememberRouteScrollPosition,
  resolveRouteScrollPosition,
  shouldRetainRouteScroll,
} from '../scrollRestoration'

const galleryRoute = { name: 'Gallery', path: '/works', fullPath: '/works' }

describe('scroll restoration', () => {
  beforeEach(() => {
    clearRouteScrollPositions()
  })

  it('remembers scroll positions for discovery pages', () => {
    rememberRouteScrollPosition(galleryRoute, { left: 12, top: 860 })

    expect(resolveRouteScrollPosition(galleryRoute)).toEqual({
      left: 12,
      top: 860,
      behavior: 'auto',
    })
  })

  it('keeps positions separate for different query states', () => {
    const searchRoute = { ...galleryRoute, fullPath: '/works?q=portrait' }
    rememberRouteScrollPosition(galleryRoute, { top: 420 })
    rememberRouteScrollPosition(searchRoute, { top: 1080 })

    expect(resolveRouteScrollPosition(galleryRoute)?.top).toBe(420)
    expect(resolveRouteScrollPosition(searchRoute)?.top).toBe(1080)
  })

  it('prefers the cached page position when browser history reports the top', () => {
    rememberRouteScrollPosition(galleryRoute, { top: 420 })

    expect(resolveRouteScrollPosition(galleryRoute, { left: 0, top: 1260 })).toEqual({
      left: 0,
      top: 420,
      behavior: 'auto',
    })
  })

  it('uses browser history when no page position has been cached', () => {
    expect(resolveRouteScrollPosition(galleryRoute, { left: 0, top: 1260 })).toEqual({
      left: 0,
      top: 1260,
      behavior: 'auto',
    })
  })

  it('does not retain ordinary detail pages', () => {
    const detailRoute = { name: 'WorkDetail', path: '/work/1', fullPath: '/work/1' }

    expect(shouldRetainRouteScroll(detailRoute)).toBe(false)
    expect(resolveRouteScrollPosition(detailRoute)).toBeNull()
  })
})
