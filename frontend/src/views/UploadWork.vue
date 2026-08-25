<template>
  <div class="upload-work-page">
    <header class="page-header">
      <button class="back-btn" type="button" @click="goBack">
        <span aria-hidden="true">&lt;</span>
        <span>返回</span>
      </button>
      <h1 class="page-title">{{ draftId ? '编辑草稿' : '发布作品' }}</h1>
    </header>

    <section class="media-panel">
      <div class="panel-head">
        <span class="media-count">
          {{ currentMediaType === 'image' ? `${selectedFiles.length}/${MAX_IMAGE_COUNT}` : selectedFiles.length ? '已选择视频' : '未选择视频' }}
        </span>
      </div>

      <div class="media-strip-wrap">
        <div ref="mediaRailRef" class="media-strip" @wheel.prevent="handleMediaWheel">
          <div v-for="(item, index) in previewItems" :key="item.id" class="media-card preview-card">
            <img v-if="currentMediaType === 'image'" :src="item.url" alt="" class="preview-media" />
            <template v-else>
              <img
                v-if="videoCoverPreviewUrl"
                :src="videoCoverPreviewUrl"
                alt=""
                class="preview-media"
              />
              <video v-else :src="item.url" class="preview-media" muted preload="metadata" />
              <button
                class="cover-card-btn"
                type="button"
                title="选择封面"
                aria-label="选择视频封面"
                @click.stop="openCoverPicker"
              >
                <el-icon><Picture /></el-icon>
              </button>
            </template>
            <button class="remove-card-btn" type="button" title="移除" aria-label="移除文件" @click="removeFile(index)">
              <el-icon><Close /></el-icon>
            </button>
            <span class="card-index">{{ index + 1 }}</span>
          </div>

          <el-upload
            v-if="canAddMore"
            ref="uploadRef"
            v-model:file-list="uploadFileList"
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :show-file-list="false"
            :multiple="uploadKind !== 'video'"
            :limit="uploadKind === 'video' ? 1 : MAX_IMAGE_COUNT"
            :accept="uploadAccept"
            :on-exceed="handleExceed"
            class="add-upload"
          >
            <button class="media-card add-card" type="button">
              <el-icon><Plus /></el-icon>
              <span>{{ uploadKind === 'video' ? '添加视频' : uploadKind === 'image' ? '添加图片' : '添加作品' }}</span>
            </button>
          </el-upload>
        </div>
      </div>

      <input
        ref="coverInputRef"
        class="cover-file-input"
        type="file"
        accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
        @change="handleCoverChange"
      >
    </section>

    <section class="info-panel">
      <div class="field-block">
        <label class="field-label" for="work-title">作品标题</label>
        <el-input id="work-title" v-model="workTitle" placeholder="如：春日写真系列" size="large" />
      </div>

      <div class="field-block">
        <label class="field-label">风格标签</label>
        <TagInput v-model="workTags" placeholder="输入风格后按回车添加，如：日系" />
      </div>

      <div class="field-block">
        <label class="field-label" for="work-desc">描述</label>
        <el-input id="work-desc" v-model="workDesc" type="textarea" :rows="5" resize="none" placeholder="作品描述" />
      </div>

    </section>

    <section class="action-panel">
      <div v-if="uploading" class="progress-wrap">
        <el-progress :percentage="uploadPercent" :status="uploadStatus" :stroke-width="14" />
        <span class="progress-text">{{ uploadStatusText }}</span>
      </div>

      <div class="action-row">
        <el-button
          type="primary"
          size="large"
          class="publish-btn"
          :loading="uploading"
          :disabled="!selectedFiles.length"
          @click="uploadWork"
        >
          发布作品
        </el-button>
        <el-button
          size="large"
          class="placeholder-btn"
          :loading="savingDraft"
          :disabled="uploading"
          @click="saveDraft"
        >
          <el-icon><FolderChecked /></el-icon>
          {{ draftId ? '更新草稿' : '保存草稿' }}
        </el-button>
        <el-button size="large" class="placeholder-btn" @click="showPlaceholder('定时发布')">
          <el-icon><Calendar /></el-icon>
          定时发布
        </el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, toRaw } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Calendar, FolderCheck as FolderChecked, Image as Picture, Plus, X as Close } from 'lucide-vue-next'
import api from '../utils/api'
import TagInput from '../components/TagInput.vue'
import { deleteWorkDraft, getWorkDraft, saveWorkDraft } from '../utils/workDrafts'

defineOptions({ name: 'UploadWork' })

const router = useRouter()
const route = useRoute()
const MAX_IMAGE_COUNT = 18
const draftId = ref('')
const uploadKind = ref(null)
const uploadRef = ref(null)
const coverInputRef = ref(null)
const mediaRailRef = ref(null)
const uploadFileList = ref([])
const selectedFiles = ref([])
const previewItems = ref([])
const videoCoverFile = ref(null)
const videoCoverPreviewUrl = ref('')
const workTitle = ref('')
const workTags = ref([])
const workDesc = ref('')
const uploading = ref(false)
const savingDraft = ref(false)
const uploadPercent = ref(0)
const uploadStatus = ref('')
const uploadStatusText = ref('')

const currentMediaType = computed(() => uploadKind.value || 'image')

const uploadAccept = computed(() => (
  uploadKind.value === 'image'
    ? 'image/*'
    : uploadKind.value === 'video'
      ? '.mp4,.avi,.mov,.wmv,.webm,.mkv,.flv'
      : 'image/*,.mp4,.avi,.mov,.wmv,.webm,.mkv,.flv'
))

const getFileKind = (file) => {
  if (!file) return null
  if (file.type?.startsWith('image/')) return 'image'
  if (file.type?.startsWith('video/')) return 'video'
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (['jpg', 'jpeg', 'png', 'webp'].includes(ext)) return 'image'
  if (['mp4', 'avi', 'mov', 'wmv', 'webm', 'mkv', 'flv'].includes(ext)) return 'video'
  return null
}

const syncSelectedFiles = (fileList = []) => {
  const rawFiles = fileList.map((item) => item.raw).filter(Boolean)
  if (!rawFiles.length) {
    uploadKind.value = null
    uploadFileList.value = []
    selectedFiles.value = []
    clearVideoCover()
    syncPreviewItems()
    return
  }

  const nextKind = uploadKind.value || getFileKind(rawFiles[0]) || 'image'
  uploadKind.value = nextKind

  selectedFiles.value = rawFiles
    .filter((file) => getFileKind(file) === nextKind)
    .slice(0, nextKind === 'image' ? MAX_IMAGE_COUNT : 1)
  uploadFileList.value = uploadFileList.value
    .filter((item) => selectedFiles.value.includes(item.raw))
  if (nextKind !== 'video' || !selectedFiles.value.length) {
    clearVideoCover()
  }
  syncPreviewItems()
}

const resetUploadFiles = () => {
  revokePreviewItems()
  uploadKind.value = null
  uploadFileList.value = []
  selectedFiles.value = []
  previewItems.value = []
  clearVideoCover()
  uploadRef.value?.clearFiles?.()
}

const handleFileChange = (_file, fileList) => {
  syncSelectedFiles(fileList)
  uploadPercent.value = 0
  uploadStatus.value = ''
  uploadStatusText.value = ''
}

const handleFileRemove = (_file, fileList) => {
  syncSelectedFiles(fileList)
}

const removeFile = (index) => {
  uploadFileList.value = uploadFileList.value.filter((_, itemIndex) => itemIndex !== index)
  syncSelectedFiles(uploadFileList.value)
  if (!selectedFiles.value.length) {
    uploadKind.value = null
  }
}

const handleExceed = () => {
  const limit = uploadKind.value === 'video' ? 1 : MAX_IMAGE_COUNT
  ElMessage.warning(`最多选择 ${limit} 个文件`)
}

const canAddMore = computed(() => {
  return currentMediaType.value === 'image'
    ? selectedFiles.value.length < MAX_IMAGE_COUNT
    : selectedFiles.value.length < 1
})

const getFileKey = (file, index) => `${file.name}-${file.size}-${file.lastModified || 0}-${index}`

const revokePreviewItems = () => {
  previewItems.value.forEach((item) => {
    if (item.url) URL.revokeObjectURL(item.url)
  })
}

const revokeVideoCoverPreview = () => {
  if (videoCoverPreviewUrl.value) {
    URL.revokeObjectURL(videoCoverPreviewUrl.value)
    videoCoverPreviewUrl.value = ''
  }
}

const clearVideoCover = () => {
  revokeVideoCoverPreview()
  videoCoverFile.value = null
  if (coverInputRef.value) {
    coverInputRef.value.value = ''
  }
}

const validateCoverFile = (file) => {
  const ext = file.name.split('.').pop()?.toLowerCase()
  const allowedCoverExts = ['jpg', 'jpeg', 'png', 'webp']
  if (!allowedCoverExts.includes(ext)) {
    ElMessage.error('封面图片仅支持 JPG/PNG/WebP')
    return false
  }
  if (file.type && !file.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件作为封面')
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('封面图片不能超过 20MB')
    return false
  }
  return true
}

const openCoverPicker = () => {
  if (uploading.value) return
  coverInputRef.value?.click()
}

const handleCoverChange = (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  if (!validateCoverFile(file)) {
    event.target.value = ''
    return
  }
  revokeVideoCoverPreview()
  videoCoverFile.value = file
  videoCoverPreviewUrl.value = URL.createObjectURL(file)
  event.target.value = ''
}

const syncPreviewItems = () => {
  revokePreviewItems()
  previewItems.value = selectedFiles.value.map((file, index) => ({
    id: getFileKey(file, index),
    name: file.name,
    url: URL.createObjectURL(file),
  }))
}

const handleMediaWheel = (event) => {
  if (!mediaRailRef.value) return
  const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
  mediaRailRef.value.scrollLeft += delta
}

const showPlaceholder = (label) => {
  ElMessage.info(`${label}功能暂未实现`)
}

const getRouteDraftId = () => {
  const value = route.query.draftId
  return Array.isArray(value) ? value[0] : value
}

const parseTokenUserId = () => {
  const token = localStorage.getItem('token')
  if (!token) return ''
  try {
    const base64 = token.split('.')[1]?.replace(/-/g, '+').replace(/_/g, '/')
    if (!base64) return ''
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
    const payload = JSON.parse(atob(padded))
    return payload.sub || payload.user_id || payload.id || ''
  } catch {
    return ''
  }
}

const resolveCurrentUserId = async () => {
  const tokenUserId = parseTokenUserId()
  if (tokenUserId) return tokenUserId

  const res = await api.get('/users/me', { skipErrorHandler: true })
  return res.data?.id || ''
}

const getStorableFiles = () => selectedFiles.value
  .map((file, index) => {
    const rawFile = toRaw(file)
    if (!rawFile) return null
    if (rawFile instanceof File) {
      return new File([rawFile], rawFile.name || `作品文件${index + 1}`, {
        type: rawFile.type || '',
        lastModified: rawFile.lastModified || Date.now(),
      })
    }
    if (rawFile instanceof Blob) {
      return new File([rawFile], rawFile.name || `作品文件${index + 1}`, {
        type: rawFile.type || '',
        lastModified: Date.now(),
      })
    }
    return null
  })
  .filter(Boolean)

const getStorableVideoCoverFile = () => {
  const rawFile = toRaw(videoCoverFile.value)
  if (!rawFile) return null
  if (rawFile instanceof File) {
    return new File([rawFile], rawFile.name || '视频封面', {
      type: rawFile.type || '',
      lastModified: rawFile.lastModified || Date.now(),
    })
  }
  if (rawFile instanceof Blob) {
    return new File([rawFile], rawFile.name || '视频封面', {
      type: rawFile.type || '',
      lastModified: Date.now(),
    })
  }
  return null
}

const hasDraftContent = computed(() => (
  selectedFiles.value.length > 0
  || workTitle.value.trim()
  || workDesc.value.trim()
  || workTags.value.length > 0
))

const restoreDraft = async () => {
  const id = getRouteDraftId()
  if (!id) return

  try {
    const draft = await getWorkDraft(id)
    if (!draft) {
      ElMessage.warning('草稿不存在或已被删除')
      return
    }

    draftId.value = draft.id
    uploadKind.value = draft.mediaType || null
    workTitle.value = draft.title || ''
    workTags.value = Array.isArray(draft.tags) ? draft.tags : []
    workDesc.value = draft.description || ''
    selectedFiles.value = Array.isArray(draft.files) ? draft.files : []
    videoCoverFile.value = draft.coverFile || null
    if (videoCoverFile.value) {
      revokeVideoCoverPreview()
      videoCoverPreviewUrl.value = URL.createObjectURL(videoCoverFile.value)
    }
    uploadFileList.value = selectedFiles.value.map((file, index) => ({
      name: file.name || `作品文件${index + 1}`,
      size: file.size || 0,
      uid: `${draft.id}-${index}-${file.lastModified || 0}`,
      status: 'ready',
      raw: file,
    }))
    if (selectedFiles.value.length) {
      uploadKind.value = draft.mediaType || getFileKind(selectedFiles.value[0]) || 'image'
    }
    syncPreviewItems()
  } catch {
    ElMessage.error('草稿读取失败')
  }
}

const saveDraft = async () => {
  if (!hasDraftContent.value) {
    ElMessage.warning('请先添加作品内容再保存草稿')
    return
  }

  savingDraft.value = true
  try {
    const userId = await resolveCurrentUserId()
    if (!userId) {
      ElMessage.warning('请先登录后再保存草稿')
      return
    }

    const draft = await saveWorkDraft({
      id: draftId.value,
      userId,
      mediaType: currentMediaType.value,
      title: workTitle.value,
      tags: workTags.value,
      description: workDesc.value,
      files: getStorableFiles(),
      coverFile: currentMediaType.value === 'video' ? getStorableVideoCoverFile() : null,
    })
    draftId.value = draft.id
    ElMessage.success('草稿已保存')
    router.push({ path: '/profile', query: { tab: 'works' } })
  } catch (error) {
    if (error?.name === 'QuotaExceededError') {
      ElMessage.error('浏览器本地空间不足，草稿保存失败')
    } else if (error?.name === 'DataCloneError') {
      ElMessage.error('当前文件无法保存为草稿，请重新选择后再试')
    } else {
      ElMessage.error('草稿保存失败，请稍后重试')
    }
  } finally {
    savingDraft.value = false
  }
}

const validateVideoFile = (file) => {
  const ext = file.name.split('.').pop()?.toLowerCase()
  const allowedVideoExts = ['mp4', 'avi', 'mov', 'wmv', 'webm', 'mkv', 'flv']
  if (!allowedVideoExts.includes(ext)) {
    ElMessage.error(`Unsupported video format .${ext}. Please upload ${allowedVideoExts.join('/')} files.`)
    return false
  }
  if (file.size > 500 * 1024 * 1024) {
    ElMessage.error('Video files cannot exceed 500MB')
    return false
  }
  return true
}

const uploadWork = async () => {
  if (!selectedFiles.value.length) return

  const isVideo = currentMediaType.value === 'video'
  const uploadFiles = selectedFiles.value

  if (isVideo && !validateVideoFile(uploadFiles[0])) return
  if (!isVideo && uploadFiles.length > MAX_IMAGE_COUNT) {
    ElMessage.error(`Upload up to ${MAX_IMAGE_COUNT} images`)
    return
  }

  uploading.value = true
  uploadPercent.value = 0
  uploadStatus.value = ''
  uploadStatusText.value = 'Preparing upload...'

  try {
    const fd = new FormData()
    if (isVideo) {
      fd.append('file', uploadFiles[0])
      if (videoCoverFile.value) {
        fd.append('cover', videoCoverFile.value)
      }
    } else {
      uploadFiles.forEach((file) => fd.append('files', file))
    }
    fd.append('title', workTitle.value)
    fd.append('tag', workTags.value.join(','))
    fd.append('description', workDesc.value)

    const endpoint = isVideo
      ? '/photographers/video/upload'
      : '/photographers/portfolio/upload'

    if (isVideo) fd.append('compress', 'true')

    uploadStatusText.value = 'Uploading...'

    await api.post(endpoint, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100)
          uploadPercent.value = percent
          uploadStatusText.value = `Uploading ${percent}%`
        }
      },
    })

    uploadPercent.value = 100
    uploadStatus.value = 'success'
    uploadStatusText.value = isVideo
      ? 'Video uploaded. Processing in the background...'
      : 'Upload complete'

    ElMessage.success('Work published')
    if (draftId.value) {
      await deleteWorkDraft(draftId.value)
      draftId.value = ''
    }
    workTitle.value = ''
    workTags.value = []
    workDesc.value = ''
    resetUploadFiles()
    router.push('/works')
  } catch {
    uploadStatus.value = 'exception'
    uploadStatusText.value = 'Upload failed. Please retry.'
  } finally {
    uploading.value = false
  }
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  restoreDraft()
})

onUnmounted(() => {
  revokePreviewItems()
  revokeVideoCoverPreview()
})
</script>

<style scoped>
.upload-work-page {
  box-sizing: border-box;
  width: min(1120px, calc(100vw - 48px));
  margin: 28px auto 56px;
  color: var(--color-ink);
}
.page-header {
  display: flex;
  align-items: center;
  gap: 28px;
  margin-bottom: 26px;
}
.back-btn {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--color-ink-tertiary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: inherit;
  font-size: calc(var(--text-base) * 1rem);
  padding: var(--space-2) 0;
  transition: color 0.15s;
}
.back-btn:hover {
  color: var(--color-brand);
}
.page-title {
  font-size: calc(var(--text-3xl) * 1rem);
  line-height: 1.2;
  font-weight: 800;
  margin: 0;
  color: var(--color-ink);
}

.info-panel,
.action-panel {
  box-sizing: border-box;
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
}

.media-panel {
  padding: var(--space-1) 0 var(--space-2);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-4);
  margin-bottom: 10px;
}

.media-count {
  font-size: calc(var(--text-sm) * 1rem);
  color: var(--color-ink-tertiary);
  white-space: nowrap;
}

.media-strip-wrap {
  position: relative;
  overflow: hidden;
}

.media-strip {
  width: 100%;
  display: flex;
  gap: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 12px var(--space-2) 2px;
  scroll-behavior: smooth;
  scrollbar-width: thin;
}

.media-card {
  position: relative;
  flex: 0 0 auto;
  width: clamp(112px, 13vw, 148px);
  aspect-ratio: 1 / 1;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-paper-light);
  border: var(--border-default);
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-media {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.remove-card-btn {
  appearance: none;
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  color: var(--color-paper);
  background: rgba(26, 26, 26, 0.62);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
}

.remove-card-btn:hover {
  background: var(--color-danger);
}

.cover-card-btn {
  appearance: none;
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-2);
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  color: var(--color-paper);
  background: rgba(26, 26, 26, 0.68);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
}

.cover-card-btn .el-icon {
  font-size: 17px;
}

.cover-card-btn:hover {
  background: var(--color-brand);
}

.cover-file-input {
  display: none;
}

.card-index {
  position: absolute;
  left: var(--space-2);
  bottom: var(--space-2);
  min-width: 26px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: rgba(26, 26, 26, 0.62);
  color: var(--color-paper);
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 22px;
  text-align: center;
}

.add-upload {
  flex: 0 0 auto;
}

.add-card {
  appearance: none;
  cursor: pointer;
  color: var(--color-brand);
  border: 1px dashed var(--color-border);
  background: var(--color-paper-light);
  flex-direction: column;
  gap: var(--space-2);
  font-size: calc(var(--text-sm) * 1rem);
  font-weight: 600;
  transition: border-color 0.15s, background 0.15s;
}

.add-card .el-icon {
  font-size: 28px;
}

.add-card:hover {
  background: var(--color-brand-light);
  border-color: var(--color-brand);
}

.info-panel {
  margin-top: var(--space-2);
  padding: 28px;
  display: grid;
  gap: 22px;
}

.field-block {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.field-label {
  padding-top: 9px;
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-base) * 1rem);
  font-weight: 600;
}

.action-panel {
  margin-top: 18px;
  padding: 22px 28px;
}

.action-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.publish-btn {
  min-width: 160px;
  font-weight: 700;
}

.placeholder-btn {
  min-width: 140px;
}

.progress-wrap {
  width: 100%;
  margin-bottom: 14px;
}

.progress-text {
  display: block;
  margin-top: 6px;
  font-size: calc(var(--text-xs) * 1rem);
  color: var(--color-ink-tertiary);
}

@media (max-width: 720px) {
  .upload-work-page {
    width: min(100% - 24px, 1120px);
    margin-top: 18px;
  }

  .page-header {
    gap: var(--space-4);
  }

  .page-title {
    font-size: calc(var(--text-2xl) * 1rem);
  }

  .media-panel,
  .info-panel,
  .action-panel {
    padding: 18px;
  }

  .media-panel {
    padding-left: 0;
    padding-right: 0;
  }

  .panel-head {
    align-items: flex-end;
  }

  .media-card {
    width: 108px;
  }

  .field-block {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }

  .field-label {
    padding-top: 0;
  }

  .action-row {
    align-items: stretch;
    flex-direction: column;
  }

  .publish-btn,
  .placeholder-btn {
    width: 100%;
  }
}
</style>
