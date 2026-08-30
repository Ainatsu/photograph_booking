<template>
  <ion-page>
    <DetailHeader title="发布摄影作品" default-href="/tabs/discover" />

    <ion-content class="mobile-publish-content">
      <main class="mobile-publish-shell">
        <section class="mobile-publish-intro">
          <span><ImagePlus :size="22" aria-hidden="true" /></span>
          <div><h1>用完整作品展示风格</h1><p>一条作品可以是最多 18 张图片，或一个视频；图片和视频需要分开发布。</p></div>
        </section>

        <section v-if="draftRestored" class="publish-draft-note" role="status">
          <FileClock :size="19" aria-hidden="true" />
          <div><strong>已恢复 {{ draftTime }} 保存的本机草稿</strong><p>标题、描述和标签已恢复，作品文件需要重新选择。</p></div>
        </section>
        <section v-if="agentTask" class="agent-source-note" role="status">已载入 Agent 整理的文字信息；媒体需要在此页面重新选择。</section>

        <form class="mobile-publish-form" novalidate @submit.prevent="publishWork">
          <section class="publish-section">
            <header class="publish-section-heading"><span>1</span><div><h2>作品媒体</h2><p>支持图片组或单个视频，上传期间请保持应用在前台。</p></div></header>
            <PublishMediaPicker v-model:files="mediaFiles" input-id="work-media-files" mode="mixed" :disabled="submitting" @error="requestError = $event" />
            <div v-if="workKind === 'video'" class="publish-field">
              <label for="work-cover-files">视频封面 <span>选填；不选则由服务端尝试截帧</span></label>
              <PublishMediaPicker v-model:files="coverFiles" input-id="work-cover-files" mode="image" :image-limit="1" :disabled="submitting" hint="封面支持 JPG、PNG、WebP，最大 10 MB" @error="requestError = $event" />
            </div>
          </section>

          <section class="publish-section">
            <header class="publish-section-heading"><span>2</span><div><h2>作品说明</h2><p>清楚的标题与标签有助于被发现和匹配。</p></div></header>
            <div class="publish-field">
              <label for="work-title">作品标题 <span>建议填写</span></label>
              <input id="work-title" v-model.trim="form.title" class="publish-input" maxlength="120" placeholder="例如：春日校园写真" :disabled="submitting" />
            </div>
            <div class="publish-field">
              <label for="work-tags-input">风格标签 <span>最多 12 个</span></label>
              <TagEditor v-model="tags" input-id="work-tags-input" placeholder="例如：日系、胶片、自然光" :disabled="submitting" @limit="toastMessage = '最多添加 12 个标签。'" />
            </div>
            <div class="publish-field">
              <label for="work-description">创作说明 <span>选填</span></label>
              <textarea id="work-description" v-model.trim="form.description" class="publish-textarea" rows="5" maxlength="1200" placeholder="说明拍摄主题、场景、光线或创作想法" :disabled="submitting" />
              <p class="publish-help">{{ form.description.length }}/1200</p>
            </div>
          </section>

          <div v-if="requestError" class="publish-request-error" role="alert"><CircleAlert :size="19" aria-hidden="true" />{{ requestError }}</div>
          <div v-if="submitting" class="publish-progress" aria-live="polite">
            <div><i :style="{ '--progress': `${uploadProgress}%` }" /></div>
            <span>{{ progressText }}</span>
          </div>
        </form>
      </main>
      <ion-toast :is-open="Boolean(toastMessage)" :message="toastMessage" :duration="2600" position="bottom" @did-dismiss="toastMessage = ''" />
    </ion-content>

    <ion-footer class="mobile-publish-footer">
      <div class="mobile-publish-actions with-agent">
        <button type="button" class="pressable" :disabled="submitting || agentPolishing" @click="saveDraftNow"><Save :size="18" aria-hidden="true" />保存本机</button>
        <PublishAgentPolishButton
          content-type="work"
          :fields="workPolishFields"
          :disabled="submitting"
          @busy-change="agentPolishing = $event"
          @error="requestError = $event"
          @polished="applyPolishedWork"
        />
        <button type="button" class="pressable" :disabled="submitting || agentPolishing || !mediaFiles.length" @click="publishWork">
          <ion-spinner v-if="submitting" name="crescent" aria-hidden="true" /><Upload v-else :size="18" aria-hidden="true" />发布作品
        </button>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonFooter, IonPage, IonSpinner, IonToast } from '@ionic/vue'
import { CircleAlert, FileClock, ImagePlus, Save, Upload } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import PublishMediaPicker from '@/components/PublishMediaPicker.vue'
import PublishAgentPolishButton from '@/components/PublishAgentPolishButton.vue'
import TagEditor from '@/components/TagEditor.vue'
import { getApiErrorMessage } from '@/api/client'
import { useAgentTaskHandoff } from '@/composables/useAgentTaskHandoff'
import { uploadImageWork, uploadVideoWork } from '@/api/publishing'
import { clearPublishDraft, formatDraftTime, readPublishDraft, savePublishDraft } from '@/utils/publishing'

interface WorkDraftState { title: string; description: string; tags: string[] }

const router = useRouter()
const route = useRoute()
const agentHandoff = useAgentTaskHandoff()
const agentTask = agentHandoff.task
const form = reactive({ title: '', description: '' })
const tags = ref<string[]>([])
const mediaFiles = ref<File[]>([])
const coverFiles = ref<File[]>([])
const requestError = ref('')
const submitting = ref(false)
const agentPolishing = ref(false)
const uploadProgress = ref(0)
const progressText = ref('正在准备上传…')
const draftRestored = ref(false)
const draftTime = ref('')
const toastMessage = ref('')
const currentDraftId = ref('')
let draftTimer: number | null = null

const workPolishFields = computed(() => ({
  title: form.title,
  description: form.description,
  tags: [...tags.value],
}))

function applyPolishedWork(fields: Record<string, unknown>, changedCount: number) {
  if (typeof fields.title === 'string') form.title = fields.title
  if (typeof fields.description === 'string') form.description = fields.description
  if (Array.isArray(fields.tags)) tags.value = fields.tags.map(String).slice(0, 12)
  requestError.value = ''
  toastMessage.value = changedCount ? `Agent 已润色 ${changedCount} 项文字内容。` : '当前文字已经很清晰，无需调整。'
}

const videoExtensions = new Set(['mp4', 'avi', 'mov', 'wmv', 'webm', 'mkv', 'flv'])
const workKind = computed<'image' | 'video'>(() => {
  const file = mediaFiles.value[0]
  if (!file) return 'image'
  const extension = file.name.split('.').pop()?.toLocaleLowerCase() || ''
  return file.type.startsWith('video/') || videoExtensions.has(extension) ? 'video' : 'image'
})

async function publishWork() {
  if (submitting.value) return
  if (!mediaFiles.value.length) {
    requestError.value = '请先选择要发布的图片或视频。'
    return
  }
  submitting.value = true
  requestError.value = ''
  uploadProgress.value = 1
  progressText.value = workKind.value === 'video' ? '正在上传并处理视频，请保持应用在前台…' : '正在上传作品图片…'
  try {
    const metadata = { title: form.title.trim(), tags: tags.value, description: form.description.trim() }
    const response = workKind.value === 'video'
      ? await uploadVideoWork(mediaFiles.value[0], coverFiles.value[0] || null, metadata, (percent) => { uploadProgress.value = percent })
      : await uploadImageWork(mediaFiles.value, metadata, (percent) => { uploadProgress.value = percent })
    uploadProgress.value = 100
    if (currentDraftId.value) clearPublishDraft('work', currentDraftId.value)
    if (agentTask.value) await agentHandoff.complete({ work_id: response.work.id })
    await router.replace({ name: 'work-detail', params: { workId: response.work.id } })
  } catch (error) {
    requestError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

function draftSnapshot(): WorkDraftState {
  return { title: form.title, description: form.description, tags: [...tags.value] }
}

function saveDraftNow() {
  const id = savePublishDraft('work', draftSnapshot(), currentDraftId.value)
  currentDraftId.value = id
  toastMessage.value = `本机草稿已保存（${formatDraftTime(new Date().toISOString())}）`
}

function restoreDraft() {
  if (route.query.agentTaskId) return
  const draftId = route.query.draftId as string | undefined
  const draft = readPublishDraft<WorkDraftState>('work', draftId)
  if (!draft) return
  Object.assign(form, draft.value)
  tags.value = Array.isArray(draft.value.tags) ? draft.value.tags : []
  draftRestored.value = true
  draftTime.value = formatDraftTime(draft.updatedAt)
  currentDraftId.value = draft.id
}

function taskOperation(field: string, value: unknown) {
  const empty = value === '' || value === null || value === undefined || (Array.isArray(value) && !value.length)
  return empty ? { field, op: 'clear' as const } : { field, op: 'set' as const, value }
}

function scheduleDraftSave() {
  if (draftTimer !== null) window.clearTimeout(draftTimer)
  draftTimer = window.setTimeout(() => {
    if (route.query.agentTaskId) {
      void agentHandoff.saveOperations([
        taskOperation('title', form.title.trim()),
        taskOperation('description', form.description.trim()),
        taskOperation('tags', [...tags.value]),
      ]).catch((error) => {
        requestError.value = getApiErrorMessage(error)
      })
    } else {
      const id = savePublishDraft('work', draftSnapshot(), currentDraftId.value)
      currentDraftId.value = id
    }
  }, 450)
}

watch(workKind, (kind) => { if (kind !== 'video') coverFiles.value = [] })
onMounted(async () => {
  const task = await agentHandoff.load('publish_work')
  if (task) {
    form.title = String(task.fields.title || '')
    form.description = String(task.fields.description || '')
    tags.value = Array.isArray(task.fields.tags) ? task.fields.tags.map(String) : []
  } else restoreDraft()
})
watch(() => draftSnapshot(), scheduleDraftSave, { deep: true })
onUnmounted(() => { if (draftTimer !== null) window.clearTimeout(draftTimer) })
</script>
