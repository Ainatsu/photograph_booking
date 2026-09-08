<template>
  <ion-page>
    <DetailHeader title="方案管理" default-href="/tabs/profile" />

    <ion-content class="package-management-content">
      <ion-refresher v-if="auth.isPhotographer" slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="package-management-shell">
        <StatePanel
          v-if="auth.initialized && !auth.isPhotographer"
          title="需要摄影师身份"
          description="只有通过摄影师认证的账号可以创建和管理可预约方案。"
          action-label="返回我的"
          @action="router.replace({ name: 'profile' })"
        />

        <template v-else>
          <section class="management-intro">
            <span><Package :size="24" aria-hidden="true" /></span>
            <div>
              <p>Service packages</p>
              <h1>管理价格、交付与预约入口</h1>
              <small>下架后客户将无法从橱窗和摄影师主页预约，但方案内容仍会保留在这里。</small>
            </div>
            <button type="button" class="intro-action pressable" :disabled="Boolean(busyPackageId)" @click="createPackage">
              <Plus :size="18" aria-hidden="true" />新建方案
            </button>
          </section>

          <nav class="status-tabs" aria-label="方案状态筛选">
            <button
              v-for="option in packageStatusOptions"
              :key="option.value"
              type="button"
              class="pressable"
              :class="{ active: status === option.value }"
              :aria-pressed="status === option.value"
              @click="setStatus(option.value)"
            >
              {{ option.label }}
              <span>{{ statusCount(option.value) }}</span>
            </button>
          </nav>

          <FeedSkeleton v-if="loading" :count="3" />
          <StatePanel
            v-else-if="error"
            tone="error"
            title="方案列表加载失败"
            :description="error"
            action-label="重新加载"
            @action="loadPackages"
          />
          <StatePanel
            v-else-if="!visiblePackages.length"
            :title="allPackages.length ? '这个状态下暂无方案' : '还没有创建摄影方案'"
            :description="allPackages.length ? '切换其他状态查看，或创建一份新的可预约方案。' : '先设置价格、时长、交付标准和服务条款，再将方案上架给客户。'"
            :action-label="allPackages.length ? '查看全部' : '创建方案'"
            @action="allPackages.length ? setStatus('all') : createPackage()"
          />

          <section v-else class="package-list" aria-label="我的摄影方案列表">
            <article v-for="offer in visiblePackages" :key="offer.id" class="managed-package-card">
              <button type="button" class="package-card-main pressable" :disabled="Boolean(busyPackageId)" @click="editPackage(offer)">
                <div class="package-cover">
                  <img
                    v-if="packageCover(offer) && !failedPackageIds.includes(String(offer.id))"
                    :src="packageCover(offer)"
                    :alt="`${getPackageName(offer)}样片`"
                    loading="lazy"
                    @error="markImageFailed(offer.id)"
                  />
                  <MediaPlaceholder v-else />
                  <span class="state-badge" :class="{ inactive: !isPackageActive(offer) }">
                    {{ isPackageActive(offer) ? '已上架' : '已下架' }}
                  </span>
                </div>

                <div class="package-copy">
                  <header>
                    <h2>{{ getPackageName(offer) }}</h2>
                    <strong>{{ formatCurrency(offer.price) }}</strong>
                  </header>
                  <p>{{ offer.description || '暂未补充方案描述，建议编辑后说明适合人群与服务边界。' }}</p>
                  <div class="package-facts">
                    <span><Clock3 :size="16" aria-hidden="true" />{{ formatDuration(offer.duration) }}</span>
                    <span><MapPin :size="16" aria-hidden="true" />{{ offer.service_location || offer.city || '不限' }}</span>
                    <span><Images :size="16" aria-hidden="true" />{{ retouchedCount(offer) }}</span>
                  </div>
                </div>
              </button>

              <footer class="package-actions">
                <button type="button" class="pressable" :disabled="Boolean(busyPackageId)" @click="editPackage(offer)">
                  <PencilLine :size="17" aria-hidden="true" />编辑
                </button>
                <button
                  type="button"
                  class="pressable"
                  :class="{ primary: !isPackageActive(offer) }"
                  :disabled="Boolean(busyPackageId)"
                  @click="togglePackageState(offer)"
                >
                  <ion-spinner v-if="busyPackageId === String(offer.id) && busyAction === 'state'" name="crescent" aria-hidden="true" />
                  <EyeOff v-else-if="isPackageActive(offer)" :size="17" aria-hidden="true" />
                  <Eye v-else :size="17" aria-hidden="true" />
                  {{ isPackageActive(offer) ? '下架' : '上架' }}
                </button>
                <button type="button" class="danger pressable" :disabled="Boolean(busyPackageId)" @click="confirmDelete(offer)">
                  <ion-spinner v-if="busyPackageId === String(offer.id) && busyAction === 'delete'" name="crescent" aria-hidden="true" />
                  <Trash2 v-else :size="17" aria-hidden="true" />删除
                </button>
              </footer>
            </article>
          </section>
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2800"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
  alertController,
  type RefresherCustomEvent,
} from '@ionic/vue'
import { Clock3, Eye, EyeOff, Images, MapPin, Package, PencilLine, Plus, Trash2 } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import MediaPlaceholder from '@/components/MediaPlaceholder.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import {
  deletePhotographerPackage,
  getPhotographerPackages,
  setPhotographerPackageActive,
} from '@/api/packages'
import { useAuthStore } from '@/stores/auth'
import type { PackageOffer } from '@/types/discovery'
import { formatCurrency, formatDuration, getPackageName } from '@/utils/format'
import { getPackagePreviewUrl } from '@/utils/media'
import {
  filterPackages,
  isPackageActive,
  packageStatusOptions,
  type PackageStatusFilter,
} from '@/utils/package'

type BusyAction = 'state' | 'delete' | ''

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const allPackages = ref<PackageOffer[]>([])
const status = ref<PackageStatusFilter>('all')
const loading = ref(false)
const error = ref('')
const toastMessage = ref('')
const busyPackageId = ref<string | null>(null)
const busyAction = ref<BusyAction>('')
const failedPackageIds = ref<string[]>([])

const visiblePackages = computed(() => filterPackages(allPackages.value, status.value))

function parseStatus(value: unknown): PackageStatusFilter {
  return value === 'active' || value === 'inactive' ? value : 'all'
}

function statusCount(value: PackageStatusFilter) {
  return filterPackages(allPackages.value, value).length
}

function packageCover(offer: PackageOffer) {
  return getPackagePreviewUrl(offer)
}

function markImageFailed(packageId: string) {
  const id = String(packageId)
  if (!failedPackageIds.value.includes(id)) failedPackageIds.value.push(id)
}

function retouchedCount(offer: PackageOffer) {
  const count = offer.retouched_image_count ?? offer.image_count
  return count === undefined || count === null ? '精修待沟通' : `精修 ${count} 张`
}

async function loadPackages() {
  if (!auth.user || !auth.isPhotographer) return
  loading.value = true
  error.value = ''
  try {
    allPackages.value = await getPhotographerPackages(auth.user.id)
    failedPackageIds.value = []
  } catch (loadError) {
    allPackages.value = []
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function setStatus(nextStatus: PackageStatusFilter) {
  status.value = nextStatus
  await router.replace({
    query: { ...route.query, status: nextStatus === 'all' ? undefined : nextStatus },
  })
}

function createPackage() {
  void router.push({ name: 'publish-package' })
}

function editPackage(offer: PackageOffer) {
  void router.push({ name: 'package-edit', params: { packageId: offer.id } })
}

async function confirmAction(header: string, message: string, confirmText: string, destructive = false) {
  const alert = await alertController.create({
    header,
    message,
    buttons: [
      { text: '取消', role: 'cancel' },
      { text: confirmText, role: destructive ? 'destructive' : 'confirm' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === (destructive ? 'destructive' : 'confirm')
}

async function togglePackageState(offer: PackageOffer) {
  if (!auth.user || busyPackageId.value) return
  const nextActive = !isPackageActive(offer)
  if (!nextActive) {
    const confirmed = await confirmAction(
      '下架摄影方案',
      '下架后客户无法继续浏览或使用这份方案创建新预约，已有订单不受影响。',
      '确认下架',
    )
    if (!confirmed) return
  }

  busyPackageId.value = String(offer.id)
  busyAction.value = 'state'
  try {
    const profile = await setPhotographerPackageActive(auth.user.id, String(offer.id), nextActive)
    allPackages.value = profile.packages || []
    toastMessage.value = nextActive ? '方案已上架' : '方案已下架'
  } catch (actionError) {
    toastMessage.value = getApiErrorMessage(actionError)
  } finally {
    busyPackageId.value = null
    busyAction.value = ''
  }
}

async function confirmDelete(offer: PackageOffer) {
  if (!auth.user || busyPackageId.value) return
  const confirmed = await confirmAction(
    '删除摄影方案',
    `确定删除「${getPackageName(offer)}」吗？删除后无法恢复，已生成订单中的方案快照不会受影响。`,
    '确认删除',
    true,
  )
  if (!confirmed) return

  busyPackageId.value = String(offer.id)
  busyAction.value = 'delete'
  try {
    const profile = await deletePhotographerPackage(auth.user.id, String(offer.id))
    allPackages.value = profile.packages || []
    toastMessage.value = '方案已删除'
  } catch (actionError) {
    toastMessage.value = getApiErrorMessage(actionError)
  } finally {
    busyPackageId.value = null
    busyAction.value = ''
  }
}

async function refresh(event: RefresherCustomEvent) {
  await loadPackages()
  await event.target.complete()
}

onMounted(async () => {
  status.value = parseStatus(route.query.status)
  if (route.query.saved === '1') {
    toastMessage.value = '方案修改已保存'
    const nextQuery = { ...route.query }
    delete nextQuery.saved
    await router.replace({ query: nextQuery })
  }
  await auth.initialize()
  if (auth.isPhotographer) await loadPackages()
})
</script>

<style scoped>
.package-management-content { --background: var(--paper); }
.package-management-shell { display: grid; width: min(100%, 720px); margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); gap: var(--space-5); }

.management-intro { display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.management-intro > span { display: grid; width: 46px; height: 46px; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.management-intro p { margin: 0 0 3px; color: var(--brand); font-size: var(--text-2xs); font-weight: 850; letter-spacing: .12em; text-transform: uppercase; }
.management-intro h1 { margin: 0; font-family: var(--font-serif); font-size: var(--text-xl); line-height: 1.35; }
.management-intro small { display: block; margin-top: 6px; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
.intro-action { grid-column: 1 / -1; display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); font-weight: 750; }
.intro-action:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); }

.status-tabs { display: grid; grid-template-columns: repeat(3, 1fr); overflow: hidden; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.status-tabs button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: 5px; border: 0; border-right: 1px solid var(--divider); background: transparent; color: var(--ink-secondary); font-size: var(--text-xs); font-weight: 750; }
.status-tabs button:last-child { border-right: 0; }
.status-tabs button.active { background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.status-tabs span { display: grid; min-width: 20px; min-height: 20px; place-items: center; padding: 0 5px; border-radius: var(--radius-pill); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-tertiary); font-size: var(--text-2xs); }
.status-tabs button.active span { background: rgba(255, 255, 255, .18); color: var(--white); }

.package-list { display: grid; gap: var(--space-4); }
.managed-package-card { overflow: hidden; border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.package-card-main { display: grid; width: 100%; padding: 0; border: 0; background: transparent; color: var(--ink); text-align: left; }
.package-card-main:disabled { opacity: .72; }
.package-cover { position: relative; overflow: hidden; aspect-ratio: 16 / 8.5; background: var(--paper); box-shadow: var(--neu-inset); }
.package-cover img { width: 100%; height: 100%; object-fit: cover; }
.state-badge { position: absolute; top: var(--space-3); left: var(--space-3); display: inline-flex; min-height: 27px; align-items: center; padding: 3px 9px; border: 1px solid color-mix(in srgb, var(--brand) 30%, transparent); border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-size: var(--text-2xs); font-weight: 800; }
.state-badge.inactive { border-color: rgba(98, 91, 78, .22); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink-tertiary); }
.package-copy { padding: var(--space-4); }
.package-copy header { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: var(--space-3); }
.package-copy h2 { margin: 0; font-size: var(--text-base); line-height: 1.45; }
.package-copy header strong { color: var(--brand); font-size: var(--text-lg); font-variant-numeric: tabular-nums; }
.package-copy > p { display: -webkit-box; margin: var(--space-2) 0 var(--space-3); overflow: hidden; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.package-facts { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--divider); color: var(--ink-tertiary); font-size: var(--text-xs); }
.package-facts span { display: inline-flex; min-width: 0; align-items: center; gap: 5px; }
.package-facts svg { flex: 0 0 auto; color: var(--brand); }

.package-actions { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--divider); }
.package-actions button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: 6px; border: 0; border-right: 1px solid var(--divider); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink-secondary); font-size: var(--text-xs); font-weight: 750; }
.package-actions button:last-child { border-right: 0; }
.package-actions button.primary { background: var(--brand-soft); color: var(--brand); }
.package-actions button.danger { color: var(--danger); }
.package-actions button:disabled { color: var(--ink-tertiary); opacity: .65; }
.package-actions ion-spinner { width: 17px; height: 17px; }

@media (min-width: 640px) {
  .management-intro { grid-template-columns: 46px minmax(0, 1fr) auto; align-items: center; }
  .intro-action { grid-column: auto; min-width: 132px; padding: 0 var(--space-4); }
  .package-card-main { grid-template-columns: 210px minmax(0, 1fr); }
  .package-cover { height: 100%; aspect-ratio: auto; }
}
</style>
