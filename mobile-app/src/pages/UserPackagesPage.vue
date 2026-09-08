<template>
  <ion-page>
    <DetailHeader :title="pageTitle" :default-href="profileHref" />

    <ion-content class="user-packages-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="user-packages-shell">
        <section class="list-intro">
          <span><Package :size="24" aria-hidden="true" /></span>
          <div>
            <p>Service packages</p>
            <h1>{{ packages.length }} 个可预约方案</h1>
            <small>只展示已上架的方案，选中后可查看交付标准并进入档期预约。</small>
          </div>
        </section>

        <FeedSkeleton v-if="loading" :count="3" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="方案列表加载失败"
          :description="error"
          action-label="重新加载"
          @action="load"
        />
        <StatePanel
          v-else-if="!packages.length"
          title="还没有上架方案"
          :description="`${displayName}暂时没有可预约的拍摄方案，可以先发消息沟通需求。`"
        />

        <section v-else class="package-list" :aria-label="`${displayName}的摄影方案列表`">
          <article v-for="offer in packages" :key="offer.id" class="package-card">
            <button type="button" class="package-card-main pressable" @click="openPackage(offer)">
              <div class="package-cover">
                <img
                  v-if="packageCover(offer) && !failedPackageIds.includes(String(offer.id))"
                  :src="packageCover(offer)"
                  :alt="`${getPackageName(offer)}样片`"
                  loading="lazy"
                  @error="markImageFailed(offer.id)"
                />
                <MediaPlaceholder v-else />
              </div>

              <div class="package-copy">
                <header>
                  <h2>{{ getPackageName(offer) }}</h2>
                  <strong>{{ formatCurrency(offer.price) }}</strong>
                </header>
                <p>{{ offer.description || '暂未补充方案描述，可在预约备注中沟通具体需求。' }}</p>
                <div class="package-facts">
                  <span><Clock3 :size="16" aria-hidden="true" />{{ formatDuration(offer.duration) }}</span>
                  <span><MapPin :size="16" aria-hidden="true" />{{ offer.service_location || offer.city || '不限' }}</span>
                  <span><Images :size="16" aria-hidden="true" />{{ retouchedCount(offer) }}</span>
                </div>
              </div>
            </button>
          </article>
        </section>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  onIonViewWillEnter,
  type RefresherCustomEvent,
} from '@ionic/vue'
import { Clock3, Images, MapPin, Package } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import MediaPlaceholder from '@/components/MediaPlaceholder.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographerDetail } from '@/api/discovery'
import type { PackageOffer, PhotographerProfile } from '@/types/discovery'
import { formatCurrency, formatDuration, getPackageName } from '@/utils/format'
import { getPackagePreviewUrl } from '@/utils/media'
import { getProfilePackages } from '@/utils/photographerProfile'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'

const route = useRoute()
const router = useRouter()
const profile = ref<PhotographerProfile | null>(null)
const loading = ref(true)
const error = ref('')
const failedPackageIds = ref<string[]>([])

const userId = computed(() => Number(route.params.userId))
const packages = computed<PackageOffer[]>(() => getProfilePackages(profile.value))
const displayName = computed(() => profile.value?.user_display_name || '该用户')
const pageTitle = computed(() => `${displayName.value}的方案`)
const profileHref = computed(() => `/photographers/${route.params.userId}`)

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

async function load() {
  if (!Number.isInteger(userId.value) || userId.value <= 0) {
    error.value = '用户编号无效。'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    profile.value = await getPhotographerDetail(userId.value)
    failedPackageIds.value = []
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  await event.target.complete()
}

function openPackage(offer: PackageOffer) {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'package_detail', page: 'user_packages' })
  void router.push({ name: 'package-detail', params: { packageId: offer.id } })
}

onIonViewWillEnter(() => void load())
</script>

<style scoped>
.user-packages-content { --background: var(--paper); }
.user-packages-shell { display: grid; width: min(100%, 720px); margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); gap: var(--space-5); }

.list-intro { display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.list-intro > span { display: grid; width: 46px; height: 46px; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.list-intro p { margin: 0 0 3px; color: var(--brand); font-size: var(--text-2xs); font-weight: 850; letter-spacing: .12em; text-transform: uppercase; }
.list-intro h1 { margin: 0; font-family: var(--font-serif); font-size: var(--text-xl); line-height: 1.35; }
.list-intro small { display: block; margin-top: 6px; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }

.package-list { display: grid; gap: var(--space-4); }
.package-card { overflow: hidden; border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.package-card-main { display: grid; width: 100%; padding: 0; border: 0; background: transparent; color: var(--ink); text-align: left; }
.package-cover { position: relative; overflow: hidden; aspect-ratio: 16 / 8.5; background: var(--paper); box-shadow: var(--neu-inset); }
.package-cover img { width: 100%; height: 100%; object-fit: cover; }
.package-copy { padding: var(--space-4); }
.package-copy header { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: var(--space-3); }
.package-copy h2 { margin: 0; font-size: var(--text-base); line-height: 1.45; }
.package-copy header strong { color: var(--brand); font-size: var(--text-lg); font-variant-numeric: tabular-nums; }
.package-copy > p { display: -webkit-box; margin: var(--space-2) 0 var(--space-3); overflow: hidden; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.package-facts { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--divider); color: var(--ink-tertiary); font-size: var(--text-xs); }
.package-facts span { display: inline-flex; min-width: 0; align-items: center; gap: 5px; }
.package-facts svg { flex: 0 0 auto; color: var(--brand); }

@media (min-width: 640px) {
  .list-intro { grid-template-columns: 46px minmax(0, 1fr); align-items: center; }
  .package-card-main { grid-template-columns: 210px minmax(0, 1fr); }
  .package-cover { height: 100%; aspect-ratio: auto; }
}
</style>
