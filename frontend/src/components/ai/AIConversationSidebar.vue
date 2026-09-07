<template>
  <aside class="conversation-sidebar" aria-label="AI 对话">
    <header class="sidebar-header">
      <div>
        <strong>对话</strong>
        <span>{{ conversations.length }} 个进行中</span>
      </div>
      <button type="button" class="icon-button" aria-label="新建对话" :disabled="busy" @click="$emit('create')">
        <SquarePen :size="19" aria-hidden="true" />
      </button>
    </header>

    <label class="conversation-search">
      <Search :size="16" aria-hidden="true" />
      <input v-model="searchText" type="search" placeholder="搜索对话" @input="$emit('search', searchText)" />
    </label>
    <div class="conversation-list">
      <p v-if="!conversations.length" class="empty-state">还没有对话</p>
      <article
        v-for="conversation in conversations"
        :key="conversation.id"
        class="conversation-item"
        :class="{ active: String(conversation.id) === String(activeId) }"
      >
        <button type="button" class="conversation-main" :disabled="busy" @click="$emit('select', conversation.id)">
          <MessageSquare :size="17" aria-hidden="true" />
          <span>
            <strong>{{ conversation.title || '新对话' }}</strong>
            <small>{{ formatDate(conversation.updated_at) }}</small>
          </span>
        </button>
        <div class="item-actions">
          <button type="button" class="icon-button compact" aria-label="重命名对话" :disabled="busy" @click="$emit('rename', conversation)">
            <Pencil :size="15" aria-hidden="true" />
          </button>
          <button type="button" class="icon-button compact" aria-label="创建对话分支" :disabled="busy" @click="$emit('fork', conversation)">
            <GitFork :size="15" aria-hidden="true" />
          </button>
          <button type="button" class="icon-button compact danger" aria-label="归档对话" :disabled="busy" @click="$emit('archive', conversation)">
            <Archive :size="15" aria-hidden="true" />
          </button>
        </div>
      </article>
    </div>
  </aside>
</template>

<script setup>
import { Archive, GitFork, MessageSquare, Pencil, Search, SquarePen } from 'lucide-vue-next'
import { ref } from 'vue'
const searchText = ref('')

defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: [String, Number], default: null },
  busy: Boolean,
})

defineEmits(['create', 'select', 'rename', 'archive', 'fork', 'search'])

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(date)
}
</script>

<style scoped>
.conversation-sidebar { display: flex; min-width: 0; flex-direction: column; border: var(--border-default); border-radius: var(--radius-md); background: var(--color-paper); overflow: hidden; }
.sidebar-header { display: flex; min-height: var(--header-height); align-items: center; justify-content: space-between; padding: 0 var(--space-3); border-bottom: 1px solid var(--color-divider); }
.sidebar-header > div { display: grid; gap: 2px; }
.sidebar-header strong { color: var(--color-ink); font-size: calc(var(--text-sm) * 1rem); }
.sidebar-header span { color: var(--color-ink-tertiary); font-size: calc(var(--text-xs) * 1rem); }
.conversation-list { min-height: 0; flex: 1; overflow-y: auto; padding: var(--space-2); }
.conversation-search { display: flex; align-items: center; gap: 8px; margin: var(--space-2); padding: 8px 10px; border: 1px solid var(--color-divider); border-radius: var(--radius-sm); color: var(--color-ink-tertiary); }
.conversation-search input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--color-ink); font: inherit; }
.conversation-item { display: flex; min-height: 58px; align-items: center; border-radius: var(--radius-sm); }
.conversation-item.active { background: var(--color-surface-soft); }
.conversation-main { display: flex; min-width: 0; flex: 1; align-items: center; gap: var(--space-2); align-self: stretch; padding: var(--space-2); border: 0; background: transparent; color: var(--color-ink-secondary); text-align: left; }
.conversation-main > span { display: grid; min-width: 0; flex: 1; gap: 3px; }
.conversation-main strong { overflow: hidden; color: var(--color-ink); font-size: calc(var(--text-sm) * 1rem); text-overflow: ellipsis; white-space: nowrap; }
.conversation-main small { color: var(--color-ink-tertiary); font-size: calc(var(--text-xs) * 1rem); }
.item-actions { display: flex; opacity: 0; transition: opacity 160ms ease-out; }
.conversation-item:hover .item-actions, .conversation-item:focus-within .item-actions { opacity: 1; }
.icon-button { display: grid; width: 44px; height: 44px; place-items: center; border: 0; border-radius: 50%; background: transparent; color: var(--color-ink-secondary); }
.icon-button.compact { width: 36px; height: 44px; }
.icon-button.danger { color: var(--color-danger); }
.icon-button:hover { background: var(--color-surface-soft); }
.icon-button:focus-visible, .conversation-main:focus-visible { outline: 3px solid var(--color-primary-soft); outline-offset: -2px; }
button:disabled { opacity: 0.45; cursor: not-allowed; }
.empty-state { padding: var(--space-8) var(--space-3); color: var(--color-ink-tertiary); text-align: center; }
@media (prefers-reduced-motion: reduce) { .item-actions { transition: none; } }
</style>
