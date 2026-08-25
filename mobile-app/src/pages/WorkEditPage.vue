<template>
  <ion-page>
    <DetailHeader title="编辑作品" :default-href="workDetailHref" />

    <ion-content class="edit-content">
      <main class="edit-shell">
        <FeedSkeleton v-if="loading" :count="2" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="作品无法编辑"
          :description="error"
          action-label="重新加载"
          @action="load"
        />

        <template v-else-if="work">
          <section class="edit-intro">
            <span><FilePenLine :size="22" aria-hidden="true" /></span>
            <div>
              <h1>完善作品信息</h1>
              <p>可以修改标题、风格标签和创作说明，已发布的图片或视频将保持不变。</p>
            </div>
          </section>

          <form class="edit-form" novalidate @submit.prevent="save">
            <div class="edit-field">
              <label for="work-edit-title">作品标题 <span>建议填写</span></label>
              <input
                id="work-edit-title"
                v-model.trim="form.title"
                class="edit-input"
                maxlength="120"
                placeholder="例如：春日校园写真"
                :disabled="submitting"
              />
            </div>

            <div class="edit-field">
              <label for="work-edit-tags">风格标签 <span>最多 12 个</span></label>
              <TagEditor
                v-model="tags"
                input-id="work-edit-tags"
                placeholder="例如：日系、胶片、自然光"
                :disabled="submitting"
                @limit="toastMessage = '最多添加 12 个标签。'"
              />
            </div>

            <div class="edit-field">
              <label for="work-edit-description">创作说明 <span>选填</span></label>
              <textarea
                id="work-edit-description"
                v-model.trim="form.description"
                class="edit-textarea"
                rows="7"
                maxlength="1200"
                placeholder="说明拍摄主题、场景、光线或创作想法"
                :disabled="submitting"
              />
              <p class="edit-help">{{ form.description.length }}/1200</p>
            </div>

            <div v-if="requestError" class="request-error" role="alert">
              <CircleAlert :size="19" aria-hidden="true" />{{ requestError }}
            </div>
          </form>
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2500"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>

    <ion-footer v-if="work && !loading && !error" class="edit-footer">
      <div class="edit-actions">
        <button type="button" class="primary pressable" :disabled="submitting" @click="save">
          <ion-spinner v-if="submitting" name="crescent" aria-hidden="true" />
          <Save v-else :size="18" aria-hidden="true" />
          保存修改
        </button>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonFooter, IonPage, IonSpinner, IonToast } from '@ionic/vue'
import { CircleAlert, FilePenLine, Save } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import TagEditor from '@/components/TagEditor.vue'
import { getApiErrorMessage } from '@/api/client'
import { getWorkDetail } from '@/api/discovery'
import { updateWorkMetadata } from '@/api/works'
import { useAuthStore } from '@/stores/auth'
import type { WorkItem } from '@/types/discovery'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const work = ref<WorkItem | null>(null)
const form = reactive({ title: '', description: '' })
const tags = ref<string[]>([])
const loading = ref(true)
const error = ref('')
const requestError = ref('')
const submitting = ref(false)
const toastMessage = ref('')

const workId = computed(() => String(route.params.workId || ''))
const workDetailHref = computed(() => `/works/${workId.value}`)

async function load() {
  loading.value = true
  error.value = ''
  requestError.value = ''
  try {
    await auth.initialize()
    const detail = await getWorkDetail(workId.value)
    const ownerId = detail.photographer_id || detail.user_id
    if (!auth.user || auth.user.id !== ownerId) {
      throw new Error('只有这组作品的发布者可以进行编辑。')
    }
    work.value = detail
    form.title = detail.title || ''
    form.description = detail.description || ''
    tags.value = [...(detail.tags || (detail.tag ? [detail.tag] : []))]
  } catch (loadError) {
    work.value = null
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!work.value || submitting.value) return
  submitting.value = true
  requestError.value = ''
  try {
    await updateWorkMetadata(work.value.id, {
      title: form.title.trim(),
      tags: tags.value,
      description: form.description.trim(),
    })
    await router.replace({ name: 'work-detail', params: { workId: work.value.id } })
  } catch (saveError) {
    requestError.value = getApiErrorMessage(saveError)
  } finally {
    submitting.value = false
  }
}

onMounted(() => void load())
</script>

<style scoped>
.edit-content { --background: var(--paper); }
.edit-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }
.edit-intro { display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: var(--space-3); margin-bottom: var(--space-4); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.edit-intro > span { display: grid; width: 46px; height: 46px; place-items: center; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--brand); }
.edit-intro h1 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.edit-intro p { margin: 4px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.edit-form { display: grid; gap: var(--space-5); padding: var(--space-5) var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.edit-field { display: grid; gap: var(--space-2); }
.edit-field label { color: var(--ink); font-size: var(--text-sm); font-weight: 700; }
.edit-field label span { color: var(--ink-tertiary); font-size: var(--text-xs); font-weight: 500; }
.edit-input, .edit-textarea { width: 100%; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font-size: var(--text-base); outline: none; }
.edit-input { min-height: var(--touch-target); padding: 0 var(--space-3); }
.edit-textarea { min-height: 150px; padding: var(--space-3); line-height: 1.65; resize: vertical; }
.edit-input:focus, .edit-textarea:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, 0.26); }
.edit-input:disabled, .edit-textarea:disabled { opacity: .6; }
.edit-help { margin: 0; color: var(--ink-tertiary); font-size: 11px; text-align: right; }
.request-error { display: flex; align-items: flex-start; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--danger); border-radius: var(--radius-md); color: var(--danger); font-size: var(--text-sm); line-height: 1.5; }
.edit-footer { background: var(--paper); }
.edit-actions { width: min(100%, var(--content-max)); margin: 0 auto; padding: var(--space-3) var(--space-4) calc(var(--space-3) + env(safe-area-inset-bottom)); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); }
.edit-actions .primary { display: inline-flex; width: 100%; min-height: 48px; align-items: center; justify-content: center; gap: var(--space-2); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); font-weight: 750; }
.edit-actions .primary:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); }
.edit-actions ion-spinner { width: 18px; height: 18px; }
</style>
