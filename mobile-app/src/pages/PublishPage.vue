<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <main class="page-shell">
        <AppTopBar @left-action="goAI" />

        <section class="publish-hero">
          <span class="hero-icon"><Plus :size="27" aria-hidden="true" /></span>
          <div>
            <h2>你想发布什么？</h2>
            <p>客户发布需求，摄影师发布作品和可预约方案。一个账号可在两种身份间切换。</p>
          </div>
        </section>

        <div class="action-list">
          <button
            v-for="action in actions"
            :key="action.id"
            type="button"
            class="publish-action pressable"
            :class="{ selected: selected === action.id }"
            @click="selectAction(action.id)"
          >
            <span class="action-icon" aria-hidden="true">
              <component :is="action.icon" :size="23" />
            </span>
            <span class="action-copy">
              <strong>{{ action.title }}</strong>
              <small>{{ action.description }}</small>
            </span>
            <ChevronRight :size="20" aria-hidden="true" />
          </button>
        </div>

        <section v-if="selectedAction" class="next-panel" aria-live="polite">
          <span>已选择</span>
          <h2>{{ selectedAction.title }}</h2>
          <p>{{ selectedAction.nextStep }}</p>
          <div v-if="requiresPhotographerIdentity" class="identity-note" role="status">
            <CircleAlert :size="19" aria-hidden="true" />
            <p>当前账号还不是摄影师。请先在摄影师认证页面完成申请与认证，再回来创建方案。</p>
          </div>
          <button
            type="button"
            class="primary-button pressable"
            :disabled="requiresPhotographerIdentity"
            @click="startPublishing"
          >
            {{ requiresPhotographerIdentity ? '需要摄影师身份' : '开始填写' }}
          </button>
        </section>

        <section class="draft-card">
          <FileClock :size="20" aria-hidden="true" />
          <div>
            <strong>草稿会保存在本机</strong>
            <p>未完成的文字内容会自动保存；出于隐私与系统限制，图片和视频需要重新选择。</p>
          </div>
          <button
            v-if="hasDrafts"
            type="button"
            class="drafts-link pressable"
            @click="goDrafts"
          >
            查看草稿箱
          </button>
        </section>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, markRaw, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage } from '@ionic/vue'
import {
  BriefcaseBusiness,
  ChevronRight,
  CircleAlert,
  FileClock,
  ImagePlus,
  PackagePlus,
  Plus,
} from 'lucide-vue-next'
import AppTopBar from '@/components/AppTopBar.vue'
import { useAuthStore } from '@/stores/auth'
import { readPublishDraft } from '@/utils/publishing'
import type { PublishResourceType } from '@/types/publishing'

type PublishType = 'project' | 'work' | 'package'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

function goAI() {
  void router.push({ name: 'ai-assistant' })
}
const actions = [
  {
    id: 'project' as const,
    title: '发布拍摄需求',
    description: '写清预算、地点与日期，邀请摄影师带方案响应',
    nextStep: '接下来填写拍摄主题、预算、城市、日期、参考图与交付要求。',
    icon: markRaw(BriefcaseBusiness),
  },
  {
    id: 'work' as const,
    title: '发布摄影作品',
    description: '上传成片或视频，完善标题、故事与风格标签',
    nextStep: '接下来选择照片或视频，并补充作品标题、描述与风格标签。',
    icon: markRaw(ImagePlus),
  },
  {
    id: 'package' as const,
    title: '创建摄影方案',
    description: '设置价格、时长、成片数量、交付周期与档期规则',
    nextStep: '接下来设置价格、拍摄时长、样片、交付标准、版权和取消规则。',
    icon: markRaw(PackagePlus),
  },
]

const initialType = actions.some((action) => action.id === route.query.type)
  ? (route.query.type as PublishType)
  : null
const selected = ref<PublishType | null>(initialType)
const selectedAction = computed(() => actions.find((action) => action.id === selected.value))
const requiresPhotographerIdentity = computed(() => (
  selected.value === 'package'
  && auth.initialized
  && auth.isAuthenticated
  && !auth.isPhotographer
))

const publishRoutes: Record<PublishType, 'publish-project' | 'publish-work' | 'publish-package'> = {
  project: 'publish-project',
  work: 'publish-work',
  package: 'publish-package',
}

function selectAction(type: PublishType) {
  selected.value = type
}

const hasDrafts = computed(() => {
  const types: PublishResourceType[] = ['work', 'package', 'project']
  return types.some((type) => readPublishDraft(type) !== null)
})

async function goDrafts() {
  await router.push({ name: 'drafts' })
}

async function startPublishing() {
  if (!selected.value || requiresPhotographerIdentity.value) return
  await router.push({ name: publishRoutes[selected.value] })
}
</script>

<style scoped>
.publish-hero {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-5);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--brand-soft);
  box-shadow: var(--neu-raise);
}

.hero-icon {
  display: grid;
  width: 50px;
  height: 50px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: var(--neu-surface-brand);
  box-shadow: var(--shadow-1);
  color: var(--white);
}

.publish-hero h2 {
  margin: 0 0 var(--space-2);
  font-family: var(--font-serif);
  font-size: var(--text-xl);
}

.publish-hero p,
.draft-card p,
.next-panel p {
  margin: 0;
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  line-height: 1.65;
}

.action-list {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.publish-action {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) 24px;
  min-height: 82px;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  color: var(--ink);
  text-align: left;
}

.publish-action.selected {
  border-color: var(--brand);
  background: var(--paper);
  box-shadow: var(--neu-inset);
  border: 0;
}

.action-icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--paper);
  box-shadow: var(--neu-inset);
  color: var(--brand);
}

.selected .action-icon {
  background: var(--neu-surface-brand);
  box-shadow: var(--shadow-1);
  color: var(--white);
}

.action-copy {
  display: grid;
  gap: 5px;
}

.action-copy strong {
  font-size: var(--text-base);
}

.action-copy small {
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.55;
}

.next-panel {
  margin-top: var(--space-5);
  padding: var(--space-5);
  border-left: 4px solid var(--brand);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
}

.next-panel > span {
  color: var(--brand);
  font-size: var(--text-xs);
  font-weight: 750;
  letter-spacing: 0.08em;
}

.next-panel h2 {
  margin: 5px 0 var(--space-2);
  font-size: var(--text-lg);
}

.primary-button {
  width: 100%;
  min-height: var(--touch-target);
  margin-top: var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface-brand);
  box-shadow: var(--shadow-1);
  color: var(--white);
  font-weight: 700;
}

.primary-button:disabled {
  background: var(--paper-deep);
  box-shadow: none;
  color: var(--ink-tertiary);
}

.identity-note {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding: var(--space-3);
  border: 1px solid color-mix(in srgb, var(--danger) 28%, transparent);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--danger) 7%, var(--paper-light));
  color: var(--danger);
}

.identity-note svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.identity-note p {
  color: inherit;
}

.draft-card {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding: var(--space-4);
  border-top: 1px solid var(--divider);
  color: var(--ink-secondary);
}

.draft-card strong {
  display: block;
  margin-bottom: 4px;
  color: var(--ink);
  font-size: var(--text-sm);
}

.drafts-link {
  flex: 0 0 auto;
  align-self: center;
  min-height: var(--touch-target);
  margin-left: auto;
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface-brand);
  box-shadow: var(--shadow-1);
  color: var(--white);
  font-size: var(--text-sm);
  font-weight: 650;
  white-space: nowrap;
}

.drafts-link:active { background: var(--neu-surface-brand); box-shadow: var(--neu-inset-brand); }
</style>
