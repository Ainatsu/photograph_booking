const retainedRouteNames = new Set(['Discover', 'Gallery', 'Packages', 'Projects'])
const routeScrollPositions = new Map()

const getRouteKey = (route) => route?.fullPath || route?.path || ''

const normalizePosition = (position) => ({
  left: Math.max(0, Number(position?.left) || 0),
  top: Math.max(0, Number(position?.top) || 0),
  behavior: 'auto',
})

export const shouldRetainRouteScroll = (route) => retainedRouteNames.has(route?.name)

export const readWindowScrollPosition = () => {
  if (typeof window === 'undefined') return { left: 0, top: 0 }
  return {
    left: window.scrollX || document.documentElement?.scrollLeft || document.body?.scrollLeft || 0,
    top: window.scrollY || document.documentElement?.scrollTop || document.body?.scrollTop || 0,
  }
}

export const rememberRouteScrollPosition = (route, position = readWindowScrollPosition()) => {
  if (!shouldRetainRouteScroll(route)) return
  const key = getRouteKey(route)
  if (!key) return
  routeScrollPositions.set(key, normalizePosition(position))
}

export const resolveRouteScrollPosition = (route, savedPosition) => {
  if (shouldRetainRouteScroll(route)) {
    const cachedPosition = routeScrollPositions.get(getRouteKey(route))
    if (cachedPosition) return cachedPosition
  }
  return savedPosition ? normalizePosition(savedPosition) : null
}

export const clearRouteScrollPositions = () => routeScrollPositions.clear()
