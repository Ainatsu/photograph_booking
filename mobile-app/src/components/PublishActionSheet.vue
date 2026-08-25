<template>
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="modelValue" class="overlay-backdrop" @click.self="$emit('update:modelValue', false)">
        <div class="overlay-cards">
          <button
            v-for="action in actions"
            :key="action.id"
            type="button"
            class="publish-card pressable"
            :class="{ dimmed: action.id === 'package' && requiresPhotographerIdentity }"
            :disabled="action.id === 'package' && requiresPhotographerIdentity"
            @click="startPublishing(action.id)"
          >
            <span class="card-icon" aria-hidden="true">
              <component :is="action.icon" :size="24" />
            </span>
            <span class="card-copy">
              <strong>{{ action.title }}</strong>
              <small>{{ action.description }}</small>
            </span>
          </button>

          <div v-if="hasDrafts" class="draft-entry">
            <button type="button" class="draft-link" @click="goDrafts">
              <FileClock :size="16" aria-hidden="true" />
              <span>查看草稿箱</span>
              <ChevronRight :size="16" aria-hidden="true" />
            </button>
          </div>
        </div>

        <button
          class="close-btn"
          aria-label="关闭"
          @click="$emit('update:modelValue', false)"
        >
          <X :size="22" aria-hidden="true" />
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, markRaw, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BriefcaseBusiness, ChevronRight, FileClock, ImagePlus, PackagePlus, X } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { readPublishDraft } from '@/utils/publishing'
import type { PublishResourceType } from '@/types/publishing'
import { tapHaptic } from '@/utils/haptics'

type PublishType = 'project' | 'work' | 'package'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const router = useRouter()
const auth = useAuthStore()

const actions = [
  {
    id: 'project' as const,
    title: '发布拍摄需求',
    description: '写清预算、地点与日期，邀请摄影师带方案响应',
    icon: markRaw(BriefcaseBusiness),
  },
  {
    id: 'work' as const,
    title: '发布摄影作品',
    description: '上传成片或视频，完善标题、故事与风格标签',
    icon: markRaw(ImagePlus),
  },
  {
    id: 'package' as const,
    title: '创建摄影方案',
    description: '设置价格、时长、成片数量、交付周期与档期规则',
    icon: markRaw(PackagePlus),
  },
]

const requiresPhotographerIdentity = computed(() => (
  auth.initialized
  && auth.isAuthenticated
  && !auth.isPhotographer
))

const publishRoutes: Record<PublishType, 'publish-project' | 'publish-work' | 'publish-package'> = {
  project: 'publish-project',
  work: 'publish-work',
  package: 'publish-package',
}

const hasDrafts = computed(() => {
  const types: PublishResourceType[] = ['work', 'package', 'project']
  return types.some((type) => readPublishDraft(type) !== null)
})

// 打开时锁定 body 滚动
watch(() => props.modelValue, (val) => {
  document.body.style.overflow = val ? 'hidden' : ''
})

onBeforeUnmount(() => {
  document.body.style.overflow = ''
})

async function startPublishing(type: PublishType) {
  if (type === 'package' && requiresPhotographerIdentity.value) return
  tapHaptic()
  emit('update:modelValue', false)
  await router.push({ name: publishRoutes[type] })
}

async function goDrafts() {
  emit('update:modelValue', false)
  await router.push({ name: 'drafts' })
}
</script>

<style scoped>
.overlay-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--layer-modal);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-end;
  padding: var(--space-4) var(--space-4) calc(var(--space-4) + env(safe-area-inset-bottom));
  background: var(--scrim);
  backdrop-filter: blur(12px) saturate(120%);
  -webkit-backdrop-filter: blur(12px) saturate(120%);
}

/* 卡片容器 */
.overlay-cards {
  display: grid;
  gap: var(--space-3);
  width: min(100%, 520px);
  margin: 0 auto;
  padding: var(--space-3);
  border: 1px solid var(--divider);
  border-radius: var(--radius-xl);
  background: var(--material-thick);
  box-shadow: var(--shadow-3);
  backdrop-filter: var(--material-blur);
  -webkit-backdrop-filter: var(--material-blur);
}

/* 单张卡片 */
.publish-card {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-2);
  border: 0;
  border-radius: var(--radius-lg);
  background: transparent;
  box-shadow: none;
  color: var(--ink);
  text-align: left;
  transition: transform var(--motion-fast) ease, box-shadow var(--motion-fast) ease;
}

.publish-card:active {
  transform: scale(0.97);
  background: var(--surface-secondary);
  box-shadow: none;
}

.publish-card.dimmed {
  opacity: 0.45;
}

.card-icon {
  display: grid;
  width: 52px;
  height: 52px;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--brand);
}

.card-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.card-copy strong {
  font-size: var(--text-base);
  font-weight: 650;
}

.card-copy small {
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

/* 草稿入口 */
.draft-entry {
  margin-top: var(--space-1);
  border-top: 1px solid var(--divider);
  padding-top: var(--space-2);
}

.draft-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) var(--space-3);
  border: 0;
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--brand);
  font-size: var(--text-xs);
  font-weight: 600;
  transition: background var(--motion-fast) ease;
}

.draft-link:active {
  background: var(--surface-secondary);
}

/* 关闭按钮 */
.close-btn {
  position: absolute;
  top: max(var(--space-3), env(safe-area-inset-top));
  right: var(--space-3);
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: var(--material-regular);
  color: var(--ink);
  transition: background var(--motion-fast) ease;
}

.close-btn:active {
  background: var(--material-thick);
}

/* 过渡动画 */
.overlay-enter-active {
  transition: opacity var(--motion-normal) ease-out;
}
.overlay-enter-active .publish-card {
  transition: opacity var(--motion-normal) ease-out, transform var(--motion-normal) var(--spring-ui);
}
.overlay-enter-from {
  opacity: 0;
}
.overlay-enter-from .publish-card {
  opacity: 0;
  transform: translateY(24px) scale(0.98);
}
.overlay-leave-active {
  transition: opacity var(--motion-fast) ease-in;
}
.overlay-leave-to {
  opacity: 0;
}

@media (prefers-reduced-transparency: reduce) {
  .overlay-backdrop,
  .overlay-cards { backdrop-filter: none; -webkit-backdrop-filter: none; }
}
</style>
