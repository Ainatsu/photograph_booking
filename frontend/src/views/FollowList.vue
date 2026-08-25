<template>
  <div class="follow-list-page">
    <div class="back-row">
      <el-button text :icon="ArrowLeft" @click="goBack">返回</el-button>
    </div>

    <h2 class="page-title">{{ isFollowers ? '我的粉丝' : '我的关注' }}</h2>

    <div class="user-list" v-loading="loading">
      <div
        class="user-row"
        v-for="item in items"
        :key="item.user_id"
        @click="goUserDetail(item.user_id)"
      >
        <el-avatar :size="56" :src="getFullUrl(item.avatar_url)">
          {{ (item.display_name || '?')[0] }}
        </el-avatar>
        <div class="row-info">
          <span class="row-name">{{ item.display_name }}</span>
          <span class="row-bio" v-if="item.bio">{{ item.bio }}</span>
        </div>
      </div>
      <el-empty v-if="!loading && items.length === 0" description="暂无数据" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import { getFollowers, getFollowing } from '@/api/follow'

const route = useRoute()
const router = useRouter()

const userId = computed(() => Number(route.params.userId))
const isFollowers = computed(() => route.query.type === 'followers')

const items = ref([])
const loading = ref(false)

const fetchList = async () => {
  loading.value = true
  try {
    const fetcher = isFollowers.value ? getFollowers : getFollowing
    const res = await fetcher(userId.value, { skip: 0, limit: 100 })
    items.value = res.data.items || []
  } finally {
    loading.value = false
  }
}

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const goUserDetail = (uid) => {
  router.push(`/photographer/${uid}`)
}

const goBack = () => {
  router.back()
}

onMounted(fetchList)
</script>

<style scoped>
.follow-list-page {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-6);
}
.back-row { margin-bottom: var(--space-4); }
.page-title {
  margin: 0 0 var(--space-6);
  font-size: calc(var(--text-2xl) * 1rem);
  font-weight: 700;
  color: var(--color-ink);
}
.user-list { display: flex; flex-direction: column; gap: 10px; }
.user-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s;
}
.user-row:hover { border-color: var(--color-ink-secondary); }
.row-info { display: flex; flex-direction: column; gap: var(--space-1); }
.row-name { font-size: calc(var(--text-base) * 1rem); font-weight: 600; color: var(--color-ink); }
.row-bio { font-size: calc(var(--text-sm) * 1rem); color: var(--color-ink-secondary); max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
