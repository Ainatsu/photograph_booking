<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <main class="page-shell inspiration-shell">
        <AppTopBar left-label="返回" :show-search="false" @left-action="goBack">
          <template #left><ArrowLeft :size="21" aria-hidden="true" /></template>
          <template #center><strong class="top-title">灵感仓库</strong></template>
        </AppTopBar>
        <div class="view-switch" role="tablist" aria-label="灵感视图">
          <button type="button" role="tab" :aria-selected="view === 'repository'" :class="{ active: view === 'repository' }" @click="view = 'repository'">仓库</button>
          <button type="button" role="tab" :aria-selected="view === 'map'" :class="{ active: view === 'map' }" @click="view = 'map'">地图</button>
          <button type="button" class="create-button pressable" @click="openEditor()"><Plus :size="18" aria-hidden="true" />新建</button>
        </div>
        <template v-if="view === 'repository'">
          <SearchField v-model="query" label="搜索灵感" placeholder="搜索标题、摘要或地点" @submit="load" />
          <div class="status-filter" role="group" aria-label="状态筛选">
            <button v-for="option in statusOptions" :key="option.value" type="button" :class="{ active: status === option.value }" @click="status = option.value; load()">{{ option.label }}</button>
          </div>
          <FeedSkeleton v-if="loading" :count="3" />
          <StatePanel v-else-if="error" tone="error" title="灵感加载失败" description="请检查网络后重试。" action-label="重新加载" @action="load" />
          <section v-else-if="items.length" class="cards" aria-live="polite"><InspirationCard v-for="item in items" :key="item.id" :item="item" show-actions @open="openDetail" @edit="openEditor" @delete="deleteItem" /></section>
          <StatePanel v-else title="仓库还是空的" description="先收集一个画面、写下一段想法或关联一个地点。" action-label="创建第一条灵感" @action="openEditor()" />
        </template>
        <template v-else>
          <InspirationMapPanel @open-detail="openDetail" />
        </template>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { alertController, onIonViewWillEnter, IonContent, IonPage } from '@ionic/vue'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Plus } from 'lucide-vue-next'
import AppTopBar from '@/components/AppTopBar.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import SearchField from '@/components/SearchField.vue'
import StatePanel from '@/components/StatePanel.vue'
import InspirationCard from '@/components/InspirationCard.vue'
import InspirationMapPanel from '@/components/InspirationMapPanel.vue'
import { archiveInspiration, getInspirations } from '@/api/inspirations'
import type { Inspiration } from '@/types/inspiration'

const router = useRouter()
const view = ref<'repository' | 'map'>('repository')
const query = ref('')
const status = ref('')
const items = ref<Inspiration[]>([])
const loading = ref(false)
const error = ref('')
const statusOptions = computed(() => [{ label: '全部', value: '' }, { label: '草稿', value: 'draft' }, { label: '已保存', value: 'saved' }])

async function load() {
  loading.value = true; error.value = ''
  try { items.value = await getInspirations({ query: query.value || undefined, status: status.value || undefined, limit: 100 }) } catch { error.value = 'load failed' } finally { loading.value = false }
}
function openEditor(id?: number) { void router.push(id ? { name: 'inspiration-edit', params: { inspirationId: id } } : { name: 'inspiration-new' }) }
function openDetail(id: number) { void router.push({ name: 'inspiration-detail', params: { inspirationId: id } }) }
function goBack() { if (window.history.length > 1) router.back(); else void router.push('/tabs/profile') }
async function deleteItem(id: number) {
  const item = items.value.find((entry) => entry.id === id)
  if (!item) return
  const alert = await alertController.create({ header: '删除灵感', message: `确定删除「${item.title}」吗？删除后无法恢复。`, buttons: [{ text: '取消', role: 'cancel' }, { text: '删除', role: 'destructive' }] })
  await alert.present()
  const result = await alert.onDidDismiss()
  if (result.role !== 'destructive') return
  await archiveInspiration(id)
  items.value = items.value.filter((entry) => entry.id !== id)
}
onIonViewWillEnter(() => void load())
</script>

<style scoped>
.inspiration-shell { padding-bottom: calc(var(--bottom-nav-height) + var(--bottom-nav-offset) + env(safe-area-inset-bottom) + var(--space-8)); }
.top-title { color: var(--ink); font-size: var(--text-base); }
.view-switch { display: grid; grid-template-columns: 1fr 1fr auto; gap: var(--space-2); margin: var(--space-4) 0; padding: 4px; border-radius: var(--radius-md); background: var(--surface-secondary); }
.view-switch > button:not(.create-button) { min-height: var(--touch-target); border: 0; border-radius: var(--radius-sm); background: transparent; color: var(--ink-secondary); font-weight: 700; }
.view-switch > button.active { background: var(--surface-solid); box-shadow: var(--shadow-1); color: var(--brand); }
.create-button { display: inline-flex; min-height: var(--touch-target); align-items: center; gap: 5px; padding: 0 13px; border: 0; border-radius: var(--radius-sm); background: var(--brand); color: var(--white); font-weight: 800; }
.status-filter { display: flex; gap: 8px; margin: var(--space-3) 0 var(--space-4); }
.status-filter button { min-height: 36px; padding: 0 14px; border: 0; border-radius: var(--radius-pill); background: var(--surface-secondary); color: var(--ink-secondary); font-size: var(--text-xs); font-weight: 700; }
.status-filter button.active { background: var(--brand-soft); color: var(--brand); }
.cards { display: grid; gap: var(--space-3); }
</style>
