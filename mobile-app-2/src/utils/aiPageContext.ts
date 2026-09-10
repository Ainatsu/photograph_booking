import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type {
  AIPageContext,
  AIPageContextResourceType,
} from '@/api/ai'
import type { PackageOffer, PhotographerProfile, ProjectBrief, WorkItem } from '@/types/discovery'
import { getPackageName, formatProjectBudget } from '@/utils/format'
import { getWorkPreviewUrl, getPackagePreviewUrl, resolveMediaUrl } from '@/utils/media'

// ── Constants ──

const HANDFOOT_PREFIX = 'ai_page_context_handoff:'
const HANDFOOT_TTL_MS = 10 * 60 * 1000 // 10 minutes

const FIELD_MAX_LENGTH = 800
const SEARCH_TEXT_MAX_LENGTH = 1600
const MAX_TAGS = 8
const MAX_TAG_LENGTH = 80
const MAX_PACKAGE_SUMMARIES = 6
const MAX_PORTFOLIO_SUMMARIES = 6
const MAX_APPLICATION_SUMMARIES = 5

// ── Text / list helpers ──

export function compactContextText(value: unknown, maxLength = FIELD_MAX_LENGTH): string {
  if (value === null || value === undefined) return ''
  const text = String(value).replace(/\s+/g, ' ').trim()
  return text.length > maxLength ? text.slice(0, maxLength) : text
}

export function compactContextList(
  value: unknown,
  limit = MAX_TAGS,
  maxItemLength = MAX_TAG_LENGTH,
): string[] {
  if (!Array.isArray(value)) return []
  const items = value
    .map((v) => compactContextText(v, maxItemLength))
    .filter(Boolean)
  const seen = new Set<string>()
  return items.filter((item) => {
    const lower = item.toLowerCase()
    if (seen.has(lower)) return false
    seen.add(lower)
    return true
  }).slice(0, limit)
}

// ── Builders ──

export function buildWorkPageContext(
  work: WorkItem,
  route: RouteLocationNormalizedLoaded,
): AIPageContext {
  const rawTags = work.tags?.length ? work.tags : work.tag ? splitLegacyTag(work.tag) : []
  const tags = compactContextList(rawTags)
  const tagsProp = tags.length ? tags : undefined

  return pruneEmptyFields({
    route_name: route.name as string || 'work-detail',
    route_path: route.fullPath,
    resource_type: 'portfolio_item' as AIPageContextResourceType,
    resource_id: String(work.id),
    title: compactContextText(work.title || work.tag || '当前作品'),
    description: compactContextText(work.description),
    tags: tagsProp,
    owner_user_id: work.user_id,
    owner_display_name: compactContextText(work.user_display_name),
    photographer_name: compactContextText(work.user_display_name),
    current_object: {
      media_type: work.media_type || 'image',
      image_url: work.media_type === 'video'
        ? undefined
        : resolveMediaUrl(work.images?.[0] || work.url) || undefined,
      thumbnail_url: resolveMediaUrl(work.thumbnail_url) || undefined,
    },
  } as AIPageContext)
}

export function buildPhotographerPageContext(
  profile: PhotographerProfile,
  route: RouteLocationNormalizedLoaded,
): AIPageContext {
  const packages = (profile.packages || [])
    .slice(0, MAX_PACKAGE_SUMMARIES)
    .map((pkg) => ({
      id: pkg.id,
      name: pkg.package_name || pkg.name,
      price: pkg.price,
      image_count: pkg.image_count,
      thumbnail: pkg.sample_thumbnails?.[0] || pkg.samples?.[0],
    }))

  const portfolio = (profile.portfolio || [])
    .slice(0, MAX_PORTFOLIO_SUMMARIES)
    .map((work) => ({
      id: work.id,
      title: work.title || work.tag,
      thumbnail_url: getWorkPreviewUrl(work),
    }))

  return pruneEmptyFields({
    route_name: route.name as string || 'photographer-detail',
    route_path: route.fullPath,
    resource_type: 'photographer' as AIPageContextResourceType,
    resource_id: String(profile.user_id),
    title: compactContextText(profile.user_display_name || '当前摄影师'),
    photographer_id: profile.user_id,
    photographer_name: compactContextText(profile.user_display_name),
    summary: compactContextText(profile.user_bio),
    description: compactContextText(profile.user_bio),
    styles: compactContextList(profile.styles),
    location: compactContextText(profile.location),
    current_object: {
      thumbnail_url: resolveMediaUrl(profile.user_avatar_url || profile.cover_image_url) || undefined,
    },
    packages: packages.length ? packages as unknown as Record<string, unknown>[] : undefined,
    portfolio: portfolio.length ? portfolio as unknown as Record<string, unknown>[] : undefined,
  } as AIPageContext)
}

export function buildPackagePageContext(
  offer: PackageOffer,
  route: RouteLocationNormalizedLoaded,
): AIPageContext {
  const name = getPackageName(offer)

  return pruneEmptyFields({
    route_name: route.name as string || 'package-detail',
    route_path: route.fullPath,
    resource_type: 'package' as AIPageContextResourceType,
    resource_id: String(offer.id),
    title: compactContextText(name, FIELD_MAX_LENGTH) || '当前方案',
    package_name: compactContextText(name),
    description: compactContextText(offer.description),
    styles: compactContextList(offer.styles),
    city: compactContextText(offer.city),
    price: offer.price,
    price_label: compactContextText(`¥${offer.price}`),
    duration: offer.duration,
    image_count: offer.image_count,
    photographer_id: offer.photographer_id,
    photographer_name: compactContextText(offer.photographer_name),
    current_object: {
      thumbnail_url: resolveMediaUrl(offer.sample_thumbnails?.[0] || offer.samples?.[0]) || undefined,
    },
  } as AIPageContext)
}

export function buildProjectPageContext(
  project: ProjectBrief,
  route: RouteLocationNormalizedLoaded,
): AIPageContext {
  return pruneEmptyFields({
    route_name: route.name as string || 'project-detail',
    route_path: route.fullPath,
    resource_type: 'project' as AIPageContextResourceType,
    resource_id: String(project.id),
    title: compactContextText(project.title) || '当前企划',
    description: compactContextText(project.description),
    styles: compactContextList(project.style_tags),
    city: compactContextText(project.city),
    location: compactContextText(project.location_name || project.location_text),
    status: compactContextText(project.status),
    budget_label: formatProjectBudget(project),
    date_label: compactContextText(project.shoot_date_start),
    duration: project.duration_minutes,
    owner_user_id: project.customer_id,
    owner_display_name: compactContextText(project.customer_name),
    current_object: {
      thumbnail_url: resolveMediaUrl(project.reference_images?.[0]) || undefined,
    },
  } as AIPageContext)
}

// ── Handoff (sessionStorage) ──

interface HandoffEntry {
  context: AIPageContext
  createdAt: number
}

export function stageAIPageContext(context: AIPageContext): string {
  const handoffKey = generateHandoffKey()
  const entry: HandoffEntry = { context, createdAt: Date.now() }
  try {
    sessionStorage.setItem(HANDFOOT_PREFIX + handoffKey, JSON.stringify(entry))
  } catch {
    // sessionStorage may be full or unavailable; fall back silently
  }
  return handoffKey
}

export function consumeAIPageContext(handoffKey: string): AIPageContext | null {
  if (!handoffKey) return null
  const key = HANDFOOT_PREFIX + handoffKey
  let raw: string | null
  try {
    raw = sessionStorage.getItem(key)
    sessionStorage.removeItem(key)
  } catch {
    return null
  }
  if (!raw) return null

  let entry: HandoffEntry
  try {
    entry = JSON.parse(raw) as HandoffEntry
  } catch {
    return null
  }

  // Expiry check
  if (!entry.createdAt || Date.now() - entry.createdAt > HANDFOOT_TTL_MS) {
    if (import.meta.env.DEV) {
      console.warn('[aiPageContext] handoff expired or invalid')
    }
    return null
  }

  const ctx = entry.context
  if (!ctx.resource_type || !ctx.resource_id || !ctx.title) {
    if (import.meta.env.DEV) {
      console.warn('[aiPageContext] handoff missing required fields')
    }
    return null
  }

  return ctx
}

// ── Source route helper ──

export function getSourceRoute(context: AIPageContext): { name: string; params: Record<string, string> } | null {
  if (context.route_path && context.route_name) {
    return { name: context.route_name, params: extractParamsFromPath(context.route_path) }
  }
  // Fallback: build route from resource_type + resource_id
  const routeName = resourceRouteName(context.resource_type)
  if (!routeName) return null
  const paramKey = resourceParamKey(context.resource_type)
  return { name: routeName, params: { [paramKey]: context.resource_id } }
}

// ── Private helpers ──

function pruneEmptyFields(ctx: AIPageContext): AIPageContext {
  const result = { ...ctx } as Record<string, unknown>
  for (const [key, value] of Object.entries(result)) {
    if (value === null || value === undefined || value === '') {
      delete result[key]
    }
  }
  // Handle current_object specially
  if (result.current_object && typeof result.current_object === 'object') {
    const co = result.current_object as Record<string, unknown>
    for (const [k, v] of Object.entries(co)) {
      if (v === null || v === undefined || v === '') {
        delete co[k]
      }
    }
    if (Object.keys(co).length === 0) {
      delete result.current_object
    }
  }
  return result as unknown as AIPageContext
}

function generateHandoffKey(): string {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let result = ''
  const array = new Uint8Array(16)
  crypto.getRandomValues(array)
  for (const byte of array) {
    result += chars[byte % chars.length]
  }
  return result
}

function splitLegacyTag(tag?: string): string[] {
  if (!tag) return []
  return tag.split(/[,，\/\s]+/).filter(Boolean).map((t) => t.trim())
}

function resourceRouteName(type: AIPageContextResourceType): string | null {
  const map: Record<AIPageContextResourceType, string> = {
    portfolio_item: 'work-detail',
    photographer: 'photographer-detail',
    package: 'package-detail',
    project: 'project-detail',
  }
  return map[type] || null
}

function resourceParamKey(type: AIPageContextResourceType): string {
  const map: Record<AIPageContextResourceType, string> = {
    portfolio_item: 'workId',
    photographer: 'userId',
    package: 'packageId',
    project: 'projectId',
  }
  return map[type]
}

function extractParamsFromPath(path: string): Record<string, string> {
  // Simple param extraction from paths like /works/:workId
  const segments = path.split('/').filter(Boolean)
  const params: Record<string, string> = {}

  // Try to match known patterns
  if (segments.length >= 2) {
    const resourceType = segments[0]
    const id = segments[1]
    if (resourceType === 'works') params.workId = id
    else if (resourceType === 'photographers') params.userId = id
    else if (resourceType === 'packages') params.packageId = id
    else if (resourceType === 'projects') params.projectId = id
  }

  return params
}
