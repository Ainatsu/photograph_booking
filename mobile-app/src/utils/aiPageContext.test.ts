import { describe, expect, it, beforeEach } from 'vitest'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type { PackageOffer, PhotographerProfile, ProjectBrief, WorkItem } from '@/types/discovery'
import {
  buildWorkPageContext,
  buildPhotographerPageContext,
  buildPackagePageContext,
  buildProjectPageContext,
  stageAIPageContext,
  consumeAIPageContext,
  compactContextText,
  compactContextList,
} from './aiPageContext'

// ── Mock route ──

function mockRoute(name: string, path: string): RouteLocationNormalizedLoaded {
  return {
    name,
    fullPath: path,
    path,
    query: {},
    params: {},
    hash: '',
    matched: [],
    redirectedFrom: undefined,
    meta: {},
  } as unknown as RouteLocationNormalizedLoaded
}

// ── Compact helpers ──

describe('compactContextText', () => {
  it('trims and collapses whitespace', () => {
    expect(compactContextText('  hello   world  ')).toBe('hello world')
  })

  it('handles null/undefined', () => {
    expect(compactContextText(null)).toBe('')
    expect(compactContextText(undefined)).toBe('')
  })

  it('respects maxLength', () => {
    const long = 'a'.repeat(1000)
    expect(compactContextText(long, 10)).toBe('a'.repeat(10))
  })
})

describe('compactContextList', () => {
  it('filters empty, deduplicates, and limits', () => {
    const input = ['a', ' b ', '', 'a', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
    expect(compactContextList(input, 5)).toEqual(['a', 'b', 'c', 'd', 'e'])
  })

  it('handles non-array values', () => {
    expect(compactContextList(null)).toEqual([])
    expect(compactContextList('string')).toEqual([])
  })
})

// ── Work builder ──

describe('buildWorkPageContext', () => {
  const route = mockRoute('work-detail', '/works/abc123')

  it('produces correct resource_type and string ID', () => {
    const work: WorkItem = { id: '123', title: 'Test Work', user_id: 1 }
    const ctx = buildWorkPageContext(work, route)
    expect(ctx.resource_type).toBe('portfolio_item')
    expect(ctx.resource_id).toBe('123')
  })

  it('maps legacy tag to tags array', () => {
    const work: WorkItem = { id: '1', tag: '人像, 街拍/纪实', user_id: 1 }
    const ctx = buildWorkPageContext(work, route)
    expect(ctx.tags).toBeDefined()
    expect(ctx.tags!.length).toBeGreaterThanOrEqual(2)
    expect(ctx.tags).toContain('人像')
    expect(ctx.tags).toContain('街拍')
  })

  it('uses existing tags array when present', () => {
    const work: WorkItem = { id: '1', tags: ['人像', '风景'], user_id: 1 }
    const ctx = buildWorkPageContext(work, route)
    expect(ctx.tags).toEqual(['人像', '风景'])
  })

  it('includes route_name and route_path', () => {
    const work: WorkItem = { id: '1', title: 'W', user_id: 1 }
    const ctx = buildWorkPageContext(work, route)
    expect(ctx.route_name).toBe('work-detail')
    expect(ctx.route_path).toBe('/works/abc123')
  })

  it('does not include video URL as image in current_object', () => {
    const work: WorkItem = {
      id: '1', title: 'Vid', media_type: 'video',
      url: 'https://example.com/vid.mp4', user_id: 1,
    }
    const ctx = buildWorkPageContext(work, route)
    expect(ctx.current_object?.image_url).toBeUndefined()
    expect(ctx.current_object?.media_type).toBe('video')
  })
})

// ── Photographer builder ──

describe('buildPhotographerPageContext', () => {
  const route = mockRoute('photographer-detail', '/photographers/42')

  const minimalProfile: PhotographerProfile = {
    id: 42,
    user_id: 42,
    user_display_name: 'Test Photog',
    user_bio: 'A great photographer.',
    styles: ['人像', '风景', '街拍'],
    location: '上海',
    packages: [],
    portfolio: [],
  }

  it('produces correct resource_type and string ID', () => {
    const ctx = buildPhotographerPageContext(minimalProfile, route)
    expect(ctx.resource_type).toBe('photographer')
    expect(ctx.resource_id).toBe('42')
  })

  it('does not include public_email', () => {
    const withEmail: PhotographerProfile = {
      ...minimalProfile,
      public_email: 'test@example.com',
    }
    const ctx = buildPhotographerPageContext(withEmail, route)
    expect((ctx as any).public_email).toBeUndefined()
  })

  it('limits packages to 6', () => {
    const manyPkgs = Array.from({ length: 10 }, (_, i) => ({
      id: String(i), name: `Pkg ${i}`, price: 100 + i,
    })) as any
    const profile: PhotographerProfile = { ...minimalProfile, packages: manyPkgs }
    const ctx = buildPhotographerPageContext(profile, route)
    expect(ctx.packages?.length).toBeLessThanOrEqual(6)
  })

  it('limits portfolio to 6', () => {
    const manyWorks = Array.from({ length: 10 }, (_, i) => ({
      id: String(i), title: `Work ${i}`,
    })) as any
    const profile: PhotographerProfile = { ...minimalProfile, portfolio: manyWorks }
    const ctx = buildPhotographerPageContext(profile, route)
    expect(ctx.portfolio?.length).toBeLessThanOrEqual(6)
  })
})

// ── Package builder ──

describe('buildPackagePageContext', () => {
  const route = mockRoute('package-detail', '/packages/pkg99')

  const offer: PackageOffer = {
    id: 'pkg99',
    package_name: '城市写真',
    price: 2999,
    description: '一套城市写真方案',
    styles: ['城市', '时尚'],
    city: '北京',
    duration: 120,
    image_count: 30,
    photographer_id: 42,
    photographer_name: '摄影师张',
  }

  it('produces correct resource_type and string ID', () => {
    const ctx = buildPackagePageContext(offer, route)
    expect(ctx.resource_type).toBe('package')
    expect(ctx.resource_id).toBe('pkg99')
  })

  it('includes price_label', () => {
    const ctx = buildPackagePageContext(offer, route)
    expect(ctx.price_label).toContain('2999')
  })
})

// ── Project builder ──

describe('buildProjectPageContext', () => {
  const route = mockRoute('project-detail', '/projects/77')

  const project: ProjectBrief = {
    id: 77,
    customer_id: 1,
    title: '海边婚礼拍摄',
    description: '寻找一位有经验的摄影师',
    style_tags: ['婚礼', '海边'],
    city: '三亚',
    location_name: '三亚湾',
    location_text: '三亚湾海滩',
    status: 'open',
    budget_min: 5000,
    budget_max: 10000,
    shoot_date_start: '2026-08-15',
    duration_minutes: 240,
    reference_images: ['https://example.com/ref.jpg'],
    category: '婚礼',
    created_at: '2026-07-01T00:00:00Z',
  }

  it('produces correct resource_type and string ID', () => {
    const ctx = buildProjectPageContext(project, route)
    expect(ctx.resource_type).toBe('project')
    expect(ctx.resource_id).toBe('77')
  })

  it('maps budget_label correctly', () => {
    const ctx = buildProjectPageContext(project, route)
    expect(ctx.budget_label).toContain('5,000')
    expect(ctx.budget_label).toContain('10,000')
  })

  it('maps location correctly', () => {
    const ctx = buildProjectPageContext(project, route)
    expect(ctx.location).toBe('三亚湾')
  })

  it('maps reference image as thumbnail', () => {
    const ctx = buildProjectPageContext(project, route)
    expect(ctx.current_object?.thumbnail_url).toBe('https://example.com/ref.jpg')
  })
})

// ── Handoff (stage/consume) ──

describe('stage/consume handoff', () => {
  const route = mockRoute('work-detail', '/works/1')
  const work: WorkItem = { id: '1', title: 'Test', user_id: 1 }
  const context = buildWorkPageContext(work, route)

  beforeEach(() => {
    sessionStorage.clear()
  })

  it('can stage and consume', () => {
    const key = stageAIPageContext(context)
    expect(key).toBeTruthy()
    const consumed = consumeAIPageContext(key)
    expect(consumed).not.toBeNull()
    expect(consumed!.resource_type).toBe('portfolio_item')
    expect(consumed!.resource_id).toBe('1')
  })

  it('can only be consumed once', () => {
    const key = stageAIPageContext(context)
    const first = consumeAIPageContext(key)
    expect(first).not.toBeNull()
    const second = consumeAIPageContext(key)
    expect(second).toBeNull()
  })

  it('returns null for empty key', () => {
    expect(consumeAIPageContext('')).toBeNull()
  })

  it('returns null for expired handoff', () => {
    // Simulate expired data by setting createdAt far in the past
    const key = stageAIPageContext(context)
    const raw = sessionStorage.getItem('ai_page_context_handoff:' + key)
    if (raw) {
      const entry = JSON.parse(raw)
      entry.createdAt = Date.now() - 11 * 60 * 1000 // 11 min ago
      sessionStorage.setItem('ai_page_context_handoff:' + key, JSON.stringify(entry))
    }
    expect(consumeAIPageContext(key)).toBeNull()
  })

  it('returns null for corrupted data', () => {
    const key = 'corrupted'
    sessionStorage.setItem('ai_page_context_handoff:' + key, 'not-json')
    expect(consumeAIPageContext(key)).toBeNull()
  })

  it('returns null for missing required fields', () => {
    const key = 'missing'
    sessionStorage.setItem(
      'ai_page_context_handoff:' + key,
      JSON.stringify({ context: { resource_type: 'portfolio_item' }, createdAt: Date.now() }),
    )
    expect(consumeAIPageContext(key)).toBeNull()
  })
})

// ── Pruning ──

describe('empty field pruning', () => {
  const route = mockRoute('work-detail', '/works/1')

  it('omits undefined/empty fields from payload', () => {
    const work: WorkItem = { id: '1', title: 'T', user_id: 1 }
    const ctx = buildWorkPageContext(work, route)
    expect(ctx.description).toBeUndefined()
    expect(ctx.tags).toBeUndefined()
  })
})
