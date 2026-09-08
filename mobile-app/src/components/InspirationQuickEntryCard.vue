<template>
  <article class="inspiration-entry">
    <button type="button" class="entry-main pressable" @click="emit('open')">
      <span class="entry-cover">
        <img v-if="entry.cover_url" :src="resolveMediaUrl(entry.cover_url)" :alt="entry.title" />
        <span v-else class="entry-placeholder"><Sparkles :size="24" aria-hidden="true" /></span>
      </span>
      <span class="entry-copy">
        <span class="entry-meta">灵感草稿</span>
        <strong>{{ entry.title }}</strong>
        <small v-if="entry.summary">{{ entry.summary }}</small>
        <span v-if="generation" class="entry-generation" role="status" aria-live="polite">
          {{ generationLabel }}
        </span>
      </span>
      <ChevronRight :size="20" aria-hidden="true" />
    </button>
    <button
      v-if="canRetry"
      type="button"
      class="entry-retry pressable"
      :disabled="retrying"
      :aria-label="retrying ? '正在重试生成' : '重试失败批次'"
      @click="retry"
    >
      <LoaderCircle v-if="retrying" class="spin" :size="17" aria-hidden="true" />
      <RotateCcw v-else :size="17" aria-hidden="true" />
    </button>
    <button type="button" class="entry-edit pressable" aria-label="编辑灵感" @click="emit('edit')">
      <Pencil :size="17" aria-hidden="true" />
    </button>
  </article>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronRight, LoaderCircle, Pencil, RotateCcw, Sparkles } from 'lucide-vue-next'
import { getApiErrorMessage } from '@/api/client'
import { getInspiration, retryInspirationGeneration } from '@/api/inspirations'
import { resolveMediaUrl } from '@/utils/media'

export interface InspirationQuickEntry {
  inspiration_id: number
  title: string
  summary?: string | null
  cover_url?: string | null
  status: 'draft' | 'saved' | string
  generation?: InspirationQuickGeneration | null
  generation_status?: InspirationQuickGeneration['status']
  total_images?: number
  completed_images?: number
  failed_images?: number
}

interface InspirationQuickGeneration {
  status: 'queued' | 'generating' | 'partial' | 'completed' | 'failed' | 'cancelled' | string
  total_images: number
  completed_images: number
  failed_images: number
  can_retry: boolean
}

const props = defineProps<{ entry: InspirationQuickEntry }>()

const emit = defineEmits<{
  open: []
  edit: []
  error: [message: string]
}>()

const initialGeneration = props.entry.generation || (props.entry.generation_status ? {
  status: props.entry.generation_status,
  total_images: props.entry.total_images || 0,
  completed_images: props.entry.completed_images || 0,
  failed_images: props.entry.failed_images || 0,
  can_retry: props.entry.generation_status === 'partial' || props.entry.generation_status === 'failed',
} : null)
const generation = ref<InspirationQuickGeneration | null>(initialGeneration)
const retrying = ref(false)
const loading = ref(false)
let timer: number | undefined

const generationLabel = computed(() => {
  if (!generation.value) return ''
  const current = generation.value
  if (current.status === 'queued' || current.status === 'generating') return `生成中 · 已完成 ${current.completed_images}/${current.total_images}`
  if (current.status === 'partial') return `部分完成 · ${current.completed_images}/${current.total_images}`
  if (current.status === 'completed') return `已完成 · ${current.completed_images}/${current.total_images}`
  if (current.status === 'failed') return '生成失败'
  return '生成已取消'
})

const canRetry = computed(() => Boolean(generation.value?.can_retry) && !retrying.value)

function stopPolling() {
  if (timer) window.clearInterval(timer)
  timer = undefined
}

function startPolling() {
  stopPolling()
  if (generation.value && ['queued', 'generating'].includes(generation.value.status)) {
    timer = window.setInterval(() => { void refresh() }, 3000)
  }
}

async function refresh() {
  if (!generation.value && !props.entry.generation_status) return
  if (loading.value || document.visibilityState === 'hidden') return
  loading.value = true
  try {
    const current = await getInspiration(props.entry.inspiration_id)
    generation.value = current.generation || null
    if (!generation.value || !['queued', 'generating'].includes(generation.value.status)) stopPolling()
  } catch (error) {
    emit('error', getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function retry() {
  if (retrying.value) return
  retrying.value = true
  try {
    const current = await retryInspirationGeneration(props.entry.inspiration_id)
    generation.value = current.generation || null
    startPolling()
  } catch (error) {
    emit('error', getApiErrorMessage(error))
  } finally {
    retrying.value = false
  }
}

function handleVisibility() {
  if (document.visibilityState === 'visible') {
    void refresh()
    startPolling()
  } else {
    stopPolling()
  }
}

onMounted(() => {
  document.addEventListener('visibilitychange', handleVisibility)
  void refresh()
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibility)
})
</script>

<style scoped>
.inspiration-entry { display: grid; grid-template-columns: minmax(0, 1fr) auto 44px; align-items: center; gap: 8px; width: min(100%, 420px); margin-top: 8px; padding-right: 8px; overflow: hidden; border: 1px solid var(--divider); border-radius: var(--radius-md); background: var(--surface-solid); box-shadow: var(--neu-raise-sm); }
.entry-main { display: grid; grid-template-columns: 76px minmax(0, 1fr) 24px; min-height: 92px; align-items: center; gap: 12px; width: 100%; padding: 8px; border: 0; background: transparent; color: var(--ink); text-align: left; }
.entry-cover { display: grid; width: 76px; height: 76px; overflow: hidden; place-items: center; border-radius: var(--radius-sm); background: var(--brand-soft); color: var(--brand); }
.entry-cover img { width: 100%; height: 100%; object-fit: cover; }
.entry-placeholder { display: grid; place-items: center; }
.entry-copy { display: grid; min-width: 0; gap: 4px; }
.entry-meta { color: var(--brand); font-size: var(--text-2xs); font-weight: 750; }
.entry-copy strong { overflow: hidden; font-size: var(--text-sm); line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.entry-copy small { display: -webkit-box; overflow: hidden; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.entry-generation { color: var(--brand); font-size: var(--text-2xs); line-height: 1.35; }
.entry-main > svg { color: var(--ink-tertiary); }
.entry-retry { display: grid; width: 44px; height: 44px; place-items: center; padding: 0; border: 0; border-radius: 50%; background: var(--brand-soft); color: var(--brand); }
.entry-retry:disabled { opacity: .5; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.entry-edit { display: grid; width: 44px; height: 44px; place-items: center; padding: 0; border: 0; border-radius: 50%; background: var(--paper); color: var(--brand); box-shadow: var(--neu-raise-sm); }
.entry-main:focus-visible, .entry-edit:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
</style>
