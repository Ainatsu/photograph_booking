<template>
  <header
    ref="topBarRef"
    class="top-bar"
    :class="{ 'searching': isSearching, 'has-center': hasCenter }"
  >
    <template v-if="!isSearching">
      <button
        v-if="showLeft"
        type="button"
        class="icon-action pressable"
        :aria-label="leftLabel"
        @click="$emit('left-action')"
      >
        <slot name="left">
          <Bot :size="21" aria-hidden="true" />
        </slot>
      </button>

      <div class="top-bar-center">
        <slot name="center" />
      </div>

      <slot name="trailing" />

      <button
        v-if="showSearch"
        type="button"
        class="icon-action pressable"
        aria-label="搜索"
        @click="startSearch"
      >
        <Search :size="21" aria-hidden="true" />
      </button>
    </template>

    <template v-else>
      <button
        type="button"
        class="icon-action pressable"
        aria-label="退出搜索"
        @click="cancelSearch"
      >
        <ArrowLeft :size="21" aria-hidden="true" />
      </button>

      <div class="search-input-wrap">
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="search"
          placeholder="搜索作品、摄影师或风格"
          enterkeyhint="search"
          aria-label="搜索"
          @keydown.enter.prevent="submitSearch"
          @keydown.esc="cancelSearch"
        />
        <button
          v-if="searchQuery"
          type="button"
          class="clear-btn"
          aria-label="清空"
          @click="searchQuery = ''"
        >
          <X :size="17" aria-hidden="true" />
        </button>
      </div>
    </template>
  </header>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useSlots, watch } from 'vue'
import { ArrowLeft, Bot, Search, X } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    leftLabel?: string
    showLeft?: boolean
    showSearch?: boolean
    /** 提交搜索后自动收起输入框，恢复中部内容（用于提交即跳转的页面） */
    collapseOnSubmit?: boolean
  }>(),
  {
    leftLabel: 'AI 助手',
    showLeft: true,
    showSearch: true,
    collapseOnSubmit: false,
  },
)

const emit = defineEmits<{
  'left-action': []
  search: [query: string]
}>()

const slots = useSlots()
const hasCenter = computed(() => Boolean(slots.center))

const isSearching = ref(false)
const searchQuery = ref('')
const searchInputRef = ref<HTMLInputElement>()
const topBarRef = ref<HTMLElement>()

function startSearch() {
  isSearching.value = true
  nextTick(() => {
    searchInputRef.value?.focus()
  })
}

function cancelSearch() {
  isSearching.value = false
  searchQuery.value = ''
}

function submitSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  emit('search', q)
  if (props.collapseOnSubmit) cancelSearch()
}

/** 点击顶栏之外的任意位置时退出搜索，恢复中部的切换栏 */
function onDocumentClick(event: Event) {
  const target = event.target as Node | null
  if (target && topBarRef.value?.contains(target)) return
  cancelSearch()
}

watch(isSearching, (searching) => {
  if (searching) {
    document.addEventListener('click', onDocumentClick, true)
  } else {
    document.removeEventListener('click', onDocumentClick, true)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick, true)
})
</script>

<style scoped>
.top-bar {
  position: sticky;
  z-index: var(--layer-sticky);
  top: 0;
  display: flex;
  min-height: calc(56px + env(safe-area-inset-top));
  align-items: center;
  gap: var(--space-2);
  margin-inline: calc(var(--space-4) * -1);
  padding-inline: var(--space-4);
  padding-top: env(safe-area-inset-top);
  background: var(--material-thin);
  box-shadow: 0 12px 16px -18px rgba(0, 0, 0, 0.45);
  backdrop-filter: var(--material-blur);
  -webkit-backdrop-filter: var(--material-blur);
  transition: gap var(--motion-fast) ease-out;
}

.top-bar.searching {
  gap: var(--space-2);
}

.top-bar.has-center {
  gap: var(--space-2);
}

.top-bar-center {
  flex: 1;
  min-width: 0;
}

.icon-action {
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  flex: 0 0 auto;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  box-shadow: none;
  color: var(--brand);
}

.icon-action:active { background: var(--surface-secondary); }

.search-input-wrap {
  display: flex;
  flex: 1;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  box-shadow: none;
}

.search-input-wrap input {
  width: 100%;
  min-width: 0;
  min-height: var(--touch-target);
  border: 0;
  outline: 0;
  background: transparent;
  box-shadow: none;
  color: var(--ink);
  font-size: var(--text-base);
}

.search-input-wrap input::placeholder {
  color: var(--ink-tertiary);
}

.search-input-wrap input::-webkit-search-cancel-button {
  display: none;
}

.clear-btn {
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  flex: 0 0 auto;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-secondary);
}

.clear-btn:active { background: var(--surface-tertiary); }

@media (prefers-reduced-transparency: reduce) {
  .top-bar { backdrop-filter: none; -webkit-backdrop-filter: none; }
}
</style>
