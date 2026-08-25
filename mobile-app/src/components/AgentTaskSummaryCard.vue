<template>
  <section class="agent-task-summary" :aria-label="task.summary.title" aria-live="polite">
    <div class="summary-heading">
      <div>
        <p class="eyebrow">正在整理</p>
        <h3>{{ task.summary.title }}</h3>
      </div>
      <span class="status">{{ statusLabel }}</span>
    </div>
    <div v-if="task.summary.lines.length" class="summary-lines">
      <div v-for="line in task.summary.lines.slice(0, 4)" :key="line.label" class="summary-line">
        <span>{{ line.label }}</span><strong>{{ line.value }}</strong>
      </div>
    </div>
    <p v-else class="empty-summary">已开始整理，继续聊即可补充信息</p>
    <p class="summary-count">
      已整理 {{ task.summary.collected_count }} 项
      <span v-if="task.summary.missing_required_count">，还需 {{ task.summary.missing_required_labels.join('、') }}</span>
    </p>
    <p v-if="task.summary.media_count" class="media-count">已收集 {{ task.summary.media_count }} 个附件</p>
    <div v-if="task.summary.next_question" class="next-question">
      <MessageCircleQuestion :size="18" aria-hidden="true" />
      <p><span>下一项</span>{{ task.summary.next_question }}</p>
    </div>
    <div class="summary-actions">
      <button type="button" class="secondary-button cancel-button" :disabled="busy" @click="$emit('cancel')">
        <X :size="17" aria-hidden="true" />取消
      </button>
      <button type="button" class="secondary-button edit-button" :disabled="busy" @click="$emit('edit')">
        <Pencil :size="17" aria-hidden="true" />{{ task.summary.edit_label || '进入编辑' }}
      </button>
      <button
        v-if="!task.summary.requires_editor"
        type="button"
        class="primary-button"
        :disabled="busy"
        @click="handlePrimaryAction"
      >
        <ion-spinner v-if="busy" name="crescent" aria-hidden="true" />
        <template v-else>
          <Send v-if="task.summary.can_commit" :size="17" aria-hidden="true" />
          <MessageCircleMore v-else :size="18" aria-hidden="true" />
          <span>{{ actionLabel }}</span>
        </template>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { IonSpinner } from '@ionic/vue'
import { MessageCircleMore, MessageCircleQuestion, Pencil, Send, X } from 'lucide-vue-next'
import type { AgentTask } from '@/types/agentTask'

const props = defineProps<{ task: AgentTask; busy?: boolean }>()
const emit = defineEmits<{ cancel: []; edit: []; continue: []; commit: [] }>()

function handlePrimaryAction() {
  if (props.task.summary.can_commit) emit('commit')
  else emit('continue')
}

const statusLabel = computed(() => {
  if (props.task.summary.requires_editor) return '需要素材'
  if (props.task.summary.can_commit) return '等待确认'
  return '信息整理中'
})
const actionLabel = computed(() => {
  if (props.task.summary.can_commit) return props.task.summary.commit_label || '确认提交'
  return '继续补充'
})
</script>

<style scoped>
.agent-task-summary { width: 100%; margin-top: 8px; padding: 14px; border: 1px solid var(--divider); border-radius: var(--radius-md); background: var(--surface-solid); color: var(--ink); box-shadow: var(--neu-raise-sm); }
.summary-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.eyebrow { margin: 0 0 3px; color: var(--ink-tertiary); font-size: 11px; }
h3 { margin: 0; font-size: var(--text-base); }
.status { color: var(--brand); font-size: var(--text-xs); white-space: nowrap; }
.summary-lines { display: grid; gap: 6px; margin-top: 12px; }
.summary-line { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; font-size: var(--text-xs); line-height: 1.45; }
.summary-line span { color: var(--ink-tertiary); }
.summary-line strong { min-width: 0; overflow-wrap: anywhere; font-weight: 600; }
.empty-summary, .summary-count, .media-count { margin: 12px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.5; }
.summary-count { color: var(--ink-tertiary); }
.media-count { margin-top: 4px; }
.next-question { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; align-items: start; margin-top: 12px; padding: 10px 12px; border-left: 3px solid var(--brand); background: var(--neu-surface); color: var(--ink-secondary); }
.next-question p { margin: 0; font-size: var(--text-sm); line-height: 1.5; overflow-wrap: anywhere; }
.next-question span { display: block; margin-bottom: 2px; color: var(--brand); font-size: 11px; font-weight: 750; }
.summary-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }
.summary-actions button { display: inline-flex; min-width: 0; min-height: 48px; padding: 0 12px; align-items: center; justify-content: center; gap: 6px; border: 0; border-radius: var(--radius-sm); font: inherit; font-size: var(--text-sm); font-weight: 650; cursor: pointer; touch-action: manipulation; }
.summary-actions button:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.secondary-button { border: 1px solid var(--divider) !important; background: var(--surface-solid); color: var(--ink-secondary); }
.cancel-button { color: var(--danger); }
.primary-button { grid-column: 1 / -1; background: var(--brand); color: var(--white); }
.summary-actions button:disabled { opacity: .55; cursor: not-allowed; }
@media (prefers-reduced-motion: reduce) { .agent-task-summary { transition: none; } }
</style>
