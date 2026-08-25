<template>
  <div class="favorites-page">
    <div class="page-header">
      <h2 class="page-title">我的收藏</h2>
    </div>

    <el-radio-group v-model="favTab" size="small" class="fav-tab-toggle">
      <el-radio-button value="works">作品收藏</el-radio-button>
      <el-radio-button value="packages">方案收藏</el-radio-button>
    </el-radio-group>

    <!-- 作品收藏 -->
    <div v-if="favTab === 'works'" class="waterfall" v-loading="loading">
      <div v-if="items.length > 0">
        <div
          class="waterfall-item"
          v-for="item in items"
          :key="item.work_id"
          @click="goWorkDetail(item)"
        >
          <el-card shadow="never" :body-style="{ padding: '0' }">
            <div
              v-if="item.work_data?.url"
              class="preview-image-wrap"
              :style="{ aspectRatio: getFavoriteWorkPreviewRatio(item) }"
            >
              <el-image
                :src="getFavoriteWorkPreviewUrl(item)"
                fit="cover"
                class="work-image"
                lazy
              />
            </div>
            <div v-else class="work-placeholder">暂无图片</div>
            <div class="card-body">
              <div class="work-title" v-if="item.work_data?.title">
                {{ item.work_data.title }}
              </div>
              <div class="work-tag" v-if="getWorkTags(item.work_data).length">
                <el-tag v-for="tag in getWorkTags(item.work_data)" :key="tag" size="small">{{ tag }}</el-tag>
              </div>
              <div class="photographer-row">
                <el-avatar
                  :size="24"
                  :src="getAvatarUrl(item)"
                  class="photographer-avatar"
                >
                  {{ (item.photographer_name || '?')[0] }}
                </el-avatar>
                <span class="photographer-name">{{ item.photographer_name || '摄影师' }}</span>
                <span class="fav-time">{{ formatTime(item.created_at) }}</span>
              </div>
            </div>
          </el-card>
        </div>
      </div>

      <el-empty
        v-if="!loading && items.length === 0"
        description="还没有收藏作品，去发现页看看吧~"
      >
        <el-button type="primary" @click="$router.push('/works')">浏览作品</el-button>
      </el-empty>
    </div>

    <!-- 方案收藏 -->
    <div v-if="favTab === 'packages'" class="waterfall" v-loading="pkgLoading">
      <div v-if="pkgItems.length > 0">
        <div
          class="waterfall-item"
          v-for="item in pkgItems"
          :key="item.package_id"
          @click="goPackageDetail(item)"
        >
          <el-card shadow="never" :body-style="{ padding: '0' }">
            <div
              v-if="getFavoritePackageCoverUrl(item)"
              class="preview-image-wrap"
              :style="{ aspectRatio: getFavoritePackagePreviewRatio(item) }"
            >
              <el-image
                :src="getFavoritePackageCoverUrl(item)"
                fit="cover"
                class="work-image"
                lazy
              />
            </div>
            <div v-else class="work-placeholder">暂无示例图</div>
            <div class="card-body">
              <div class="work-title" v-if="item.package_data?.package_name">
                {{ item.package_data.package_name }}
              </div>
              <div class="pkg-price" v-if="item.package_data?.price">¥{{ item.package_data.price }}</div>
              <div class="photographer-row">
                <el-avatar
                  :size="24"
                  :src="getAvatarUrl(item)"
                  class="photographer-avatar"
                >
                  {{ (item.photographer_name || '?')[0] }}
                </el-avatar>
                <span class="photographer-name">{{ item.photographer_name || '摄影师' }}</span>
                <span class="fav-time">{{ formatTime(item.created_at) }}</span>
              </div>
            </div>
          </el-card>
        </div>
      </div>

      <el-empty
        v-if="!pkgLoading && pkgItems.length === 0"
        description="还没有收藏方案，去看看有哪些方案吧~"
      >
        <el-button type="primary" @click="$router.push('/packages')">浏览方案</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getUserFavorites, getUserPackageFavorites } from '@/api/favorite'
import { useImageAspectRatio } from '@/composables/useImageAspectRatio'
import {
  getFavoritePackagePreviewUrl as getFavoritePackageCardPreviewUrl,
  getFavoriteWorkPreviewUrl,
} from '@/utils/imagePreview'

const router = useRouter()
const favTab = ref('works')
const items = ref([])
const total = ref(0)
const loading = ref(false)
const pkgItems = ref([])
const pkgTotal = ref(0)
const pkgLoading = ref(false)
const { getOrPreload } = useImageAspectRatio()

const fetchWorks = async () => {
  loading.value = true
  try {
    const { data } = await getUserFavorites(0, 200)
    items.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

let pkgLoaded = false
const fetchPackages = async () => {
  if (pkgLoaded) return
  pkgLoading.value = true
  try {
    const { data } = await getUserPackageFavorites(0, 200)
    pkgItems.value = data.items || []
    pkgTotal.value = data.total || 0
    pkgLoaded = true
  } finally {
    pkgLoading.value = false
  }
}

const getWorkTags = (work) => {
  if (Array.isArray(work?.tags)) return work.tags
  return (work?.tag || '')
    .split(/[,\uFF0C\u3001\n]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
}

const ratioKey = (type, id) => (id ? `${type}:${id}` : '')

const getFavoriteWorkPreviewRatio = (item) => {
  const url = getFavoriteWorkPreviewUrl(item)
  return getOrPreload(url, ratioKey('favorite-page-work', item?.work_id || item?.work_data?.url))
}

const getFavoritePackageCoverUrl = (item) => {
  return getFavoritePackageCardPreviewUrl(item)
}

const getFavoritePackagePreviewRatio = (item) => {
  const url = getFavoritePackageCoverUrl(item)
  return getOrPreload(url, ratioKey('favorite-page-package', item?.package_id || url))
}

const getAvatarUrl = (item) => {
  const avatar = item.photographer_avatar
  if (!avatar) return ''
  return avatar.startsWith('http') ? avatar : avatar
}

const formatTime = (dt) => {
  if (!dt) return ''
  const d = new Date(dt)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 2592000000) return `${Math.floor(diff / 86400000)}天前`
  return d.toLocaleDateString('zh-CN')
}

const goWorkDetail = (item) => {
  if (item.work_id) {
    router.push({ path: `/work/${item.work_id}`, state: { from: router.currentRoute.value.fullPath, work: item.work_data } })
  }
}

const goPackageDetail = (item) => {
  if (item.package_id) {
    router.push({ path: `/package/${item.package_id}`, state: { from: router.currentRoute.value.fullPath } })
  }
}

watch(favTab, (tab) => {
  if (tab === 'packages') fetchPackages()
})

onMounted(fetchWorks)
</script>

<style scoped>
.favorites-page { max-width: var(--content-max-width); margin: 0 auto; padding: 20px; }
.page-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }
.page-title { font-size: var(--text-3xl); font-weight: 700; margin: 0; color: var(--color-ink); }

.waterfall { column-count: 4; column-gap: 16px; }
.waterfall-item {
  break-inside: avoid; margin-bottom: 16px; cursor: pointer;
  border-radius: var(--radius-md);
  transition: border-color 0.2s;
}
.waterfall-item :deep(.el-card) {
  border: var(--border-default);
  background: var(--color-paper-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.waterfall-item:hover :deep(.el-card) {
  border-color: var(--color-brand);
}

.preview-image-wrap {
  overflow: hidden;
  background: var(--color-paper);
  display: flex;
  align-items: center;
  justify-content: center;
}
.work-image { width: 100%; height: 100%; display: block; }
.work-placeholder {
  width: 100%; aspect-ratio: 1/1; background: var(--color-paper);
  display: flex; align-items: center; justify-content: center; color: var(--color-ink-tertiary);
  font-size: 14px;
}

.card-body { padding: 12px 14px; }
.work-title { font-size: 15px; font-weight: 600; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-ink); }
.work-tag { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.pkg-price { font-size: 14px; font-weight: 600; color: var(--color-ink); margin-bottom: 8px; }

.photographer-row { display: flex; align-items: center; gap: 8px; }
.photographer-avatar { flex-shrink: 0; }
.photographer-name { font-size: 13px; color: var(--color-ink); flex: 1; }
.fav-time { font-size: var(--text-xs); color: var(--color-ink-secondary); white-space: nowrap; }

/* el-tag overrides */
:deep(.el-tag--small) {
  background: var(--color-brand-light);
  color: var(--color-brand);
  border-color: var(--color-brand-light);
}

/* el-radio-group tabs */
.fav-tab-toggle {
  margin-bottom: 20px;
}
:deep(.el-radio-button__inner) {
  border-color: var(--color-border);
  color: var(--color-ink-secondary);
  background: var(--color-paper-light);
}
:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--color-brand);
  border-color: var(--color-brand);
  color: #fff;
  box-shadow: none;
}
:deep(.el-radio-button__inner:hover) {
  color: var(--color-brand);
}

@media (max-width: 992px) { .waterfall { column-count: 3; } }
@media (max-width: 768px) { .waterfall { column-count: 2; } }
@media (max-width: 480px) { .waterfall { column-count: 1; } }
</style>
