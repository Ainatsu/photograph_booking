<template>
  <Teleport to="body">
    <Transition name="conversation-panel">
      <div v-if="open" class="panel-layer" role="presentation" @click.self="$emit('close')">
        <aside class="conversation-panel" role="dialog" aria-modal="true" aria-labelledby="conversation-panel-title">
          <header class="panel-header">
            <div>
              <h2 id="conversation-panel-title">对话</h2>
              <p>{{ conversations.length }} 个进行中的对话</p>
            </div>
            <button type="button" class="icon-button" aria-label="关闭对话列表" @click="$emit('close')">
              <X :size="21" aria-hidden="true" />
            </button>
          </header>

          <button type="button" class="new-conversation-button" :disabled="busy" @click="$emit('create')">
            <SquarePen :size="19" aria-hidden="true" />
            <span>新建对话</span>
          </button>
          <label class="conversation-search">
            <Search :size="16" aria-hidden="true" />
            <input v-model="searchText" type="search" placeholder="搜索对话" @input="$emit('search', searchText)" />
          </label>

          <div class="conversation-list" aria-label="对话列表">
            <p v-if="!conversations.length" class="empty-state">还没有对话</p>
            <article
              v-for="conversation in conversations"
              :key="conversation.id"
              class="conversation-row"
              :class="{ active: String(conversation.id) === String(activeId) }"
            >
              <button
                type="button"
                class="conversation-main"
                :aria-current="String(conversation.id) === String(activeId) ? 'page' : undefined"
                :disabled="busy"
                @click="$emit('select', conversation)"
              >
                <MessageSquare :size="18" aria-hidden="true" />
                <span class="conversation-copy">
                  <strong>{{ conversation.title || '新对话' }}</strong>
                  <small>{{ formatConversationDate(conversation.updated_at) }}</small>
                </span>
              </button>
              <div class="conversation-actions">
                <button type="button" class="icon-button" :disabled="busy" aria-label="重命名对话" @click="$emit('rename', conversation)">
                  <Pencil :size="17" aria-hidden="true" />
                </button>
                <button type="button" class="icon-button danger" :disabled="busy" aria-label="归档对话" @click="$emit('archive', conversation)">
                  <Archive :size="17" aria-hidden="true" />
                </button>
                <button type="button" class="icon-button" :disabled="busy" aria-label="创建对话分支" @click="$emit('fork', conversation)">
                  <GitFork :size="17" aria-hidden="true" />
                </button>
              </div>
            </article>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { Archive, GitFork, MessageSquare, Pencil, Search, SquarePen, X } from 'lucide-vue-next'
import { ref } from 'vue'
import type { AIConversation } from '@/api/ai'
const searchText = ref('')

defineProps<{
  open: boolean
  conversations: AIConversation[]
  activeId?: string | number | null
  busy?: boolean
}>()

defineEmits<{
  close: []
  create: []
  select: [conversation: AIConversation]
  rename: [conversation: AIConversation]
  archive: [conversation: AIConversation]
  fork: [conversation: AIConversation]
  search: [query: string]
}>()

function formatConversationDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(date)
}
</script>

<style scoped>
.panel-layer {
  position: fixed;
  z-index: var(--layer-modal, 1000);
  inset: 0;
  display: flex;
  background: rgba(15, 23, 42, 0.48);
}

.conversation-panel {
  display: flex;
  width: min(88vw, 380px);
  min-height: 100dvh;
  flex-direction: column;
  gap: var(--space-4);
  padding: calc(var(--space-4) + env(safe-area-inset-top)) var(--space-4) calc(var(--space-4) + env(safe-area-inset-bottom));
  overflow: hidden;
  background: var(--surface-solid);
  color: var(--ink);
}

.panel-header,
.conversation-row,
.conversation-main,
.conversation-actions,
.new-conversation-button {
  display: flex;
  align-items: center;
}

.panel-header { justify-content: space-between; }
.panel-header h2 { margin: 0; font-size: var(--text-lg); }
.panel-header p { margin: 2px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); }

.icon-button {
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
.icon-button:active { background: var(--surface-secondary); }
.icon-button.danger { color: var(--danger, #b42318); }

.new-conversation-button {
  min-height: var(--touch-target);
  justify-content: center;
  gap: var(--space-2);
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--brand);
  color: var(--white);
  font-weight: 600;
}

.conversation-list {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
}
.conversation-search { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 10px; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); color: var(--ink-tertiary); }
.conversation-search input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--ink); font: inherit; }

.conversation-row {
  min-height: 64px;
  border-bottom: 1px solid var(--border-subtle);
}
.conversation-row.active { background: var(--brand-soft); }

.conversation-main {
  min-width: 0;
  flex: 1;
  gap: var(--space-3);
  align-self: stretch;
  padding: var(--space-2);
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

.conversation-copy { display: grid; min-width: 0; flex: 1; gap: 3px; }
.conversation-copy strong { overflow: hidden; font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.conversation-copy small { color: var(--ink-tertiary); font-size: var(--text-xs); }
.conversation-actions { flex: 0 0 auto; }
.empty-state { padding: var(--space-8) var(--space-4); color: var(--ink-secondary); text-align: center; }

.conversation-panel-enter-active,
.conversation-panel-leave-active { transition: opacity 180ms ease-out; }
.conversation-panel-enter-active .conversation-panel,
.conversation-panel-leave-active .conversation-panel { transition: transform 220ms ease-out; }
.conversation-panel-enter-from,
.conversation-panel-leave-to { opacity: 0; }
.conversation-panel-enter-from .conversation-panel,
.conversation-panel-leave-to .conversation-panel { transform: translateX(-100%); }

button:focus-visible { outline: 3px solid var(--brand-soft); outline-offset: 2px; }
button:disabled { opacity: 0.45; }

@media (prefers-reduced-motion: reduce) {
  .conversation-panel-enter-active,
  .conversation-panel-leave-active,
  .conversation-panel-enter-active .conversation-panel,
  .conversation-panel-leave-active .conversation-panel { transition: none; }
}
</style>
