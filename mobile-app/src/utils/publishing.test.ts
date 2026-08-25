import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearPublishDraft,
  deletePublishDraft,
  listPublishDrafts,
  normalizeTags,
  readPublishDraft,
  savePublishDraft,
  toLocalDateTimeInput,
  toOptionalIso,
} from './publishing'

describe('mobile publishing helpers', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('normalizes separators, removes hashes and deduplicates tags case-insensitively', () => {
    expect(normalizeTags(['#人像，胶片', '人像、Portrait\nportrait', '  夜景  '])).toEqual([
      '人像',
      '胶片',
      'Portrait',
      '夜景',
    ])
  })

  it('respects tag count and length limits', () => {
    expect(normalizeTags(['一,二,三,四'], 3)).toEqual(['一', '二', '三'])
    expect(normalizeTags(['a'.repeat(40)])).toEqual(['a'.repeat(30)])
  })

  it('converts valid local date values to ISO and rejects empty or invalid values', () => {
    expect(toOptionalIso('')).toBeNull()
    expect(toOptionalIso('not-a-date')).toBeNull()
    expect(toOptionalIso('2026-08-01T10:30')).toBe(new Date('2026-08-01T10:30').toISOString())
  })

  it('hydrates API timestamps into datetime-local values without changing the instant', () => {
    const value = toLocalDateTimeInput('2026-08-01T02:30:00Z')
    expect(value).toMatch(/^2026-08-01T\d{2}:30$/)
    expect(new Date(value).toISOString()).toBe('2026-08-01T02:30:00.000Z')
    expect(toLocalDateTimeInput('invalid')).toBe('')
  })

  it('saves, reads, lists and clears local publishing drafts with multi-slot support', () => {
    // save 创建新草稿并返回 ID
    const id1 = savePublishDraft('project', { title: '夏日写真', tags: ['自然光'] })
    expect(typeof id1).toBe('string')
    expect(id1.length).toBeGreaterThan(0)

    // save 第二个草稿
    const id2 = savePublishDraft('project', { title: '秋日人像', tags: ['胶片'] })
    expect(id2).not.toBe(id1)

    // readPublishDraft 不传 draftId 返回最新一条
    const latest = readPublishDraft<{ title: string }>('project')
    expect(latest).not.toBeNull()
    expect(latest!.id).toBe(id2)
    expect(latest!.type).toBe('project')
    expect(latest!.value.title).toBe('秋日人像')
    expect(Number.isNaN(new Date(latest!.updatedAt).getTime())).toBe(false)

    // readPublishDraft 传 draftId 返回指定草稿
    const first = readPublishDraft<{ title: string }>('project', id1)
    expect(first).not.toBeNull()
    expect(first!.id).toBe(id1)
    expect(first!.value.title).toBe('夏日写真')

    // listPublishDrafts 列出所有草稿
    const all = listPublishDrafts()
    expect(all.length).toBe(2)
    expect(all[0].id).toBe(id2) // 最新在前

    // listPublishDrafts 按类型筛选
    const typeFiltered = listPublishDrafts('project')
    expect(typeFiltered.length).toBe(2)

    const emptyFiltered = listPublishDrafts('work')
    expect(emptyFiltered.length).toBe(0)

    // deletePublishDraft 删除指定草稿
    deletePublishDraft('project', id1)
    expect(listPublishDrafts('project').length).toBe(1)
    expect(listPublishDrafts('project')[0].id).toBe(id2)

    // clearPublishDraft 清空指定类型所有草稿
    clearPublishDraft('project')
    expect(listPublishDrafts('project').length).toBe(0)

    // clearPublishDraft 清空所有类型
    savePublishDraft('work', { title: 'test' })
    savePublishDraft('package', { name: 'test' })
    expect(listPublishDrafts().length).toBe(2)
    clearPublishDraft()
    expect(listPublishDrafts().length).toBe(0)
  })
})
