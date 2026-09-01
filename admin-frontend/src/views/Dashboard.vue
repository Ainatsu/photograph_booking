<template>
  <div class="dashboard-page">
    <header class="page-header">
      <div><h1>仪表盘</h1><p>平台业务与 AI 图片生成运行概览</p></div>
      <el-button :icon="RefreshCw" :loading="loading || generationLoading" @click="refreshAll">刷新</el-button>
    </header>

    <section aria-labelledby="business-title">
      <h2 id="business-title">业务概览</h2>
      <el-row :gutter="12" class="stats-row" v-loading="loading">
        <el-col v-for="card in cards" :key="card.label" :xs="12" :sm="8" :lg="4">
          <div class="metric-tile"><span>{{ card.label }}</span><strong>{{ card.value }}</strong></div>
        </el-col>
      </el-row>
    </section>

    <section class="generation-section" aria-labelledby="generation-title">
      <div class="section-heading">
        <div><h2 id="generation-title">图片生成调用</h2><p>成功率按已结束任务计算，部分完成计为成功。</p></div>
        <el-segmented v-model="periodDays" :options="periodOptions" @change="fetchGenerationOverview" />
      </div>

      <div v-loading="generationLoading" class="generation-content" aria-live="polite">
        <div class="generation-metrics">
          <div v-for="item in generationCards" :key="item.label" class="generation-metric">
            <span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>{{ item.note }}</small>
          </div>
        </div>

        <div class="operations-grid">
          <div class="status-panel">
            <h3>任务状态</h3>
            <div v-if="statusRows.length" class="status-list">
              <div v-for="item in statusRows" :key="item.key" class="status-row">
                <div><span>{{ item.label }}</span><strong>{{ item.count }}</strong></div>
                <el-progress :percentage="item.percentage" :stroke-width="8" :show-text="false" :color="item.color" />
              </div>
            </div>
            <el-empty v-else description="当前周期暂无生成调用" :image-size="72" />
          </div>
          <div class="provider-panel">
            <h3>Provider 分布</h3>
            <dl v-if="providerRows.length" class="provider-list">
              <div v-for="item in providerRows" :key="item.name"><dt>{{ item.name }}</dt><dd>{{ item.count }} 次</dd></div>
            </dl>
            <el-empty v-else description="暂无 Provider 数据" :image-size="72" />
          </div>
        </div>

        <div class="recent-panel">
          <h3>最近任务</h3>
          <el-table :data="generation.recent_jobs || []" empty-text="当前周期暂无任务" table-layout="fixed">
            <el-table-column prop="job_id" label="Job" width="76" />
            <el-table-column label="模式" width="104"><template #default="{ row }">{{ modeLabel(row.mode) }}</template></el-table-column>
            <el-table-column label="状态" width="104"><template #default="{ row }"><el-tag :type="statusTagType(row.status)" effect="plain">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
            <el-table-column prop="provider" label="Provider" min-width="130"><template #default="{ row }">{{ row.provider || '等待调用' }}</template></el-table-column>
            <el-table-column label="结果" width="88"><template #default="{ row }">{{ row.saved_count }}/{{ row.requested_count }}</template></el-table-column>
            <el-table-column label="耗时" width="100"><template #default="{ row }">{{ formatLatency(row.latency_ms) }}</template></el-table-column>
            <el-table-column label="尝试" width="72" prop="attempts" />
            <el-table-column label="来源" width="96"><template #default="{ row }">{{ row.is_regenerated ? '重新生成' : '首次生成' }}</template></el-table-column>
            <el-table-column label="创建时间" min-width="168"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
          </el-table>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import api from '../utils/api'

const stats = ref({})
const generation = ref({})
const loading = ref(false)
const generationLoading = ref(false)
const periodDays = ref(7)
const periodOptions = [{ label: '近 7 天', value: 7 }, { label: '近 30 天', value: 30 }]
const cards = computed(() => [
  { label: '总用户数', value: stats.value.total_users ?? '-' }, { label: '摄影师', value: stats.value.total_photographers ?? '-' },
  { label: '客户', value: stats.value.total_customers ?? '-' }, { label: '总订单', value: stats.value.total_orders ?? '-' },
  { label: '待处理订单', value: stats.value.pending_orders ?? '-' }, { label: '今日订单', value: stats.value.today_orders ?? '-' },
])
const generationCards = computed(() => [
  { label: '生成任务', value: generation.value.total_jobs ?? 0, note: `${periodDays.value} 天内` },
  { label: '成功率', value: `${generation.value.success_rate ?? 0}%`, note: `${generation.value.successful_jobs ?? 0} 个成功任务` },
  { label: '生成图片', value: generation.value.generated_assets ?? 0, note: '已保存资产' },
  { label: '平均耗时', value: formatLatency(generation.value.average_latency_ms), note: '端到端耗时' },
  { label: '重新生成', value: generation.value.regenerated_jobs ?? 0, note: '继承原任务参数' },
])
const statusMeta = {
  completed: { label: '已完成', color: '#3f7d45' }, partial: { label: '部分完成', color: '#b7791f' },
  failed: { label: '失败', color: '#b42318' }, generating: { label: '生成中', color: '#2563a6' },
  queued: { label: '排队中', color: '#6b7280' }, retry_wait: { label: '等待重试', color: '#7c5aa6' }, cancelled: { label: '已取消', color: '#8a8178' },
}
const statusRows = computed(() => {
  const total = Math.max(1, Number(generation.value.total_jobs || 0))
  return Object.entries(generation.value.status_counts || {}).map(([key, count]) => ({
    key, count, percentage: Math.round(Number(count) / total * 100), ...(statusMeta[key] || { label: key, color: '#6b7280' }),
  })).sort((a, b) => b.count - a.count)
})
const providerRows = computed(() => Object.entries(generation.value.provider_counts || {})
  .map(([name, count]) => ({ name: name === 'pending' ? '等待调用' : name, count })).sort((a, b) => b.count - a.count))

async function fetchStats() { loading.value = true; try { stats.value = (await api.get('/dashboard')).data } finally { loading.value = false } }
async function fetchGenerationOverview() { generationLoading.value = true; try { generation.value = (await api.get('/ai/image-generations/overview', { params: { days: periodDays.value } })).data } finally { generationLoading.value = false } }
function refreshAll() { void Promise.all([fetchStats(), fetchGenerationOverview()]) }
function formatLatency(value) { if (value === null || value === undefined) return '-'; return value >= 1000 ? `${(value / 1000).toFixed(1)} 秒` : `${value} ms` }
function formatDate(value) { return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '-' }
function modeLabel(mode) { return mode === 'image_to_image' ? '以图生图' : '文生图' }
function statusLabel(status) { return statusMeta[status]?.label || status }
function statusTagType(status) { return ({ completed: 'success', partial: 'warning', failed: 'danger', cancelled: 'info' })[status] || 'primary' }
onMounted(refreshAll)
</script>

<style scoped>
.dashboard-page{display:grid;gap:28px;min-width:0;color:#1a1a1a}.dashboard-page>*{min-width:0}.page-header,.section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}h1,h2,h3,p{margin:0;letter-spacing:0}h1{font-size:24px;line-height:1.3}h2{font-size:17px;line-height:1.4}h3{font-size:14px;line-height:1.4}.page-header p,.section-heading p{margin-top:4px;color:#6b6560;font-size:13px;line-height:1.5}.stats-row{margin-top:12px}.metric-tile{min-height:92px;box-sizing:border-box;padding:16px;border:1px solid #d9d3cb;border-radius:4px;background:#fffdf9}.metric-tile span,.generation-metric span{display:block;color:#6b6560;font-size:12px}.metric-tile strong{display:block;margin-top:8px;font-size:24px;font-variant-numeric:tabular-nums}.generation-section{display:grid;gap:14px}.generation-content{min-width:0;min-height:280px}.generation-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid #d9d3cb;border-radius:4px;background:#fffdf9}.generation-metric{min-width:0;padding:16px;border-right:1px solid #e5e0da}.generation-metric:last-child{border-right:0}.generation-metric strong{display:block;margin-top:6px;font-size:22px;font-variant-numeric:tabular-nums}.generation-metric small{display:block;margin-top:3px;color:#8a8178;font-size:11px}.operations-grid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(240px,.7fr);gap:12px;margin-top:12px}.status-panel,.provider-panel,.recent-panel{border:1px solid #d9d3cb;border-radius:4px;background:#fffdf9}.status-panel,.provider-panel{padding:16px}.status-list,.provider-list{display:grid;gap:12px;margin:14px 0 0}.status-row>div,.provider-list div{display:flex;justify-content:space-between;gap:12px}.status-row span,.provider-list dt{color:#6b6560;font-size:12px}.status-row strong,.provider-list dd{margin:0;font-size:12px;font-variant-numeric:tabular-nums}.status-row :deep(.el-progress){margin-top:6px}.recent-panel{width:100%;min-width:0;margin-top:12px;overflow-x:auto}.recent-panel h3{padding:16px 16px 10px}.recent-panel :deep(.el-table){--el-table-border-color:#e5e0da;--el-table-header-bg-color:#faf7f2}.recent-panel :deep(.el-table .cell){font-size:12px}.page-header :deep(.el-button),.section-heading :deep(.el-segmented){min-height:40px}
@media(max-width:1100px){.generation-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.generation-metric{border-bottom:1px solid #e5e0da}.operations-grid{grid-template-columns:1fr}}
@media(max-width:900px){.page-header,.section-heading{align-items:stretch;flex-direction:column}.stats-row :deep(.el-col){flex:0 0 50%;max-width:50%;margin-bottom:12px}.generation-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){.dashboard-page{gap:22px}.recent-panel{overflow-x:auto}.recent-panel :deep(.el-table){min-width:840px}}
</style>
