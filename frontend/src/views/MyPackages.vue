<template>
  <div class="my-packages-page">
    <div class="page-header">
      <h2>我的方案</h2>
      <el-button type="primary" :icon="Plus" @click="router.push('/packages/new')">
        发布新方案
      </el-button>
    </div>

    <div v-loading="loading">
      <div v-if="packages.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无方案，快去发布一个吧" />
      </div>

      <div class="package-grid" v-else>
        <div
          v-for="pkg in packages"
          :key="pkg.id || pkg.package_name"
          class="package-card"
        >
          <div class="pkg-header">
            <h3>{{ pkg.package_name }}</h3>
            <span class="pkg-price">&yen;{{ pkg.price }}</span>
          </div>
          <p class="pkg-desc">{{ pkg.description || '暂无描述' }}</p>
          <div class="pkg-meta">
            <span>时长：{{ pkg.duration || '待定' }}</span>
            <span v-if="pkg.city" class="city-tag">{{ pkg.city }}</span>
            <span v-else class="city-tag unrestricted">不限制城市</span>
          </div>
          <div class="pkg-samples" v-if="pkg.samples?.length">
            <el-image
              v-for="(sample, idx) in pkg.samples.slice(0, 3)"
              :key="idx"
              :src="sample"
              fit="cover"
              class="sample-img"
              :preview-src-list="pkg.samples"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from 'lucide-vue-next'
import api from '../utils/api'

defineOptions({ name: 'MyPackages' })

const router = useRouter()
const packages = ref([])
const loading = ref(true)

const fetchMyPackages = async () => {
  loading.value = true
  try {
    const res = await api.get('/users/me', { skipErrorHandler: true })
    const userId = res.data.id
    const profileRes = await api.get(`/photographers/profile/${userId}`, { skipErrorHandler: true })
    packages.value = (profileRes.data.packages || []).filter(p => p.name)
    // 标准化字段名
    packages.value = packages.value.map(p => ({
      ...p,
      package_name: p.name,
    }))
  } catch {
    packages.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchMyPackages)
</script>

<style scoped>
.my-packages-page {
  max-width: 1120px;
  margin: 0 auto;
  padding: var(--space-6);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-6);
}

.page-header h2 {
  margin: 0;
  font-size: calc(var(--text-2xl) * 1rem);
  color: var(--color-ink);
}

.empty-state {
  margin-top: 60px;
}

.package-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: var(--space-4);
}

.package-card {
  padding: var(--space-6);
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  transition: border-color 0.15s;
}

.package-card:hover {
  border-color: var(--color-ink-secondary);
}

.pkg-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.pkg-header h3 {
  margin: 0;
  font-size: calc(var(--text-base) * 1rem);
  color: var(--color-ink);
}

.pkg-price {
  color: var(--color-brand);
  font-weight: 700;
  font-size: calc(var(--text-lg) * 1rem);
}

.pkg-desc {
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-sm) * 1rem);
  line-height: 1.6;
  margin: 0 0 var(--space-3);
}

.pkg-meta {
  display: flex;
  gap: var(--space-4);
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-sm) * 1rem);
  margin-bottom: var(--space-3);
  align-items: center;
}

.city-tag {
  display: inline-block;
  padding: 1px var(--space-2);
  font-size: calc(var(--text-xs) * 1rem);
  color: var(--color-brand);
  background: var(--color-brand-light);
  border-radius: var(--radius-md);
  font-weight: 500;
}

.city-tag.unrestricted {
  color: var(--color-ink-tertiary);
  background: var(--color-border-light);
}

.pkg-samples {
  display: flex;
  gap: var(--space-2);
}

.sample-img {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-md);
  object-fit: cover;
  cursor: pointer;
}
</style>
