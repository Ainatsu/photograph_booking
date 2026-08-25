<template>
  <teleport to="body">
    <el-tooltip v-if="shouldShow" :content="buttonTooltip" placement="left">
      <button
        type="button"
        class="ai-context-fab"
        :class="{ active: panelOpen, dragging }"
        :style="fabStyle"
        aria-label="打开小龟J"
        @click="handleFabClick"
        @pointerdown="startDrag"
      >
        <el-icon :size="22"><MagicStick /></el-icon>
      </button>
    </el-tooltip>

    <transition name="ai-context-panel">
      <aside
        v-if="hasOpenedPanel"
        v-show="panelOpen"
        class="ai-context-panel"
        :style="panelStyle"
        :aria-hidden="!panelOpen"
        aria-label="小龟J上下文助手"
      >
        <AIAssistant
          embedded
          :page-context="activeContext"
          :quick-prompts="activeQuickPrompts"
          :context-label="contextLabel"
          @close="closePanel"
        />
      </aside>
    </transition>
  </teleport>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { WandSparkles as MagicStick } from 'lucide-vue-next'
import { getPackageDetail, getPhotographerDetail, getWorkDetail } from '../api/photographer'
import { getProjectDetail } from '../api/project'

const AIAssistant = defineAsyncComponent(() => import('../views/AIAssistant.vue'))

const props = defineProps({
  enabled: {
    type: Boolean,
    default: true,
  },
})

const route = useRoute()
const panelOpen = ref(false)
const hasOpenedPanel = ref(false)
const routeContext = ref(null)
const routeQuickPrompts = ref([])
const externalContext = ref(null)
const externalQuickPrompts = ref([])
const externalContextPath = ref('')
let contextRequestId = 0

const POSITION_STORAGE_KEY = 'ai_context_fab_position'
const FAB_SIZE = 48
const VIEWPORT_GUTTER = 10
const DEFAULT_DESKTOP_LEFT = 40
const DEFAULT_DESKTOP_BOTTOM = 96
const DEFAULT_MOBILE_LEFT = 18
const DEFAULT_MOBILE_BOTTOM = 86
const PANEL_WIDTH = 440
const PANEL_HEIGHT = 680
const PANEL_GAP = 12

const fabPosition = ref({ x: DEFAULT_DESKTOP_LEFT, y: 0 })
const positionReady = ref(false)
const dragging = ref(false)
const ignoreNextClick = ref(false)
let dragState = null

const hiddenRouteNames = new Set(['Login', 'Register', 'AIAssistant'])

const shouldShow = computed(() => {
  return props.enabled && !hiddenRouteNames.has(route.name)
})

const activeContext = computed(() => {
  if (externalContext.value && externalContextPath.value === route.fullPath) {
    return {
      ...(routeContext.value || {}),
      ...externalContext.value,
    }
  }
  return routeContext.value
})

const activeQuickPrompts = computed(() => {
  if (externalContext.value && externalContextPath.value === route.fullPath && externalQuickPrompts.value.length) {
    return externalQuickPrompts.value
  }
  return routeQuickPrompts.value
})

const contextLabel = computed(() => {
  return activeContext.value?.title || activeContext.value?.package_name || activeContext.value?.photographer_name || ''
})

const buttonTooltip = computed(() => {
  return contextLabel.value ? `问小龟J：${contextLabel.value}` : '打开小龟J'
})

const fabStyle = computed(() => ({
  left: `${fabPosition.value.x}px`,
  top: `${fabPosition.value.y}px`,
  visibility: positionReady.value ? 'visible' : 'hidden',
}))

const panelStyle = computed(() => {
  if (!positionReady.value) return {}
  const viewport = getViewportSize()
  const width = Math.min(PANEL_WIDTH, Math.max(280, viewport.width - VIEWPORT_GUTTER * 2))
  const availableHeight = viewport.height - VIEWPORT_GUTTER * 2
  const height = Math.min(PANEL_HEIGHT, Math.max(Math.min(360, availableHeight), availableHeight))
  const opensLeft = fabPosition.value.x > viewport.width / 2
  const preferredLeft = opensLeft
    ? fabPosition.value.x + FAB_SIZE - width
    : fabPosition.value.x
  const hasRoomAbove = fabPosition.value.y >= height + PANEL_GAP + VIEWPORT_GUTTER
  const preferredTop = hasRoomAbove
    ? fabPosition.value.y - height - PANEL_GAP
    : fabPosition.value.y + FAB_SIZE + PANEL_GAP

  return {
    width: `${width}px`,
    height: `${height}px`,
    left: `${clamp(preferredLeft, VIEWPORT_GUTTER, viewport.width - width - VIEWPORT_GUTTER)}px`,
    top: `${clamp(preferredTop, VIEWPORT_GUTTER, viewport.height - height - VIEWPORT_GUTTER)}px`,
  }
})

const openPanel = () => {
  hasOpenedPanel.value = true
  panelOpen.value = true
}

const closePanel = () => {
  panelOpen.value = false
}

const togglePanel = () => {
  if (panelOpen.value) {
    closePanel()
  } else {
    openPanel()
  }
}

const handleFabClick = () => {
  if (ignoreNextClick.value) {
    ignoreNextClick.value = false
    return
  }
  togglePanel()
}

const getViewportSize = () => ({
  width: window.innerWidth || document.documentElement.clientWidth || 1024,
  height: window.innerHeight || document.documentElement.clientHeight || 768,
})

const clamp = (value, min, max) => {
  if (max < min) return min
  return Math.min(Math.max(value, min), max)
}

const clampPosition = (position) => {
  const viewport = getViewportSize()
  return {
    x: clamp(position.x, VIEWPORT_GUTTER, viewport.width - FAB_SIZE - VIEWPORT_GUTTER),
    y: clamp(position.y, VIEWPORT_GUTTER, viewport.height - FAB_SIZE - VIEWPORT_GUTTER),
  }
}

const defaultPosition = () => {
  const viewport = getViewportSize()
  const isMobile = viewport.width <= 760
  return clampPosition({
    x: isMobile ? DEFAULT_MOBILE_LEFT : DEFAULT_DESKTOP_LEFT,
    y: viewport.height - FAB_SIZE - (isMobile ? DEFAULT_MOBILE_BOTTOM : DEFAULT_DESKTOP_BOTTOM),
  })
}

const restorePosition = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(POSITION_STORAGE_KEY) || 'null')
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
      fabPosition.value = clampPosition(saved)
    } else {
      fabPosition.value = defaultPosition()
    }
  } catch {
    fabPosition.value = defaultPosition()
  }
  positionReady.value = true
}

const savePosition = () => {
  localStorage.setItem(POSITION_STORAGE_KEY, JSON.stringify(fabPosition.value))
}

const startDrag = (event) => {
  if (event.button !== undefined && event.button !== 0) return
  dragging.value = true
  dragState = {
    startX: event.clientX,
    startY: event.clientY,
    originX: fabPosition.value.x,
    originY: fabPosition.value.y,
    moved: false,
  }
  window.addEventListener('pointermove', handleDragMove)
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
}

const handleDragMove = (event) => {
  if (!dragging.value || !dragState) return
  const deltaX = event.clientX - dragState.startX
  const deltaY = event.clientY - dragState.startY
  if (Math.abs(deltaX) + Math.abs(deltaY) > 4) {
    dragState.moved = true
  }
  fabPosition.value = clampPosition({
    x: dragState.originX + deltaX,
    y: dragState.originY + deltaY,
  })
}

const stopDrag = () => {
  if (!dragging.value || !dragState) return
  const moved = dragState.moved
  dragging.value = false
  dragState = null
  window.removeEventListener('pointermove', handleDragMove)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
  if (moved) {
    ignoreNextClick.value = true
    savePosition()
    window.setTimeout(() => {
      ignoreNextClick.value = false
    }, 0)
  }
}

const handleViewportResize = () => {
  if (!positionReady.value) return
  fabPosition.value = clampPosition(fabPosition.value)
}

const compactText = (value, maxLength = 500) => {
  if (!value) return ''
  return String(value).replace(/\s+/g, ' ').trim().slice(0, maxLength)
}

const compactList = (values, limit = 8) => {
  if (!Array.isArray(values)) return []
  return values
    .map(item => compactText(item, 80))
    .filter(Boolean)
    .slice(0, limit)
}

const getWorkTags = (work) => {
  if (Array.isArray(work?.tags)) return compactList(work.tags)
  return compactList((work?.tag || '').split(/[,\uFF0C\u3001\n]/))
}

const buildBaseContext = (resourceType, resourceId = '') => ({
  route_name: route.name || '',
  route_path: route.fullPath,
  resource_type: resourceType,
  resource_id: resourceId ? String(resourceId) : '',
})

const buildWorkContext = (work) => {
  const tags = getWorkTags(work)
  return {
    ...buildBaseContext('portfolio_item', work?.id),
    title: compactText(work?.title || work?.tag || '当前作品', 120),
    description: compactText(work?.description),
    tags,
    owner_user_id: work?.user_id,
    owner_display_name: compactText(work?.user_display_name, 120),
    photographer_name: compactText(work?.user_display_name, 120),
    current_object: {
      media_type: work?.media_type || 'image',
      image_url: work?.media_type === 'video'
        ? ''
        : ((Array.isArray(work?.images) && work.images[0]) || work?.url || ''),
      thumbnail_url: work?.thumbnail_url || '',
    },
    search_text: compactText([
      work?.title,
      work?.description,
      tags.join(' '),
      work?.user_display_name,
    ].filter(Boolean).join(' '), 1200),
  }
}

const buildPackageContext = (pkg) => {
  const styles = compactList(pkg?.styles)
  return {
    ...buildBaseContext('package', pkg?.id),
    title: compactText(pkg?.package_name || '当前套餐', 120),
    package_name: compactText(pkg?.package_name, 120),
    description: compactText(pkg?.description),
    styles,
    city: compactText(pkg?.city, 80),
    price: pkg?.price,
    price_label: pkg?.price ? `¥${pkg.price}` : '',
    duration: pkg?.duration,
    image_count: pkg?.image_count,
    photographer_id: pkg?.photographer_id,
    photographer_name: compactText(pkg?.photographer_name, 120),
    current_object: {
      thumbnail_url: pkg?.samples?.[0] || '',
    },
    search_text: compactText([
      pkg?.package_name,
      pkg?.description,
      styles.join(' '),
      pkg?.city,
      pkg?.photographer_name,
      pkg?.price ? `价格 ${pkg.price}` : '',
    ].filter(Boolean).join(' '), 1200),
  }
}

const buildPhotographerContext = (profile) => {
  const packages = (profile?.packages || []).slice(0, 6).map(pkg => ({
    id: pkg.id,
    name: compactText(pkg.name || pkg.package_name, 100),
    price: pkg.price,
    duration: pkg.duration,
    styles: compactList(pkg.styles, 4),
  }))
  const portfolio = (profile?.portfolio || []).slice(0, 6).map(work => ({
    id: work.id,
    title: compactText(work.title || work.tag, 100),
    tags: getWorkTags(work).slice(0, 4),
    description: compactText(work.description, 160),
  }))
  return {
    ...buildBaseContext('photographer', profile?.user_id),
    title: compactText(profile?.user_display_name || '当前摄影师', 120),
    photographer_id: profile?.user_id,
    photographer_name: compactText(profile?.user_display_name, 120),
    summary: compactText(profile?.user_bio),
    description: compactText(profile?.user_bio),
    styles: compactList(profile?.styles),
    location: compactText(profile?.location, 80),
    packages,
    portfolio,
    search_text: compactText([
      profile?.user_display_name,
      profile?.user_bio,
      profile?.location,
      compactList(profile?.styles).join(' '),
      packages.map(pkg => `${pkg.name} ${pkg.price || ''}`).join(' '),
      portfolio.map(work => `${work.title} ${(work.tags || []).join(' ')}`).join(' '),
    ].filter(Boolean).join(' '), 1600),
  }
}

const formatBudget = (project) => {
  if (!project) return ''
  if (project.budget_min && project.budget_max) return `¥${project.budget_min} - ¥${project.budget_max}`
  if (project.budget_min) return `¥${project.budget_min} 起`
  if (project.budget_max) return `¥${project.budget_max} 内`
  return ''
}

const buildProjectContext = (project, applications = []) => {
  const styles = compactList(project?.style_tags)
  return {
    ...buildBaseContext('project', project?.id),
    title: compactText(project?.title || '当前企划', 120),
    description: compactText(project?.description),
    styles,
    city: compactText(project?.city, 80),
    location: compactText(project?.location_text, 120),
    status: project?.status || '',
    budget_label: formatBudget(project),
    date_label: compactText(project?.shoot_date_start, 80),
    duration: project?.duration_minutes,
    owner_user_id: project?.customer_id,
    owner_display_name: compactText(project?.customer_name, 120),
    applications: (applications || []).slice(0, 5).map(item => ({
      photographer_id: item.photographer_id,
      photographer_name: compactText(item.photographer_name, 120),
      price_quote: item.price_quote,
      proposal_text: compactText(item.proposal_text, 240),
      styles: compactList(item.photographer_styles, 4),
    })),
    search_text: compactText([
      project?.title,
      project?.description,
      styles.join(' '),
      project?.city,
      project?.location_text,
      formatBudget(project),
    ].filter(Boolean).join(' '), 1400),
  }
}

const routeFallbackContext = () => {
  if (route.name === 'ProjectCreate' || route.name === 'ProjectEdit') {
    return {
      context: {
        ...buildBaseContext('project_draft', route.params.projectId),
        title: route.name === 'ProjectEdit' ? '正在编辑拍摄企划' : '正在发布拍摄企划',
        summary: '用户正在填写企划表单，适合帮助优化需求、预算、时间和交付描述。',
      },
      quickPrompts: ['帮我优化需求', '检查预算和时间是否清晰', '把企划描述写得更吸引摄影师'],
    }
  }
  if (route.name === 'Packages') {
    return {
      context: {
        ...buildBaseContext('package_list'),
        title: '方案列表',
      },
      quickPrompts: ['帮我筛选套餐', '按我的预算找方案', '怎么判断套餐是否合适'],
    }
  }
  if (route.name === 'Gallery') {
    return {
      context: {
        ...buildBaseContext('portfolio_list'),
        title: '作品列表',
      },
      quickPrompts: ['按这种审美找摄影师', '帮我找类似风格作品', '适合我拍什么风格'],
    }
  }
  if (route.name === 'Projects') {
    return {
      context: {
        ...buildBaseContext('project_list'),
        title: '企划大厅',
      },
      quickPrompts: ['帮我写一个企划', '看看什么需求更容易收到应邀', '预算怎么写更合理'],
    }
  }
  return {
    context: {
      ...buildBaseContext('site'),
      title: '当前页面',
    },
    quickPrompts: ['帮我找摄影师', '帮我挑套餐', '我该怎么描述拍摄需求'],
  }
}

const loadRouteContext = async () => {
  const requestId = ++contextRequestId
  externalContext.value = null
  externalQuickPrompts.value = []
  externalContextPath.value = ''

  if (!shouldShow.value) {
    routeContext.value = null
    routeQuickPrompts.value = []
    panelOpen.value = false
    // 不重置 hasOpenedPanel —— 保持 AIAssistant 组件存活
    // 组件生命周期仅由用户登出控制（见下方 watch）
    return
  }

  try {
    if (route.name === 'WorkDetail') {
      const passedWork = history.state?.work
      const res = passedWork?.id && String(passedWork.id) === String(route.params.workId)
        ? { data: passedWork }
        : await getWorkDetail(route.params.workId)
      if (requestId !== contextRequestId) return
      routeContext.value = buildWorkContext(res.data)
      routeQuickPrompts.value = ['找类似风格的摄影师', '按这个风格找套餐', '这组作品适合什么拍摄需求']
      return
    }

    if (route.name === 'PhotographerDetail') {
      const res = await getPhotographerDetail(route.params.userId)
      if (requestId !== contextRequestId) return
      routeContext.value = buildPhotographerContext(res.data)
      routeQuickPrompts.value = ['帮我比较他的套餐', '他的风格适合我吗', '推荐他最适合的拍摄场景']
      return
    }

    if (route.name === 'PackageDetail') {
      const res = await getPackageDetail(route.params.packageId)
      if (requestId !== contextRequestId) return
      routeContext.value = buildPackageContext(res.data)
      routeQuickPrompts.value = ['这个适不适合我', '帮我比较这个套餐', '预约前我还该确认什么']
      return
    }

    if (route.name === 'ProjectDetail') {
      const res = await getProjectDetail(route.params.projectId)
      if (requestId !== contextRequestId) return
      routeContext.value = buildProjectContext(res.data.project, res.data.applications || [])
      routeQuickPrompts.value = ['帮我优化需求', '这个预算合理吗', '适合找什么风格摄影师']
      return
    }
  } catch {
    // 保留通用入口，不让页面上下文拉取失败影响助手可用性。
  }

  if (requestId !== contextRequestId) return
  if (window.__aiPageContext?.routePath === route.fullPath) {
    handleExternalContext({ detail: window.__aiPageContext })
  }
  const fallback = routeFallbackContext()
  routeContext.value = fallback.context
  routeQuickPrompts.value = fallback.quickPrompts
}

const handleExternalContext = (event) => {
  const detail = event.detail || {}
  externalContext.value = detail.context || null
  externalQuickPrompts.value = Array.isArray(detail.quickPrompts) ? detail.quickPrompts : []
  externalContextPath.value = detail.routePath || route.fullPath
}

// 用户登出时销毁面板组件，避免不同用户间数据残留
watch(() => props.enabled, (enabled) => {
  if (!enabled) {
    hasOpenedPanel.value = false
    panelOpen.value = false
    routeContext.value = null
    routeQuickPrompts.value = []
  }
})

onMounted(() => {
  restorePosition()
  window.addEventListener('resize', handleViewportResize)
  window.addEventListener('ai-context:update', handleExternalContext)
  loadRouteContext()
})

onUnmounted(() => {
  stopDrag()
  window.removeEventListener('resize', handleViewportResize)
  window.removeEventListener('ai-context:update', handleExternalContext)
})

watch(() => [route.fullPath, props.enabled], loadRouteContext)
</script>

<style scoped>
.ai-context-fab {
  position: fixed;
  z-index: 1800;
  width: 48px;
  height: 48px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  color: var(--color-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  touch-action: none;
  user-select: none;
  transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;
}

.ai-context-fab:hover,
.ai-context-fab.active {
  background: var(--color-brand-light);
  color: var(--color-brand-hover);
  border-color: var(--color-brand);
}

.ai-context-fab.dragging {
  cursor: grabbing;
}

.ai-context-panel {
  position: fixed;
  z-index: 2500;
  width: min(440px, calc(100vw - 32px));
  height: min(680px, calc(100dvh - 190px));
  min-height: min(440px, calc(100dvh - 20px));
  overflow: hidden;
  border: var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--color-paper-light);
  box-shadow: var(--shadow-flyout);
}

.ai-context-panel-enter-active,
.ai-context-panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.ai-context-panel-enter-from,
.ai-context-panel-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 760px) {
  .ai-context-panel {
    min-height: min(360px, calc(100dvh - 20px));
  }
}
</style>
