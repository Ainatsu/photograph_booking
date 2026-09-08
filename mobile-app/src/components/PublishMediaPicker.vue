<template>
  <div class="media-picker">
    <input
      ref="inputRef"
      :id="inputId"
      class="sr-only"
      type="file"
      :accept="acceptValue"
      :multiple="mode !== 'video'"
      :disabled="disabled"
      @change="selectFiles"
    />

    <div v-if="previews.length" class="preview-grid" aria-label="已选择的媒体文件">
      <article v-for="(item, index) in previews" :key="item.key" class="preview-card">
        <img v-if="item.kind === 'image'" :src="item.url" :alt="item.file.name" />
        <video v-else :src="item.url" controls muted playsinline preload="metadata" />
        <button
          type="button"
          class="remove-media pressable"
          :disabled="disabled"
          :aria-label="`移除 ${item.file.name}`"
          @click="removeFile(index)"
        >
          <X :size="18" aria-hidden="true" />
        </button>
        <span class="media-index">{{ index + 1 }}</span>
        <span class="media-name">{{ item.file.name }}</span>
      </article>
    </div>

    <button
      type="button"
      class="picker-button pressable"
      :disabled="disabled || files.length >= currentLimit"
      @click="inputRef?.click()"
    >
      <ImagePlus v-if="currentKind !== 'video'" :size="21" aria-hidden="true" />
      <Video v-else :size="21" aria-hidden="true" />
      {{ buttonLabel }}
    </button>
    <div class="picker-meta">
      <span>{{ displayCount }}/{{ displayLimit }}</span>
      <small>{{ hint || defaultHint }}</small>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ImagePlus, Video, X } from 'lucide-vue-next'

type MediaKind = 'image' | 'video'
type MediaMode = MediaKind | 'mixed'

interface PreviewItem {
  key: string
  file: File
  kind: MediaKind
  url: string
}

const props = withDefaults(defineProps<{
  files: File[]
  inputId: string
  mode?: MediaMode
  imageLimit?: number
  imageMaxSizeMb?: number
  videoMaxSizeMb?: number
  existingCount?: number
  disabled?: boolean
  hint?: string
}>(), {
  mode: 'image',
  imageLimit: 18,
  imageMaxSizeMb: 10,
  videoMaxSizeMb: 500,
  existingCount: 0,
  disabled: false,
  hint: '',
})

const emit = defineEmits<{
  'update:files': [files: File[]]
  error: [message: string]
}>()

const imageExtensions = new Set(['jpg', 'jpeg', 'png', 'webp'])
const videoExtensions = new Set(['mp4', 'avi', 'mov', 'wmv', 'webm', 'mkv', 'flv'])
const inputRef = ref<HTMLInputElement | null>(null)
const previews = ref<PreviewItem[]>([])

const currentKind = computed<MediaKind>(() => fileKind(props.files[0]) || (props.mode === 'video' ? 'video' : 'image'))
const displayLimit = computed(() => currentKind.value === 'video' ? 1 : props.imageLimit)
const currentLimit = computed(() => currentKind.value === 'video'
  ? 1
  : Math.max(0, props.imageLimit - props.existingCount))
const displayCount = computed(() => props.files.length + (currentKind.value === 'image' ? props.existingCount : 0))
const acceptValue = computed(() => {
  const image = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'
  const video = '.mp4,.avi,.mov,.wmv,.webm,.mkv,.flv,video/mp4,video/webm,video/quicktime'
  return props.mode === 'mixed' ? `${image},${video}` : props.mode === 'video' ? video : image
})
const buttonLabel = computed(() => {
  if (props.mode === 'mixed' && !props.files.length) return '选择图片或视频'
  return currentKind.value === 'video' ? '选择视频' : '选择图片'
})
const defaultHint = computed(() => currentKind.value === 'video'
  ? `单个视频不超过 ${props.videoMaxSizeMb} MB`
  : `支持 JPG、PNG、WebP，单张不超过 ${props.imageMaxSizeMb} MB`)

function extension(file: File) {
  return file.name.split('.').pop()?.toLocaleLowerCase() || ''
}

function fileKind(file?: File): MediaKind | null {
  if (!file) return null
  if (file.type.startsWith('image/') || imageExtensions.has(extension(file))) return 'image'
  if (file.type.startsWith('video/') || videoExtensions.has(extension(file))) return 'video'
  return null
}

function fileKey(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`
}

function revokePreviews() {
  previews.value.forEach((item) => URL.revokeObjectURL(item.url))
}

function syncPreviews() {
  revokePreviews()
  previews.value = props.files.map((file) => ({
    key: fileKey(file),
    file,
    kind: fileKind(file) || 'image',
    url: URL.createObjectURL(file),
  }))
}

function selectFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const candidates = Array.from(input.files || [])
  const next = [...props.files]
  let targetKind = fileKind(next[0])
  let errorMessage = ''

  for (const file of candidates) {
    const kind = fileKind(file)
    if (!kind) {
      errorMessage ||= `${file.name} 的格式不受支持。`
      continue
    }
    if (props.mode !== 'mixed' && kind !== props.mode) {
      errorMessage ||= props.mode === 'image' ? '这里只能选择图片。' : '这里只能选择视频。'
      continue
    }
    targetKind ||= kind
    if (kind !== targetKind) {
      errorMessage ||= '同一作品不能混合图片和视频，请分开发布。'
      continue
    }
    const maxBytes = (kind === 'video' ? props.videoMaxSizeMb : props.imageMaxSizeMb) * 1024 * 1024
    if (file.size > maxBytes) {
      errorMessage ||= `${file.name} 超过 ${kind === 'video' ? props.videoMaxSizeMb : props.imageMaxSizeMb} MB。`
      continue
    }
    if (next.some((item) => fileKey(item) === fileKey(file))) continue
    const limit = kind === 'video' ? 1 : currentLimit.value
    if (next.length >= limit) {
      errorMessage ||= `最多选择 ${limit} 个文件。`
      break
    }
    next.push(file)
  }

  emit('update:files', next)
  if (errorMessage) emit('error', errorMessage)
  input.value = ''
}

function removeFile(index: number) {
  emit('update:files', props.files.filter((_, itemIndex) => itemIndex !== index))
}

watch(() => props.files, syncPreviews, { immediate: true })
onUnmounted(revokePreviews)
</script>

<style scoped>
.media-picker { display: grid; gap: var(--space-3); }
.preview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
.preview-card { position: relative; min-width: 0; overflow: hidden; aspect-ratio: 1 / 1; border: 0; border-radius: var(--radius-md); background: var(--ink); box-shadow: var(--neu-raise); }
.preview-card img, .preview-card video { width: 100%; height: 100%; object-fit: cover; }
.remove-media { position: absolute; top: 4px; right: 4px; display: grid; width: 48px; height: 48px; place-items: center; border: 0; border-radius: 50%; background: rgba(26, 26, 26, .68); color: var(--white); }
.media-index { position: absolute; top: 8px; left: 8px; display: grid; min-width: 24px; height: 24px; place-items: center; border-radius: var(--radius-pill); background: rgba(26, 26, 26, .68); color: var(--white); font-size: var(--text-2xs); font-weight: 800; }
.media-name { position: absolute; right: 0; bottom: 0; left: 0; overflow: hidden; padding: 22px 8px 7px; background: linear-gradient(transparent, rgba(26, 26, 26, .78)); color: var(--white); font-size: var(--text-2xs); text-overflow: ellipsis; white-space: nowrap; }
.picker-button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); font-weight: 750; }
.picker-button:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); opacity: .7; }
.picker-meta { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.picker-meta span { flex: 0 0 auto; color: var(--brand); font-size: var(--text-xs); font-weight: 800; }
.picker-meta small { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.5; text-align: right; }
@media (min-width: 640px) { .preview-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
