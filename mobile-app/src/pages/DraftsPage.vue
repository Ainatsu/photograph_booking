<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <main class="page-shell">
        <AppTopBar @left-action="goAI" />

        <FeedSkeleton v-if="loading" :count="3" />

        <StatePanel
          v-else-if="drafts.length === 0"
          title="还没有保存的草稿"
          description="发布作品、方案或企划时，填写的文字内容会自动保存在本机。"
        />

        <section v-else class="draft-list">
          <article v-for="draft in drafts" :key="draft.id" class="draft-card">
            <header class="draft-header">
              <span class="draft-icon">
                <component :is="draft.icon" :size="22" aria-hidden="true" />
              </span>
              <div class="draft-meta">
                <strong>{{ draft.label }}</strong>
                <small>保存于 {{ draft.formattedTime }}</small>
                <p v-if="draft.summary" class="draft-summary">{{ draft.summary }}</p>
              </div>
            </header>
            <div class="draft-actions">
              <button type="button" class="draft-action continue pressable" @click="continueDraft(draft)">
                <PenLine :size="16" aria-hidden="true" />
                继续编辑
              </button>
              <button type="button" class="draft-action delete pressable" @click="deleteDraft(draft)">
                <Trash2 :size="16" aria-hidden="true" />
                删除
              </button>
            </div>
          </article>
        </section>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { IonContent, IonPage, alertController, onIonViewWillEnter } from '@ionic/vue'
import { BriefcaseBusiness, FileText, Image, PenLine, Trash2 } from 'lucide-vue-next'
import type { Component } from 'vue'
import AppTopBar from '@/components/AppTopBar.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import { listPublishDrafts, deletePublishDraft, formatDraftTime } from '@/utils/publishing'
import type { DraftItem } from '@/utils/publishing'
import type { PublishResourceType } from '@/types/publishing'

interface DraftInfo {
  id: string
  type: PublishResourceType
  label: string
  icon: Component
  formattedTime: string
  summary: string
}

const router = useRouter()
const loading = ref(true)

function goAI() {
  void router.push({ name: 'ai-assistant' })
}

const typeLabels: Record<PublishResourceType, { label: string; icon: Component }> = {
  work: { label: '摄影作品草稿', icon: Image },
  package: { label: '摄影方案草稿', icon: FileText },
  project: { label: '拍摄企划草稿', icon: BriefcaseBusiness },
}

const publishRouteMap: Record<PublishResourceType, string> = {
  work: 'publish-work',
  package: 'publish-package',
  project: 'publish-project',
}

function getDraftSummary(type: PublishResourceType, value: Record<string, unknown>): string {
  const text = type === 'package'
    ? String(value.name ?? value.package_name ?? '')
    : String(value.title ?? '')
  return text.length > 40 ? text.slice(0, 40) + '…' : text
}

const drafts = computed(() => {
  const all = listPublishDrafts()
  return all.map((item: DraftItem) => {
    const meta = typeLabels[item.type] || { label: item.type, icon: Image }
    return {
      id: item.id,
      type: item.type,
      label: meta.label,
      icon: meta.icon,
      formattedTime: formatDraftTime(item.updatedAt),
      summary: getDraftSummary(item.type, item.value as Record<string, unknown>),
    } satisfies DraftInfo
  })
})

async function continueDraft(draft: DraftInfo) {
  const routeName = publishRouteMap[draft.type]
  await router.push({ name: routeName, query: { draftId: draft.id } })
}

async function deleteDraft(draft: DraftInfo) {
  const labels: Record<PublishResourceType, string> = {
    work: '摄影作品',
    package: '摄影方案',
    project: '拍摄企划',
  }
  const alert = await alertController.create({
    header: '删除草稿',
    message: `确定要删除${labels[draft.type]}草稿吗？删除后无法恢复。`,
    buttons: [
      { text: '取消', role: 'cancel' },
      { text: '删除', role: 'destructive' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  if (result.role !== 'destructive') return
  deletePublishDraft(draft.type, draft.id)
  loading.value = true
  loading.value = false
}

onIonViewWillEnter(() => {
  loading.value = false
})
</script>

<style scoped>
.draft-list {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.draft-card {
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
}

.draft-header {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-4) var(--space-4) var(--space-3);
}

.draft-icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--brand);
}

.draft-meta {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.draft-meta strong {
  font-size: var(--text-sm);
  line-height: 1.3;
}

.draft-meta small {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

.draft-summary {
  margin: 4px 0 0;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.55;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.draft-actions {
  display: flex;
  border-top: 1px solid var(--divider);
}

.draft-action {
  display: flex;
  flex: 1;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border: 0;
  background: transparent;
  font-size: var(--text-sm);
  font-weight: 600;
}

.draft-action + .draft-action { border-left: 1px solid var(--divider); }

.draft-action.continue {
  color: var(--brand);
}

.draft-action.delete {
  color: var(--danger);
}

.draft-action:active { background: var(--paper); box-shadow: var(--neu-inset); }
</style>
