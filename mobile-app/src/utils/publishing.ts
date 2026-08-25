import type { PublishResourceType } from '@/types/publishing'

// 新增类型：草稿条目
export interface DraftItem<T = any> {
  id: string // 唯一标识（UUID）
  type: PublishResourceType
  value: T
  updatedAt: string
  summary?: string // 内容摘要，用于显示
}

const oldKeyPrefix = 'mobile-publish-draft:'
const newKeyPrefix = 'mobile-publish-drafts:'

function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback 兼容不支持 crypto.randomUUID 的环境
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

function readDraftList(type: PublishResourceType): DraftItem[] {
  try {
    const raw = localStorage.getItem(`${newKeyPrefix}${type}`)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (item): item is DraftItem =>
        item && typeof item === 'object' && typeof item.id === 'string' && typeof item.type === 'string',
    )
  } catch {
    return []
  }
}

function writeDraftList(type: PublishResourceType, items: DraftItem[]): void {
  try {
    localStorage.setItem(`${newKeyPrefix}${type}`, JSON.stringify(items))
  } catch {
    // 本地空间不可用时静默失败
  }
}

function migrateOldDrafts(): void {
  const types: PublishResourceType[] = ['work', 'package', 'project']
  for (const type of types) {
    const oldKey = `${oldKeyPrefix}${type}`
    try {
      const raw = localStorage.getItem(oldKey)
      if (!raw) continue
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || !parsed.value || typeof parsed.value !== 'object') {
        localStorage.removeItem(oldKey)
        continue
      }
      // 如果新格式已存在，不再迁移
      const newKey = `${newKeyPrefix}${type}`
      if (localStorage.getItem(newKey)) {
        localStorage.removeItem(oldKey)
        continue
      }
      const item: DraftItem = {
        id: generateId(),
        type,
        value: parsed.value,
        updatedAt: parsed.updatedAt || new Date().toISOString(),
      }
      localStorage.setItem(newKey, JSON.stringify([item]))
      localStorage.removeItem(oldKey)
    } catch {
      localStorage.removeItem(oldKey)
    }
  }
}

/**
 * 列出草稿。
 * @param type 可选，不传则返回所有类型的草稿
 */
export function listPublishDrafts(type?: PublishResourceType): DraftItem[] {
  migrateOldDrafts()
  const allTypes: PublishResourceType[] = ['work', 'package', 'project']
  const types = type ? [type] : allTypes
  const result: DraftItem[] = []
  for (const t of types) {
    const items = readDraftList(t)
    result.push(...items)
  }
  // 按保存时间倒序
  result.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
  return result
}

/**
 * 读取指定草稿。
 * @param type 草稿类型
 * @param draftId 可选，不传则读取该类型最新的一条草稿（向后兼容）
 */
export function readPublishDraft<T>(type: PublishResourceType, draftId?: string): DraftItem<T> | null {
  migrateOldDrafts()
  const items = readDraftList(type)
  if (draftId) {
    const found = items.find((item) => item.id === draftId)
    return (found as DraftItem<T>) ?? null
  }
  // 不传 draftId，返回最新的一条
  return items.length > 0 ? (items[0] as DraftItem<T>) : null
}

/**
 * 保存草稿。
 * @param type 草稿类型
 * @param value 草稿数据
 * @param draftId 可选，传了则更新指定草稿，不传则创建新草稿
 * @returns 草稿 ID
 */
export function savePublishDraft<T>(type: PublishResourceType, value: T, draftId?: string): string {
  migrateOldDrafts()
  const items = readDraftList(type)
  const now = new Date().toISOString()

  if (draftId) {
    const index = items.findIndex((item) => item.id === draftId)
    if (index !== -1) {
      items[index] = { ...items[index], value, updatedAt: now }
      writeDraftList(type, items)
      return draftId
    }
    // 如果指定 ID 不存在，回退创建新草稿
  }

  const id = generateId()
  const newItem: DraftItem = { id, type, value, updatedAt: now }
  items.unshift(newItem)
  writeDraftList(type, items)
  return id
}

/**
 * 删除指定草稿。
 */
export function deletePublishDraft(type: PublishResourceType, draftId: string): void {
  migrateOldDrafts()
  const items = readDraftList(type)
  const filtered = items.filter((item) => item.id !== draftId)
  if (filtered.length === items.length) return
  writeDraftList(type, filtered)
}

/**
 * 清除草稿。
 * @param type 可选，传 type 则清除该类型所有草稿
 * @param draftId 可选，同时传 type 和 draftId 则清除指定草稿
 */
export function clearPublishDraft(type?: PublishResourceType, draftId?: string): void {
  migrateOldDrafts()
  if (type && draftId) {
    deletePublishDraft(type, draftId)
    return
  }
  if (type) {
    writeDraftList(type, [])
    return
  }
  // 都不传则清除所有类型
  const allTypes: PublishResourceType[] = ['work', 'package', 'project']
  for (const t of allTypes) {
    writeDraftList(t, [])
  }
}

export function normalizeTags(values: string[], max = 12): string[] {
  const result: string[] = []
  for (const value of values) {
    for (const tag of String(value).split(/[，,、\n]+/)) {
      const normalized = tag.trim().replace(/^#/, '')
      if (!normalized || result.some((item) => item.toLocaleLowerCase() === normalized.toLocaleLowerCase())) continue
      result.push(normalized.slice(0, 30))
      if (result.length >= max) return result
    }
  }
  return result
}

export function toOptionalIso(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function toLocalDateTimeInput(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return localDate.toISOString().slice(0, 16)
}

export function formatDraftTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
