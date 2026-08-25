import { defineStore } from 'pinia'
import {
  toggleFavorite,
  togglePackageFavorite,
  getBatchFavoriteStatus,
  getBatchPackageFavoriteStatus,
} from '@/api/favorite'

export const useFavoriteStore = defineStore('favorites', {
  state: () => ({
    // { [workId]: true/false }
    items: {},
    // { [packageId]: true/false }
    pkgItems: {},
    // { [workId]: true }
    pending: {},
    // { [packageId]: true }
    pkgPending: {},
  }),

  getters: {
    get: (state) => (workId) => !!state.items[workId],
    isPending: (state) => (workId) => !!state.pending[workId],
    getPkg: (state) => (packageId) => !!state.pkgItems[packageId],
    isPkgPending: (state) => (packageId) => !!state.pkgPending[packageId],
  },

  actions: {
    // ---- 作品收藏 ----
    async toggle(workId, photographerId, workData = null) {
      if (this.pending[workId]) return this.get(workId)

      const prev = this.get(workId)
      this.items = { ...this.items, [workId]: !prev }
      this.pending = { ...this.pending, [workId]: true }

      try {
        const { data } = await toggleFavorite(workId, photographerId, workData)
        this.items = { ...this.items, [workId]: data.favorited }
        return data.favorited
      } catch {
        this.items = { ...this.items, [workId]: prev }
        return prev
      } finally {
        this.pending = { ...this.pending, [workId]: false }
      }
    },

    async loadMany(ids) {
      const clean = [...new Set(ids.filter(Boolean).map(String))]
      if (!clean.length) return

      try {
        const { data } = await getBatchFavoriteStatus(clean)
        const merged = { ...this.items }
        clean.forEach((id) => {
          merged[id] = !!data[id]
        })
        this.items = merged
      } catch {
        // silently ignore on error
      }
    },

    // ---- 方案收藏 ----
    async togglePkg(packageId, photographerId, packageData = null) {
      if (this.pkgPending[packageId]) return this.getPkg(packageId)

      const prev = this.getPkg(packageId)
      this.pkgItems = { ...this.pkgItems, [packageId]: !prev }
      this.pkgPending = { ...this.pkgPending, [packageId]: true }

      try {
        const { data } = await togglePackageFavorite(packageId, photographerId, packageData)
        this.pkgItems = { ...this.pkgItems, [packageId]: data.favorited }
        return data.favorited
      } catch {
        this.pkgItems = { ...this.pkgItems, [packageId]: prev }
        return prev
      } finally {
        this.pkgPending = { ...this.pkgPending, [packageId]: false }
      }
    },

    async loadPkgMany(ids) {
      const clean = [...new Set(ids.filter(Boolean).map(String))]
      if (!clean.length) return

      try {
        const { data } = await getBatchPackageFavoriteStatus(clean)
        const merged = { ...this.pkgItems }
        clean.forEach((id) => {
          merged[id] = !!data[id]
        })
        this.pkgItems = merged
      } catch {
        // silently ignore on error
      }
    },
  },
})
