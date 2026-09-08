<template>
  <ion-page>
    <DetailHeader title="候选摄影师" :default-href="projectDetailHref" />

    <ion-content class="candidates-content">
      <main class="candidates-shell">
        <FeedSkeleton v-if="loading" :count="3" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="候选摄影师加载失败"
          :description="error"
          action-label="重新加载"
          @action="load"
        />
        <StatePanel
          v-else-if="project && !isOwner"
          title="无法查看候选摄影师"
          description="只有这份企划的发布者可以查看摄影师提交的方案。"
          action-label="返回企划详情"
          @action="goProjectDetail"
        />

        <template v-else-if="project">
          <section class="project-context" aria-labelledby="candidate-project-title">
            <div>
              <span>正在为企划选择摄影师</span>
              <h1 id="candidate-project-title">{{ project.title }}</h1>
            </div>
            <strong>{{ applications.length }} 个方案</strong>
          </section>

          <section class="application-section" aria-labelledby="candidate-list-title">
            <div class="application-heading">
              <div>
                <h2 id="candidate-list-title">候选方案</h2>
                <p>选定后会创建一笔待摄影师确认的订单，其他方案会自动标记为未选中。</p>
              </div>
            </div>

            <div v-if="applications.length" class="application-list">
              <article v-for="application in applications" :key="application.id" class="application-card">
                <header class="candidate-header">
                  <button type="button" class="candidate-identity pressable" @click="openPhotographer(application)">
                    <AvatarImage :src="application.photographer_avatar_url" :name="application.photographer_name" :size="48" />
                    <span>
                      <strong>{{ application.photographer_name || `摄影师 #${application.photographer_id}` }}</strong>
                      <small>{{ application.photographer_city || '查看摄影师主页' }}</small>
                    </span>
                  </button>
                  <span class="application-status" :class="application.status">{{ applicationStatusLabel(application.status) }}</span>
                </header>

                <div class="application-price"><span>摄影师报价</span><strong>{{ formatCurrency(application.price_quote) }}</strong></div>
                <div v-if="application.package_snapshot" class="package-snapshot"><small>关联方案</small><strong>{{ application.package_snapshot }}</strong></div>
                <p class="application-proposal">{{ application.proposal_text }}</p>
                <p v-if="application.revision_note" class="application-note">条款事项：{{ application.revision_note }}</p>
                <p v-if="application.photographer_equipment" class="equipment-note">常用器材：{{ application.photographer_equipment }}</p>
                <div v-if="application.photographer_styles?.length" class="tag-list">
                  <span v-for="tag in application.photographer_styles" :key="tag" class="tag">{{ tag }}</span>
                </div>
                <div v-if="applicationPortfolio(application).length" class="application-portfolio">
                  <img
                    v-for="(item, index) in applicationPortfolio(application)"
                    :key="item.url"
                    :src="resolveMediaUrl(item.thumbnail_url || item.url)"
                    :alt="item.title || `候选作品 ${index + 1}`"
                    loading="lazy"
                  />
                </div>

                <footer class="candidate-actions">
                  <button type="button" class="secondary pressable" @click="messagePhotographer(application)">
                    <MessageCircle :size="17" aria-hidden="true" />私信沟通
                  </button>
                  <button
                    v-if="project.status === 'open' && application.status === 'submitted'"
                    type="button"
                    class="primary pressable"
                    :disabled="selectingApplicationId !== null"
                    @click="selectApplication(application)"
                  >
                    <ion-spinner v-if="selectingApplicationId === application.id" name="crescent" aria-hidden="true" />
                    <Check v-else :size="17" aria-hidden="true" />选定摄影师
                  </button>
                </footer>
              </article>
            </div>

            <div v-else class="application-empty">
              <UsersRound :size="28" aria-hidden="true" />
              <strong>还没有候选摄影师</strong>
              <p>摄影师提交方案后会显示在这里。你也可以分享企划，邀请合适的摄影师查看。</p>
            </div>
          </section>
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2500"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage, IonSpinner, IonToast, alertController } from '@ionic/vue'
import { Check, MessageCircle, UsersRound } from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getProjectDetail } from '@/api/discovery'
import { selectProjectApplication } from '@/api/projects'
import { useAuthStore } from '@/stores/auth'
import type { ProjectApplication, ProjectBrief, ProjectPortfolioReference } from '@/types/discovery'
import { formatCurrency } from '@/utils/format'
import { resolveMediaUrl } from '@/utils/media'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const project = ref<ProjectBrief | null>(null)
const applications = ref<ProjectApplication[]>([])
const loading = ref(true)
const error = ref('')
const toastMessage = ref('')
const selectingApplicationId = ref<number | null>(null)

const projectDetailHref = computed(() => `/projects/${route.params.projectId}`)
const isOwner = computed(() => Boolean(project.value && auth.user?.id === project.value.customer_id))
const coverUrl = computed(() => {
  const firstReference = project.value?.reference_images?.find(Boolean)
  return firstReference ? resolveMediaUrl(firstReference) : ''
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    await auth.initialize()
    const payload = await getProjectDetail(Number(route.params.projectId))
    project.value = payload.project
    applications.value = payload.applications || []
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

function goProjectDetail() {
  void router.replace({ name: 'project-detail', params: { projectId: route.params.projectId } })
}

function applicationStatusLabel(status: string) {
  return ({ submitted: '已提交', selected: '已选中', rejected: '未选中', withdrawn: '已撤回' }[status] || status)
}

function applicationPortfolio(application: ProjectApplication): ProjectPortfolioReference[] {
  return Array.isArray(application.portfolio_refs)
    ? application.portfolio_refs.filter((item) => Boolean(item?.url)).slice(0, 8)
    : []
}

function openPhotographer(application: ProjectApplication) {
  void router.push({ name: 'photographer-detail', params: { userId: application.photographer_id } })
}

function messagePhotographer(application: ProjectApplication) {
  if (!project.value) return
  void router.push({
    name: 'conversation',
    params: { userId: application.photographer_id },
    query: {
      introType: 'project',
      introTitle: project.value.title,
      introUrl: `/projects/${project.value.id}`,
      ...(coverUrl.value ? { introCoverUrl: coverUrl.value } : {}),
      introText: `你好，我正在查看你针对企划「${project.value.title}」提交的方案，想进一步确认拍摄安排和交付细节。`,
    },
  })
}

async function selectApplication(application: ProjectApplication) {
  if (!project.value || selectingApplicationId.value !== null) return
  if (!project.value.shoot_date_start || !project.value.duration_minutes) {
    toastMessage.value = '生成订单前需要确定拍摄开始时间和时长，请先编辑这份企划。'
    return
  }
  const alert = await alertController.create({
    header: '选定摄影师',
    message: `确认选择「${application.photographer_name || `摄影师 #${application.photographer_id}`}」并按 ${formatCurrency(application.price_quote)} 创建订单？其他方案会自动标记为未选中。`,
    buttons: [{ text: '取消', role: 'cancel' }, { text: '确认选择', role: 'confirm' }],
  })
  await alert.present()
  const confirmation = await alert.onDidDismiss()
  if (confirmation.role !== 'confirm') return
  selectingApplicationId.value = application.id
  try {
    const result = await selectProjectApplication(project.value.id, application.id)
    toastMessage.value = '摄影师已选定，订单已创建'
    await router.replace({ name: 'order-detail', params: { orderId: result.order.id } })
  } catch (selectionError) {
    toastMessage.value = getApiErrorMessage(selectionError)
    await load()
  } finally {
    selectingApplicationId.value = null
  }
}

onMounted(() => void load())
</script>

<style scoped>
.candidates-content { --background: var(--paper); }
.candidates-shell { width: min(100%, var(--content-max)); min-height: 100%; margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }

.project-context { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); padding: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.project-context > div { min-width: 0; }
.project-context span { color: var(--brand); font-size: var(--text-xs); font-weight: 700; }
.project-context h1 { margin: 4px 0 0; font-family: var(--font-serif); font-size: var(--text-lg); line-height: 1.45; }
.project-context > strong { flex: 0 0 auto; color: var(--brand); font-size: var(--text-sm); font-variant-numeric: tabular-nums; }

.application-section { padding-top: var(--space-2); }
.application-heading { margin-bottom: var(--space-4); }
.application-heading h2 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.application-heading p { margin: 4px 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.55; }
.application-list { display: grid; gap: var(--space-4); }
.application-card { display: grid; gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.candidate-header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.candidate-identity { display: grid; grid-template-columns: 48px minmax(0, 1fr); min-width: 0; min-height: var(--touch-target); align-items: center; gap: var(--space-3); padding: 0; border: 0; background: transparent; color: var(--ink); text-align: left; }
.candidate-identity > span { display: grid; min-width: 0; gap: 3px; }
.candidate-identity strong { overflow: hidden; font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.candidate-identity small { color: var(--ink-tertiary); font-size: var(--text-xs); }
.application-status { display: inline-flex; min-height: 28px; flex: 0 0 auto; align-items: center; padding: 3px 9px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-size: var(--text-2xs); font-weight: 750; }
.application-status.rejected, .application-status.withdrawn { background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); }
.application-status.selected { background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.application-price { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--divider); }
.application-price span { color: var(--ink-tertiary); font-size: var(--text-xs); }
.application-price strong { color: var(--brand); font-size: var(--text-xl); font-variant-numeric: tabular-nums; }
.package-snapshot { display: grid; gap: 4px; padding: var(--space-3); border-left: 3px solid var(--brand); background: var(--brand-soft); }
.package-snapshot small { color: var(--brand); font-size: var(--text-2xs); font-weight: 700; }
.package-snapshot strong { font-size: var(--text-sm); line-height: 1.5; }
.application-proposal, .application-note, .equipment-note { margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.7; white-space: pre-wrap; }
.application-note, .equipment-note { padding-top: var(--space-2); border-top: 1px solid var(--divider); font-size: var(--text-xs); }
.application-portfolio { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-2); }
.application-portfolio img { width: 100%; aspect-ratio: 1 / 1; border-radius: var(--radius-sm); object-fit: cover; }
.candidate-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); padding-top: var(--space-3); border-top: 1px solid var(--divider); }
.candidate-actions button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); border-radius: var(--radius-md); font-size: var(--text-xs); font-weight: 750; }
.candidate-actions .secondary { border: 0; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); }
.candidate-actions .primary { border: 0; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.candidate-actions button:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); }
.candidate-actions ion-spinner { width: 18px; height: 18px; }
.application-empty { display: grid; min-height: 260px; place-items: center; align-content: center; padding: var(--space-6) var(--space-5); border: 0; border-radius: var(--radius-lg); background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); text-align: center; }
.application-empty strong { margin-top: var(--space-3); color: var(--ink); font-family: var(--font-serif); font-size: var(--text-lg); }
.application-empty p { max-width: 300px; margin: var(--space-2) 0 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; }

@media (min-width: 768px) {
  .candidates-shell { padding-inline: var(--space-6); }
  .application-portfolio { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
</style>
