import { defineStore } from 'pinia'
import { toggleFollow, getFollowStatus } from '@/api/follow'

export const useFollowStore = defineStore('follow', {
  state: () => ({
    // { [userId]: true/false } — 当前用户是否关注了 userId
    items: {},
    // { [userId]: true } — 正在请求中的 userId
    pending: {},
  }),

  getters: {
    isFollowing: (state) => (userId) => !!state.items[userId],
    isPending: (state) => (userId) => !!state.pending[userId],
  },

  actions: {
    async toggle(userId) {
      if (this.pending[userId]) return this.isFollowing(userId)

      const prev = this.isFollowing(userId)
      this.items = { ...this.items, [userId]: !prev }
      this.pending = { ...this.pending, [userId]: true }

      try {
        const { data } = await toggleFollow(userId)
        this.items = { ...this.items, [userId]: data.following }
        return {
          following: data.following,
          followerCount: data.follower_count,
          followingCount: data.following_count,
        }
      } catch {
        this.items = { ...this.items, [userId]: prev }
        return { following: prev }
      } finally {
        this.pending = { ...this.pending, [userId]: false }
      }
    },

    async loadStatus(userId) {
      try {
        const { data } = await getFollowStatus(userId)
        this.items = { ...this.items, [userId]: data.following }
      } catch {
        // silently ignore
      }
    },
  },
})