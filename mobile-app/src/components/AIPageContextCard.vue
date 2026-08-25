<template>
  <div
    class="context-card"
    :class="{
      'context-card--clickable': clickable,
      'context-card--sent': sent,
    }"
    :role="clickable ? 'button' : undefined"
    :tabindex="clickable ? 0 : undefined"
    :aria-label="clickable ? `查看${typeLabel}详情` : undefined"
    @click="handleClick"
    @keydown.enter="handleClick"
  >
    <div class="context-card-media">
      <img
        v-if="thumbnailUrl"
        :src="thumbnailUrl"
        :alt="context.title"
        class="context-card-thumb"
        loading="lazy"
        @error="imageFailed = true"
      />
      <div v-else class="context-card-fallback">
        <component :is="fallbackIcon" :size="28" aria-hidden="true" />
      </div>
      <button
        v-if="removable"
        type="button"
        class="context-card-remove"
        aria-label="取消引用"
        @click.stop="$emit('remove')"
      >
        <X :size="14" aria-hidden="true" />
      </button>
    </div>

    <div class="context-card-body">
      <span class="context-card-type">{{ typeLabel }}</span>
      <span class="context-card-title">{{ context.title }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Bot, Image as ImageIcon, User, Package, ClipboardList, X } from 'lucide-vue-next'
import type { AIPageContext } from '@/api/ai'
import { resolveMediaUrl } from '@/utils/media'

const props = withDefaults(
  defineProps<{
    context: AIPageContext
    removable?: boolean
    clickable?: boolean
    sent?: boolean
  }>(),
  { removable: false, clickable: false, sent: false },
)

const emit = defineEmits<{
  remove: []
  'open-source': []
}>()

const imageFailed = ref(false)

const typeLabel = computed(() => {
  const map: Record<string, string> = {
    portfolio_item: '引用作品',
    photographer: '引用摄影师',
    package: '引用方案',
    project: '引用企划',
  }
  return map[props.context.resource_type] || '引用'
})

const fallbackIcon = computed(() => {
  const map: Record<string, any> = {
    portfolio_item: ImageIcon,
    photographer: User,
    package: Package,
    project: ClipboardList,
  }
  return map[props.context.resource_type] || Bot
})

const thumbnailUrl = computed(() => {
  if (imageFailed.value) return ''
  const co = props.context.current_object
  if (co?.thumbnail_url) return resolveMediaUrl(co.thumbnail_url)
  if (co?.image_url) return resolveMediaUrl(co.image_url)
  return ''
})

function handleClick() {
  if (props.clickable) {
    emit('open-source')
  }
}
</script>

<style scoped>
.context-card {
  display: grid;
  grid-template-rows: 1fr auto;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.context-card--clickable {
  cursor: pointer;
}

.context-card--clickable:active {
  border-color: var(--brand);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.context-card--sent {
  opacity: 0.9;
}

.context-card-media {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.context-card-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.context-card-fallback {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  color: var(--ink-tertiary);
}

.context-card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  min-width: 0;
}

.context-card-type {
  font-size: 10px;
  color: var(--brand);
  font-weight: 700;
  line-height: 1.2;
}

.context-card-title {
  overflow: hidden;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink);
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-card-remove {
  position: absolute;
  top: 0;
  right: 0;
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border: 0;
  background: transparent;
  color: #fff;
  cursor: pointer;
  z-index: 1;
}

.context-card-remove::before {
  position: absolute;
  inset: 10px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.45);
  content: '';
}

.context-card-remove svg {
  position: relative;
}

.context-card-remove:active::before {
  background: rgba(0, 0, 0, 0.65);
}

.context-card-remove:focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: -2px;
}
</style>
