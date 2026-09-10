<template>
  <Transition name="sheet">
    <div v-if="modelValue" class="sheet-layer" @click.self="close">
      <div
        ref="sheetRef"
        class="sheet"
        role="dialog"
        aria-modal="true"
        aria-label="发布"
        tabindex="-1"
        @keydown.esc="close"
      >
        <header class="sheet-head">
          <h2>发布</h2>
          <button type="button" class="close-btn pressable" aria-label="关闭" @click="close">
            <X :size="20" aria-hidden="true" />
          </button>
        </header>

        <ul class="action-list">
          <li v-for="action in actions" :key="action.id">
            <button type="button" class="action pressable" @click="startPublishing(action.id)">
              <span class="action-icon" aria-hidden="true">
                <component :is="action.icon" :size="22" />
              </span>
              <span class="action-text">
                <strong>{{ action.title }}</strong>
                <small>{{ action.description }}</small>
              </span>
              <ChevronRight :size="18" aria-hidden="true" />
            </button>
          </li>
        </ul>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { markRaw, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BriefcaseBusiness, ChevronRight, ImagePlus, PackagePlus, X } from 'lucide-vue-next'

type PublishType = 'project' | 'work' | 'package'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const router = useRouter()
const sheetRef = ref<HTMLElement>()

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

const publishRoutes: Record<PublishType, 'publish-project' | 'publish-work' | 'publish-package'> = {
  project: 'publish-project',
  work: 'publish-work',
  package: 'publish-package',
}

/**
 * TODO(负责人): 参照实现里还有两处未搬过来，等对应页面就绪时补：
 * 1. 创建方案前的摄影师身份校验（需要 auth store 的 user / isPhotographer）。
 * 2. 底部的「本机草稿」入口 —— 它指向的 drafts 路由至今没有接线，见 PAGES.md §2.2。
 * 触觉反馈（tapHaptic）随第 5 步一起接。
 */

function close() {
  emit('update:modelValue', false)
}

async function startPublishing(type: PublishType) {
  close()
  await router.push({ name: publishRoutes[type] })
}

// 打开时锁定 body 滚动，关闭时把焦点交还给触发它的 Tab 按钮。
watch(
  () => props.modelValue,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) void nextTick(() => sheetRef.value?.focus())
  },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<style scoped>
.sheet-layer {
  position: fixed;
  z-index: var(--layer-modal);
  inset: 0;
  display: flex;
  align-items: flex-end;
  background: var(--scrim);
}

.sheet {
  width: 100%;
  max-width: var(--content-max);
  margin-inline: auto;
  padding: var(--space-4) var(--space-4) calc(var(--space-6) + env(safe-area-inset-bottom));
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  background: var(--material-thick);
}

.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.sheet-head h2 {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 700;
  line-height: var(--leading-snug);
}

.close-btn {
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  flex: 0 0 auto;
  place-items: center;
  border: 0;
  border-radius: var(--radius-pill);
  background: var(--surface-secondary);
  color: var(--ink-secondary);
}

.action-list {
  display: grid;
  gap: var(--space-2);
  padding: 0;
  margin: var(--space-4) 0 0;
  list-style: none;
}

.action {
  display: flex;
  width: 100%;
  min-height: var(--touch-target);
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--surface-solid);
  box-shadow: var(--shadow-1);
  color: var(--ink);
  text-align: left;
}

.action-icon {
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--brand);
}

.action-text {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 2px;
}

.action-text strong {
  font-size: var(--text-sm);
  font-weight: 650;
}

.action-text small {
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.5;
}

/* 只动 transform 与 opacity，见 DESIGN.md §8 */
.sheet-enter-active,
.sheet-leave-active {
  transition: opacity var(--motion-fast) ease-out;
}

.sheet-enter-active .sheet,
.sheet-leave-active .sheet {
  transition: transform var(--motion-normal) var(--spring-ui);
}

.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}

.sheet-enter-from .sheet,
.sheet-leave-to .sheet {
  transform: translateY(100%);
}
</style>
