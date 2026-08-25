<template>
  <div>
    <h3>仪表盘</h3>
    <el-row :gutter="16" class="stats-row" v-loading="loading">
      <el-col :span="4" v-for="card in cards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../utils/api'

const stats = ref({})
const loading = ref(false)

const fetch = async () => {
  loading.value = true
  try {
    const res = await api.get('/dashboard')
    stats.value = res.data
  } finally {
    loading.value = false
  }
}

const cards = computed(() => [
  { label: '总用户数', value: stats.value.total_users ?? '-' },
  { label: '摄影师', value: stats.value.total_photographers ?? '-' },
  { label: '客户', value: stats.value.total_customers ?? '-' },
  { label: '总订单', value: stats.value.total_orders ?? '-' },
  { label: '待处理订单', value: stats.value.pending_orders ?? '-' },
  { label: '今日订单', value: stats.value.today_orders ?? '-' },
])

onMounted(fetch)
</script>

<style scoped>
.stats-row {
  margin-top: 16px;
}

.stat-card {
  text-align: center;
  background: #FFFDF9;
  border: 1px solid #D9D3CB;
  border-radius: 4px;
  box-shadow: none;
}

.stat-card :deep(.el-card__body) {
  padding: 24px 16px;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: #1A1A1A;
  line-height: 1.2;
}

.stat-label {
  font-size: 0.875rem;
  color: #9C9892;
  margin-top: 8px;
}

@media (max-width: 992px) {
  .stats-row :deep(.el-col) {
    flex: 0 0 50%;
    max-width: 50%;
    margin-bottom: 12px;
  }
}

@media (max-width: 576px) {
  .stats-row :deep(.el-col) {
    flex: 0 0 100%;
    max-width: 100%;
  }
}
</style>
