<template>
  <ion-page>
    <DetailHeader title="收藏、赞过与关注" default-href="/tabs/profile" />

    <ion-content class="social-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新收藏与关注" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="social-shell">
        <section class="social-intro">
          <span><HeartHandshake :size="23" aria-hidden="true" /></span>
          <div>
          <h1>把喜欢的内容留在身边</h1>
          <p>收藏、点赞和关注都会同步到网页版账号，并保留各自用途。</p>
          </div>
        </section>

        <SegmentSwitch v-model="activeTab" :items="segments" label="收藏与关注分类" />

        <FeedSkeleton v-if="loading" :count="4" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="收藏与关注暂时无法加载"
          :description="error"
          action-label="重新加载"
          @action="loadAll"
        />
        <StatePanel
          v-else-if="activeItemsCount === 0"
          :title="emptyTitle"
          :description="emptyDescription"
          :action-label="emptyActionLabel"
          @action="openDiscovery"
        />

        <div v-else-if="activeTab === 'works' || activeTab === 'liked'" class="work-grid">
          <WorkCard
            v-for="work in activeWorkCards"
            :key="work.id"
            :work="work"
            @open="openWork"
          />
        </div>

        <div v-else-if="activeTab === 'packages'" class="package-list">
          <PackageCard
            v-for="offer in packageCards"
            :key="offer.id"
            :offer="offer"
            @open="openPackage"
          />
        </div>

        <div v-else class="people-list">
          <article v-for="item in activePeople" :key="item.user_id" class="person-card">
            <button type="button" class="person-main pressable" @click="openPerson(item)">
              <AvatarImage :src="item.avatar_url" :name="item.display_name" :size="50" />
              <span class="person-copy">
                <span><strong>{{ item.display_name || '用户' }}</strong><small>{{ roleLabel(item.role) }}</small></span>
                <em>{{ item.bio || (item.role === 'photographer' ? '进入主页查看作品与方案' : '这个用户还没有补充个人简介') }}</em>
              </span>
              <ChevronRight v-if="item.role === 'photographer'" :size="19" aria-hidden="true" />
            </button>
            <button
              v-if="item.user_id !== auth.user?.id"
              type="button"
              class="follow-button pressable"
              :class="{ active: item.is_followed }"
              :disabled="Boolean(followLoading[item.user_id])"
              :aria-pressed="item.is_followed"
              @click="togglePersonFollow(item)"
            >
              <ion-spinner v-if="followLoading[item.user_id]" name="crescent" aria-hidden="true" />
              <UserCheck v-else-if="item.is_followed" :size="17" aria-hidden="true" />
              <UserPlus v-else :size="17" aria-hidden="true" />
              {{ item.is_followed ? '已关注' : '关注' }}
            </button>
          </article>
        </div>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2600"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
  onIonViewWillEnter,
  type RefresherCustomEvent,
} from '@ionic/vue'
import { ChevronRight, HeartHandshake, UserCheck, UserPlus } from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import PackageCard from '@/components/PackageCard.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import WorkCard from '@/components/WorkCard.vue'
import { getApiErrorMessage } from '@/api/client'
import { getLikedWorks } from '@/api/engagement'
import {
  getFollowers,
  getFollowing,
  getPackageFavorites,
  getWorkFavorites,
  toggleFollow,
} from '@/api/social'
import { useAuthStore } from '@/stores/auth'
import type { PackageOffer, WorkItem } from '@/types/discovery'
import type { LikedWorkItem } from '@/types/engagement'
import type { FavoritePackageItem, FavoriteWorkItem, FollowListItem } from '@/types/social'
import { favoritePackageToOffer, favoriteWorkToWork, likedWorkToWork } from '@/utils/social'

type SocialTab = 'works' | 'packages' | 'liked' | 'following' | 'followers'

const validTabs = new Set<SocialTab>(['works', 'packages', 'liked', 'following', 'followers'])
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const activeTab = ref<SocialTab>(normalizeTab(route.query.tab))
const workFavorites = ref<FavoriteWorkItem[]>([])
const packageFavorites = ref<FavoritePackageItem[]>([])
const likedWorks = ref<LikedWorkItem[]>([])
const following = ref<FollowListItem[]>([])
const followers = ref<FollowListItem[]>([])
const totals = ref<Record<SocialTab, number>>({ works: 0, packages: 0, liked: 0, following: 0, followers: 0 })
const followLoading = ref<Record<number, boolean>>({})
const loading = ref(true)
const error = ref('')
const toastMessage = ref('')

const segments = computed(() => [
  { label: '收藏', value: 'works', count: totals.value.works },
  { label: '方案', value: 'packages', count: totals.value.packages },
  { label: '赞过', value: 'liked', count: totals.value.liked },
  { label: '关注', value: 'following', count: totals.value.following },
  { label: '粉丝', value: 'followers', count: totals.value.followers },
])
const workCards = computed<WorkItem[]>(() => workFavorites.value.map(favoriteWorkToWork))
const likedWorkCards = computed<WorkItem[]>(() => likedWorks.value.map(likedWorkToWork))
const activeWorkCards = computed(() => activeTab.value === 'liked' ? likedWorkCards.value : workCards.value)
const packageCards = computed<PackageOffer[]>(() => packageFavorites.value.map(favoritePackageToOffer))
const activePeople = computed(() => activeTab.value === 'following' ? following.value : followers.value)
const activeItemsCount = computed(() => totals.value[activeTab.value])
const emptyTitle = computed(() => ({
  works: '还没有收藏作品',
  packages: '还没有收藏方案',
  liked: '还没有点赞作品',
  following: '还没有关注用户',
  followers: '暂时还没有粉丝',
})[activeTab.value])
const emptyDescription = computed(() => ({
  works: '在作品详情点击书签按钮后，会同步保存在这里。',
  packages: '在摄影方案详情点击书签按钮后，会同步保存在这里。',
  liked: '点赞用于表达喜欢；收藏则更适合留作预约前的候选清单。',
  following: '进入摄影师主页即可关注，对方的新内容更容易再次找到。',
  followers: '公开展示作品和完善摄影师主页，有助于其他用户关注你。',
})[activeTab.value])
const emptyActionLabel = computed(() => activeTab.value === 'packages' ? '浏览方案' : '去发现')

function normalizeTab(value: unknown): SocialTab {
  const tab = String(value || '') as SocialTab
  return validTabs.has(tab) ? tab : 'works'
}

async function loadAll() {
  await auth.initialize()
  if (!auth.user) {
    loading.value = false
    await router.replace({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  loading.value = true
  error.value = ''
  try {
    const [worksResult, packagesResult, likedResult, followingResult, followersResult] = await Promise.all([
      getWorkFavorites(),
      getPackageFavorites(),
      getLikedWorks(),
      getFollowing(auth.user.id),
      getFollowers(auth.user.id),
    ])
    workFavorites.value = worksResult.items || []
    packageFavorites.value = packagesResult.items || []
    likedWorks.value = likedResult.items || []
    following.value = followingResult.items || []
    followers.value = followersResult.items || []
    totals.value = {
      works: worksResult.total || workFavorites.value.length,
      packages: packagesResult.total || packageFavorites.value.length,
      liked: likedResult.total || likedWorks.value.length,
      following: followingResult.total || following.value.length,
      followers: followersResult.total || followers.value.length,
    }
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function refresh(event: RefresherCustomEvent) {
  await loadAll()
  event.target.complete()
}

function openWork(work: WorkItem) {
  void router.push({ name: 'work-detail', params: { workId: work.id } })
}

function openPackage(offer: PackageOffer) {
  void router.push({ name: 'package-detail', params: { packageId: offer.id } })
}

function openPerson(item: FollowListItem) {
  if (item.role !== 'photographer') {
    toastMessage.value = '客户账号暂时没有公开主页。'
    return
  }
  void router.push({ name: 'photographer-detail', params: { userId: item.user_id } })
}

async function togglePersonFollow(item: FollowListItem) {
  if (followLoading.value[item.user_id]) return
  followLoading.value = { ...followLoading.value, [item.user_id]: true }
  try {
    const result = await toggleFollow(item.user_id)
    const wasFollowing = item.is_followed
    if (result.following) {
      const nextItem = { ...item, is_followed: true }
      following.value = following.value.some((entry) => entry.user_id === item.user_id)
        ? following.value.map((entry) => entry.user_id === item.user_id ? nextItem : entry)
        : [nextItem, ...following.value]
    } else {
      following.value = following.value.filter((entry) => entry.user_id !== item.user_id)
    }
    if (wasFollowing !== result.following) {
      totals.value = {
        ...totals.value,
        following: Math.max(0, totals.value.following + (result.following ? 1 : -1)),
      }
    }
    followers.value = followers.value.map((entry) => entry.user_id === item.user_id ? { ...entry, is_followed: result.following } : entry)
    toastMessage.value = result.following ? '已关注该用户' : '已取消关注'
  } catch (toggleError) {
    toastMessage.value = getApiErrorMessage(toggleError)
  } finally {
    followLoading.value = { ...followLoading.value, [item.user_id]: false }
  }
}

function roleLabel(role?: string | null) {
  return role === 'photographer' ? '摄影师' : '客户'
}

function openDiscovery() {
  void router.push({ name: activeTab.value === 'packages' ? 'showcase' : 'discover' })
}

watch(activeTab, (tab) => {
  if (route.query.tab !== tab) void router.replace({ query: { ...route.query, tab } })
})

onIonViewWillEnter(() => {
  activeTab.value = normalizeTab(route.query.tab)
  void loadAll()
})
</script>

<style scoped>
.social-content { --background: var(--paper); }
.social-shell { display: grid; width: min(100%, var(--content-max)); margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); gap: var(--space-5); }
.social-intro { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.social-intro > span { display: grid; width: 46px; height: 46px; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.social-intro h1 { margin: 0 0 5px; font-family: var(--font-serif); font-size: var(--text-lg); line-height: 1.4; }
.social-intro p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
.work-grid { columns: 2; column-gap: var(--space-3); }
.package-list, .people-list { display: grid; gap: var(--space-4); }
.person-card { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: var(--space-2); padding: var(--space-3); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.person-main { display: grid; grid-template-columns: 50px minmax(0, 1fr) 20px; min-width: 0; align-items: center; gap: var(--space-3); padding: 0; border: 0; background: transparent; color: var(--ink); text-align: left; }
.person-copy { display: grid; min-width: 0; gap: 5px; }
.person-copy > span { display: flex; min-width: 0; align-items: center; gap: var(--space-2); }
.person-copy strong { overflow: hidden; font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.person-copy small { flex: 0 0 auto; padding: 2px 6px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-size: var(--text-2xs); font-weight: 700; }
.person-copy em { overflow: hidden; color: var(--ink-tertiary); font-size: var(--text-xs); font-style: normal; text-overflow: ellipsis; white-space: nowrap; }
.person-main > svg { color: var(--ink-tertiary); }
.follow-button { display: inline-flex; min-width: 86px; min-height: var(--touch-target); align-items: center; justify-content: center; gap: 5px; padding: 0 var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); font-size: var(--text-xs); font-weight: 750; }
.follow-button.active { background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); }
.follow-button:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); }
.follow-button ion-spinner { width: 18px; height: 18px; }
@media (max-width: 390px) {
  :deep(.segment-button) { gap: 2px; font-size: 12px; }
  :deep(.segment-button .count) { padding-inline: 3px; }
  .person-card { grid-template-columns: 1fr; }
  .follow-button { width: 100%; }
}
</style>
