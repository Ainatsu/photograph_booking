<template>
  <section class="generation-card" :aria-busy="isActive" aria-live="polite">
    <header>
      <div><span>AI 生成</span><strong>{{ modeLabel }}</strong></div>
      <em :class="`status-${statusTone}`">{{ statusLabel }}</em>
    </header>

    <p v-if="prompt" class="prompt">{{ prompt }}</p>
    <div class="facts">
      <span>{{ String(job?.parameters?.aspect_ratio || '1:1') }}</span>
      <span>{{ job?.progress?.total || 1 }} 张</span>
      <span>{{ job?.parameters?.quality === 'high' ? '高质量' : '标准质量' }}</span>
    </div>

    <div v-if="isActive" class="progress" role="status">
      <LoaderCircle :size="20" class="spin" aria-hidden="true" />
      <div><strong>{{ stageLabel }}</strong><span>{{ progressText }}</span></div>
    </div>

    <div v-if="sourceImages.length" class="source-strip">
      <span>参考图</span>
      <img v-for="asset in sourceImages" :key="asset.id" :src="mediaUrl(asset.thumbnail_url || asset.storage_url)" alt="图片生成参考图" loading="lazy" />
    </div>

    <div v-if="resultImages.length" class="results" :class="{ comparison: isComparison }">
      <button v-for="(asset, index) in resultImages" :key="asset.id" type="button" class="result pressable" :style="{ aspectRatio: resultAspectRatio }" @click="openAsset(asset.storage_url)">
        <img :src="mediaUrl(asset.thumbnail_url || asset.storage_url)" :alt="`AI 生成结果 ${index + 1}`" loading="lazy" />
      </button>
    </div>

    <div v-if="job?.error" class="error" role="alert">
      <AlertCircle :size="18" aria-hidden="true" /><span>{{ errorMessage }}</span>
    </div>

    <footer>
      <button v-if="resultImages.length" type="button" class="action pressable" @click="openAsset(resultImages[0].storage_url)"><Expand :size="17" /><span>查看</span></button>
      <button v-if="resultImages.length" type="button" class="action pressable" @click="downloadAsset(resultImages[0].storage_url)"><Download :size="17" /><span>下载</span></button>
      <button v-if="job?.can_retry" type="button" class="action pressable" :disabled="actionBusy" @click="retry"><RotateCw :size="17" /><span>重试</span></button>
      <button v-if="canRegenerate" type="button" class="action pressable" @click="$emit('regenerate', regenerationPayload)"><Sparkles :size="17" /><span>重新生成</span></button>
      <button v-if="job?.can_cancel" type="button" class="action pressable" :disabled="actionBusy" @click="cancel"><X :size="17" /><span>取消</span></button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { AlertCircle, Download, Expand, LoaderCircle, RotateCw, Sparkles, X } from 'lucide-vue-next'
import { cancelImageGeneration, getImageGeneration, retryImageGeneration, type AIImageGenerationJob } from '@/api/ai'
import { resolveMediaUrl } from '@/utils/media'

const props = defineProps<{ reference: { job_id: number; mode: string; status?: string }; prompt?: string }>()
const emit = defineEmits<{ regenerate: [payload: { mode: string; prompt: string; parameters: Record<string, unknown>; sourceImages: AIImageGenerationJob['source_images'] }]; error: [message: string] }>()

const job = ref<AIImageGenerationJob | null>(null)
const actionBusy = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null
const activeStatuses = new Set(['queued', 'generating', 'retry_wait'])
const isActive = computed(() => activeStatuses.has(job.value?.status || props.reference.status || 'queued'))
const sourceImages = computed(() => job.value?.source_images || [])
const resultImages = computed(() => job.value?.result_images || [])
const isComparison = computed(() => job.value?.mode === 'image_to_image' && resultImages.value.length === 1)
const resultAspectRatio = computed(() => ({ '1:1': '1 / 1', '3:4': '3 / 4', '4:3': '4 / 3', '9:16': '9 / 16', '16:9': '16 / 9' }[String(job.value?.parameters?.aspect_ratio || '1:1')] || '1 / 1'))
const canRegenerate = computed(() => Boolean(job.value && !isActive.value))
const modeLabel = computed(() => (job.value?.mode || props.reference.mode) === 'image_to_image' ? '以图生图' : '文生图')
const statusTone = computed(() => ({ completed: 'success', partial: 'warning', failed: 'danger', cancelled: 'muted' }[job.value?.status || ''] || 'primary'))
const statusLabel = computed(() => ({ queued: '等待生成', generating: '生成中', retry_wait: '等待重试', completed: '已完成', partial: '部分完成', failed: '生成失败', cancelled: '已取消' }[job.value?.status || props.reference.status || ''] || '载入中'))
const stageLabel = computed(() => ({ queued: '等待生成', validating_input: '正在校验输入', preparing_request: '正在准备请求', calling_provider: '正在提交模型', saving_assets: '正在保存图片', retry_wait: '服务繁忙，等待重试' }[job.value?.stage || 'queued'] || '正在生成'))
const progressText = computed(() => `${job.value?.progress.completed || 0} / ${job.value?.progress.total || 1} 张已完成`)
const errorMessage = computed(() => ({ provider_unavailable: '图像服务暂时不可用，可点击重试。', invalid_provider_image: '上游返回的图片无效，可点击重试。', asset_save_failed: '部分图片保存失败，可点击重试。' }[job.value?.error?.code || ''] || job.value?.error?.message || '图片生成失败，请调整描述后重新生成。'))
const regenerationPayload = computed(() => ({ mode: job.value?.mode || props.reference.mode, prompt: props.prompt || '', parameters: job.value?.parameters || {}, sourceImages: sourceImages.value }))

function mediaUrl(url?: string | null) { return resolveMediaUrl(url || '') }
function clearPoll() { if (pollTimer) clearTimeout(pollTimer); pollTimer = null }
function schedulePoll() { clearPoll(); if (isActive.value && document.visibilityState === 'visible') pollTimer = setTimeout(loadJob, 2000) }
async function loadJob() { clearPoll(); try { job.value = await getImageGeneration(props.reference.job_id) } catch { if (!job.value) emit('error', '生成任务状态加载失败，请稍后刷新') } finally { schedulePoll() } }
async function retry() { actionBusy.value = true; try { job.value = await retryImageGeneration(props.reference.job_id); schedulePoll() } catch { emit('error', '任务暂时无法重试') } finally { actionBusy.value = false } }
async function cancel() { actionBusy.value = true; try { job.value = await cancelImageGeneration(props.reference.job_id); schedulePoll() } catch { emit('error', '任务暂时无法取消') } finally { actionBusy.value = false } }
function openAsset(url: string) { window.open(mediaUrl(url), '_blank', 'noopener,noreferrer') }
function downloadAsset(url: string) { const link = document.createElement('a'); link.href = mediaUrl(url); link.download = `ai-generation-${props.reference.job_id}.jpg`; link.click() }
function onVisibilityChange() { if (document.visibilityState === 'visible') void loadJob(); else clearPoll() }

watch(() => props.reference.job_id, loadJob)
onMounted(() => { document.addEventListener('visibilitychange', onVisibilityChange); void loadJob() })
onBeforeUnmount(() => { clearPoll(); document.removeEventListener('visibilitychange', onVisibilityChange) })
</script>

<style scoped>
.generation-card { width: 100%; margin-top: 8px; padding: 14px; border: 1px solid var(--divider); border-radius: var(--radius-md); background: var(--surface-solid); box-shadow: var(--shadow-1); }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; } header div { display: grid; gap: 2px; } header span { color: var(--ink-tertiary); font-size: var(--text-xs); } header strong { color: var(--ink); font-size: var(--text-sm); } header em { padding: 3px 8px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-size: var(--text-xs); font-style: normal; }
.status-success { color: var(--success); }.status-warning { color: var(--warning); }.status-danger { color: var(--danger); }.status-muted { color: var(--ink-tertiary); }
.prompt { margin: 10px 0 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.55; }.facts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }.facts span { padding: 3px 7px; border-radius: var(--radius-sm); background: var(--paper); color: var(--ink-secondary); font-size: var(--text-xs); }
.progress,.error { display: flex; align-items: center; gap: 10px; margin-top: 12px; padding: 10px; border-radius: var(--radius-sm); background: var(--paper); }.progress > div { display: grid; gap: 2px; }.progress strong { color: var(--ink); font-size: var(--text-sm); }.progress span { color: var(--ink-tertiary); font-size: var(--text-xs); }.progress svg { color: var(--brand); }.error { color: var(--danger); font-size: var(--text-xs); }
.spin { animation: generation-spin 1s linear infinite; } @keyframes generation-spin { to { transform: rotate(360deg); } }
.source-strip { display: flex; align-items: center; gap: 8px; margin-top: 12px; color: var(--ink-tertiary); font-size: var(--text-xs); }.source-strip img { width: 52px; height: 52px; border-radius: var(--radius-sm); object-fit: cover; }
.results { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }.results.comparison { grid-template-columns: 1fr; }.result { width: 100%; padding: 0; overflow: hidden; border: 0; border-radius: var(--radius-sm); background: var(--paper); }.result img { width: 100%; height: 100%; object-fit: cover; }
footer { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }.action { display: inline-flex; min-width: 88px; min-height: 44px; flex: 1 1 auto; align-items: center; justify-content: center; gap: 6px; padding: 0 10px; border: 1px solid var(--divider); border-radius: var(--radius-sm); background: var(--paper); color: var(--brand); font: inherit; font-size: var(--text-xs); }.action:disabled { opacity: .42; }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
</style>
