import { defineStore } from 'pinia'
import { getLikeSummary, setLikeState } from '@/api/like'

const EMPTY = Object.freeze({ liked: false, count: 0 })
const TARGET_TYPES = new Set(['portfolio', 'package'])

const keyOf = (targetType, targetId) => `${targetType}:${targetId}`

const cleanIds = (ids) => [...new Set(
  (ids || [])
    .map((id) => String(id || '').trim())
    .filter(Boolean),
)]

const normalizeState = (state) => ({
  liked: !!state?.liked,
  count: Math.max(0, Number(state?.count || 0)),
})

export const useLikeStore = defineStore('likes', {
  state: () => ({
    items: {},
    pending: {},
    version: {},
    requestSeq: 0,
  }),

  getters: {
    get: (state) => (targetType, targetId) => normalizeState(state.items[keyOf(targetType, targetId)] || EMPTY),
    isPending: (state) => (targetType, targetId) => !!state.pending[keyOf(targetType, targetId)],
  },

  actions: {
    assertTarget(targetType, targetId = 'placeholder') {
      const normalizedType = String(targetType || '').trim()
      const normalizedId = String(targetId || '').trim()
      if (!TARGET_TYPES.has(normalizedType)) {
        throw new Error(`Invalid like target type: ${targetType}`)
      }
      if (!normalizedId) {
        throw new Error('Like target id cannot be empty')
      }
      return { targetType: normalizedType, targetId: normalizedId }
    },

    write(targetType, targetId, value, expectedVersion = null) {
      const targetKey = keyOf(targetType, targetId)
      if (expectedVersion !== null && (this.version[targetKey] || 0) !== expectedVersion) {
        return false
      }

      this.items = {
        ...this.items,
        [targetKey]: normalizeState(value),
      }
      return true
    },

    markChanged(targetType, targetId) {
      const targetKey = keyOf(targetType, targetId)
      this.version = {
        ...this.version,
        [targetKey]: (this.version[targetKey] || 0) + 1,
      }
      return this.version[targetKey]
    },

    async loadMany(targetType, ids) {
      const { targetType: normalizedType } = this.assertTarget(targetType)
      const normalizedIds = cleanIds(ids)
      if (!normalizedIds.length) return {}

      const snapshot = {}
      normalizedIds.forEach((id) => {
        snapshot[keyOf(normalizedType, id)] = this.version[keyOf(normalizedType, id)] || 0
      })

      const requestId = ++this.requestSeq
      const { data } = await getLikeSummary(normalizedType, normalizedIds)
      const items = data.items || {}

      normalizedIds.forEach((id) => {
        const targetKey = keyOf(normalizedType, id)
        const expectedVersion = snapshot[targetKey]
        this.write(normalizedType, id, items[id] || EMPTY, expectedVersion)
      })

      return { requestId, items }
    },

    async toggle(targetType, targetId) {
      const target = this.assertTarget(targetType, targetId)
      const targetKey = keyOf(target.targetType, target.targetId)
      if (this.pending[targetKey]) return this.get(target.targetType, target.targetId)

      const previous = this.get(target.targetType, target.targetId)
      const nextLiked = !previous.liked
      const optimistic = {
        liked: nextLiked,
        count: Math.max(0, previous.count + (nextLiked ? 1 : -1)),
      }

      this.markChanged(target.targetType, target.targetId)
      this.write(target.targetType, target.targetId, optimistic)
      this.pending = { ...this.pending, [targetKey]: true }

      try {
        const { data } = await setLikeState(target.targetType, target.targetId, nextLiked)
        const confirmed = normalizeState(data)
        this.markChanged(target.targetType, target.targetId)
        this.write(target.targetType, target.targetId, confirmed)
        return confirmed
      } catch (error) {
        this.markChanged(target.targetType, target.targetId)
        this.write(target.targetType, target.targetId, previous)
        throw error
      } finally {
        const nextPending = { ...this.pending }
        delete nextPending[targetKey]
        this.pending = nextPending
      }
    },
  },
})
