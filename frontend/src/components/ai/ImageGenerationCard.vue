<template>
  <section class="generation-card" :aria-busy="isActive" aria-live="polite">
    <header class="generation-header">
      <div>
        <span class="generation-kicker">AI 生成</span>
        <strong>{{ modeLabel }}</strong>
      </div>
      <span class="generation-status" :class="`status-${statusTone}`">{{ statusLabel }}</span>
    </header>

    <p v-if="prompt" class="generation-prompt">{{ prompt }}</p>
    <dl class="generation-facts">
      <div><dt>比例</dt><dd>{{ job?.parameters?.aspect_ratio || '1:1' }}</dd></div>
      <div><dt>数量</dt><dd>{{ job?.progress?.total || 1 }} 张</dd></div>
      <div v-if="job?.parameters?.quality"><dt>质量</dt><dd>{{ job.parameters.quality === 'high' ? '高' : '标准' }}</dd></div>
    </dl>

    <div v-if="isActive" class="generation-progress" role="status">
      <LoaderCircle class="spin" aria-hidden="true" />
      <div>
        <strong>{{ stageLabel }}</strong>
        <span>{{ progressText }}</span>
      </div>
    </div>

    <div v-if="sourceImages.length" class="source-strip">
      <span>参考图</span>
      <img
        v-for="asset in sourceImages"
        :key="asset.id"
        :src="asset.thumbnail_url || asset.storage_url"
        alt="图片生成参考图"
        loading="lazy"
      />
    </div>

    <div v-if="resultImages.length" class="result-grid" :class="{ 'is-comparison': isComparison }">
      <figure v-for="(asset, index) in resultImages" :key="asset.id" :style="{ aspectRatio: resultAspectRatio }">
        <el-image
          :src="asset.thumbnail_url || asset.storage_url"
          :preview-src-list="resultImages.map(item => item.storage_url)"
          :initial-index="index"
          fit="cover"
          loading="lazy"
          :alt="`AI 生成结果 ${index + 1}`"
        />
      </figure>
    </div>

    <div v-if="job?.error" class="generation-error" role="alert">
      <AlertCircle aria-hidden="true" />
      <span>{{ errorMessage }}</span>
    </div>

    <footer class="generation-actions">
      <el-button v-if="resultImages.length" :icon="Expand" @click="openFirstResult">查看大图</el-button>
      <el-button v-if="resultImages.length" :icon="Download" @click="downloadFirstResult">下载</el-button>
      <el-button v-if="job?.can_retry" :icon="RotateCw" :loading="actionBusy" @click="retry">重试</el-button>
      <el-button v-if="canRegenerate" :icon="Sparkles" @click="$emit('regenerate', regenerationPayload)">重新生成</el-button>
      <el-button v-if="job?.can_cancel" :icon="X" :loading="actionBusy" @click="cancel">取消</el-button>
    </footer>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { AlertCircle, Download, Expand, LoaderCircle, RotateCw, Sparkles, X } from 'lucide-vue-next'
import { cancelImageGeneration, getImageGeneration, retryImageGeneration } from '../../api/ai'

const props = defineProps({
  reference: { type: Object, required: true },
  prompt: { type: String, default: '' },
})

defineEmits(['regenerate'])

const job = ref(null)
const actionBusy = ref(false)
let pollTimer = null

const activeStatuses = new Set(['queued', 'generating', 'retry_wait'])
const isActive = computed(() => activeStatuses.has(job.value?.status || props.reference?.status))
const sourceImages = computed(() => job.value?.source_images || [])
const resultImages = computed(() => job.value?.result_images || [])
const isComparison = computed(() => job.value?.mode === 'image_to_image' && resultImages.value.length === 1)
const resultAspectRatio = computed(() => ({ '1:1': '1 / 1', '3:4': '3 / 4', '4:3': '4 / 3', '9:16': '9 / 16', '16:9': '16 / 9' }[job.value?.parameters?.aspect_ratio] || '1 / 1'))
const canRegenerate = computed(() => Boolean(job.value && !isActive.value))
const modeLabel = computed(() => (job.value?.mode || props.reference?.mode) === 'image_to_image' ? '以图生图' : '文生图')
const statusTone = computed(() => ({ completed: 'success', partial: 'warning', failed: 'danger', cancelled: 'muted' }[job.value?.status] || 'primary'))
const statusLabel = computed(() => ({
  queued: '等待生成', generating: '生成中', retry_wait: '等待重试', completed: '已完成',
  partial: '部分完成', failed: '生成失败', cancelled: '已取消',
}[job.value?.status || props.reference?.status] || '载入中'))
const stageLabel = computed(() => ({
  queued: '等待生成', validating_input: '正在校验输入', preparing_request: '正在准备请求',
  calling_provider: '正在提交模型', saving_assets: '正在保存图片', retry_wait: '服务繁忙，等待重试',
}[job.value?.stage || 'queued'] || '正在生成'))
const progressText = computed(() => `${job.value?.progress?.completed || 0} / ${job.value?.progress?.total || 1} 张已完成`)
const errorMessage = computed(() => {
  const code = job.value?.error?.code
  const labels = {
    provider_unavailable: '图像服务暂时不可用，可点击重试。',
    invalid_provider_image: '上游返回的图片无效，可点击重试。',
    asset_save_failed: '部分图片保存失败，可点击重试。',
  }
  return labels[code] || job.value?.error?.message || '图片生成失败，请调整描述后重新生成。'
})
const regenerationPayload = computed(() => ({
  mode: job.value?.mode || props.reference?.mode,
  prompt: props.prompt,
  parameters: job.value?.parameters || {},
  sourceImages: sourceImages.value,
}))

function clearPoll() {
  if (pollTimer) window.clearTimeout(pollTimer)
  pollTimer = null
}

function schedulePoll() {
  clearPoll()
  if (!isActive.value || document.visibilityState !== 'visible') return
  pollTimer = window.setTimeout(loadJob, 2000)
}

async function loadJob() {
  clearPoll()
  try {
    const response = await getImageGeneration(props.reference.job_id)
    job.value = response.data
  } catch {
    if (!job.value) ElMessage.error('生成任务状态加载失败，请稍后刷新')
  } finally {
    schedulePoll()
  }
}

async function retry() {
  actionBusy.value = true
  try {
    job.value = (await retryImageGeneration(props.reference.job_id)).data
    schedulePoll()
  } catch {
    ElMessage.error('任务暂时无法重试')
  } finally {
    actionBusy.value = false
  }
}

async function cancel() {
  actionBusy.value = true
  try {
    job.value = (await cancelImageGeneration(props.reference.job_id)).data
    schedulePoll()
  } catch {
    ElMessage.error('任务暂时无法取消')
  } finally {
    actionBusy.value = false
  }
}

function openFirstResult() {
  window.open(resultImages.value[0]?.storage_url, '_blank', 'noopener,noreferrer')
}

function downloadFirstResult() {
  const link = document.createElement('a')
  link.href = resultImages.value[0]?.storage_url
  link.download = `ai-generation-${props.reference.job_id}.jpg`
  link.click()
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') void loadJob()
  else clearPoll()
}

watch(() => props.reference.job_id, loadJob)
onMounted(() => {
  document.addEventListener('visibilitychange', onVisibilityChange)
  void loadJob()
})
onBeforeUnmount(() => {
  clearPoll()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<style scoped>
.generation-card { width: min(100%, 560px); margin-top: 8px; padding: 14px; border: var(--border-default); border-radius: var(--radius-md); background: var(--color-paper); box-shadow: var(--shadow-xs); }
.generation-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.generation-header > div { display: grid; gap: 2px; }
.generation-kicker { color: var(--color-ink-tertiary); font-size: calc(var(--text-xs) * 1rem); }
.generation-header strong { color: var(--color-ink); font-size: calc(var(--text-sm) * 1rem); }
.generation-status { flex: 0 0 auto; padding: 3px 8px; border-radius: 999px; background: var(--color-brand-light); color: var(--color-brand); font-size: calc(var(--text-xs) * 1rem); }
.status-success { color: var(--color-success); }.status-warning { color: var(--color-warning); }.status-danger { color: var(--color-danger); }.status-muted { color: var(--color-ink-tertiary); }
.generation-prompt { margin: 10px 0 0; color: var(--color-ink-secondary); font-size: calc(var(--text-sm) * 1rem); line-height: 1.55; }
.generation-facts { display: flex; flex-wrap: wrap; gap: 14px; margin: 10px 0 0; }
.generation-facts div { display: flex; gap: 4px; font-size: calc(var(--text-xs) * 1rem); }.generation-facts dt { color: var(--color-ink-tertiary); }.generation-facts dd { margin: 0; color: var(--color-ink); font-weight: 600; }
.generation-progress,.generation-error { display: flex; align-items: center; gap: 10px; margin-top: 12px; padding: 10px; border-radius: var(--radius-sm); background: var(--color-paper-light); color: var(--color-ink-secondary); }
.generation-progress svg,.generation-error svg { width: 20px; height: 20px; flex: 0 0 auto; color: var(--color-brand); }.generation-progress > div { display: grid; gap: 2px; }.generation-progress strong { color: var(--color-ink); font-size: calc(var(--text-sm) * 1rem); }.generation-progress span { font-size: calc(var(--text-xs) * 1rem); }
.generation-error { color: var(--color-danger); font-size: calc(var(--text-xs) * 1rem); }.generation-error svg { color: currentColor; }
.spin { animation: generation-spin 1s linear infinite; } @keyframes generation-spin { to { transform: rotate(360deg); } }
.source-strip { display: flex; align-items: center; gap: 8px; margin-top: 12px; color: var(--color-ink-tertiary); font-size: calc(var(--text-xs) * 1rem); }.source-strip img { width: 52px; height: 52px; border-radius: var(--radius-sm); object-fit: cover; }
.result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }.result-grid figure { margin: 0; overflow: hidden; border-radius: var(--radius-sm); background: var(--color-paper-light); }.result-grid :deep(.el-image) { width: 100%; height: 100%; }.result-grid.is-comparison { grid-template-columns: 1fr; }
.generation-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }.generation-actions :deep(.el-button) { min-height: 44px; margin: 0; }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
@media (max-width: 520px) { .generation-card { padding: 12px; }.result-grid { grid-template-columns: 1fr; }.generation-actions :deep(.el-button) { flex: 1 1 calc(50% - 4px); } }
</style>
