<template>
  <section class="shoot-context-card" :class="`status-${context.status}`" aria-label="拍摄环境信息">
    <header class="card-header">
      <div class="title-group">
        <MapPinned :size="18" aria-hidden="true" />
        <div>
          <p class="eyebrow">拍摄环境</p>
          <h3>{{ context.place?.name || '地点待确认' }}</h3>
        </div>
      </div>
      <span class="status-label">{{ statusLabel }}</span>
    </header>

    <div v-if="context.place && hasCoordinates" class="map-frame">
      <LocationMap
        :latitude="context.place.latitude"
        :longitude="context.place.longitude"
        :zoom="13"
        aria-label="拍摄地点地图"
      />
    </div>

    <div v-if="context.place?.address" class="address-row">
      <MapPin :size="14" aria-hidden="true" />
      <span>{{ context.place.address }}</span>
    </div>

    <!-- 地点有歧义时只展示候选，不渲染可能属于错误地点的天气。 -->
    <div v-if="isAmbiguous" class="state-block" role="status">
      <AlertCircle :size="18" aria-hidden="true" />
      <div>
        <strong>请确认拍摄地点</strong>
        <p>找到多个相近地点，请回到对话中选择后再查询天气。</p>
        <div v-if="context.place_candidates?.length" class="candidate-list" aria-label="地点候选">
          <button
            v-for="candidate in context.place_candidates"
            :key="`${candidate.name}-${candidate.latitude}-${candidate.longitude}`"
            type="button"
            class="candidate-button"
            :disabled="disabled"
            :aria-label="`选择地点：${candidate.address || candidate.name}`"
            @click="emit('select-candidate', candidate)"
          >
            <MapPin :size="16" aria-hidden="true" />
            <span>
              <strong>{{ candidate.name }}</strong>
              <small v-if="candidate.address">{{ candidate.address }}</small>
            </span>
          </button>
        </div>
      </div>
    </div>

    <div v-else-if="context.status === 'failed'" class="state-block" role="alert">
      <AlertCircle :size="18" aria-hidden="true" />
      <div>
        <strong>暂时无法获取拍摄环境</strong>
        <p>地点或天气服务暂时不可用，请稍后重试。</p>
      </div>
    </div>

    <!-- partial 状态仍可展示可信的地点或日照降级结果。 -->
    <template v-else>
      <div v-if="context.status === 'partial'" class="partial-note" role="status">
        <AlertCircle :size="15" aria-hidden="true" />
        <span>{{ context.error_code === 'forecast_unavailable' ? '该日期超出当前预报范围。' : '天气暂时不可用，已保留地点信息。' }}</span>
      </div>

      <div v-if="hourly.length" class="weather-section">
        <div class="section-heading">
          <CloudSun :size="16" aria-hidden="true" />
          <span>{{ weatherTitle }}</span>
        </div>
        <div class="weather-strip" role="list" aria-label="逐小时天气">
          <div v-for="hour in hourly" :key="hour.time" class="weather-hour" role="listitem">
            <span class="hour-time">{{ hour.time }}</span>
            <strong>{{ formatTemperature(hour.temperature_c) }}</strong>
            <span class="hour-meta">雨 {{ formatNumber(hour.precipitation_probability) }}%</span>
            <span class="hour-meta">风 {{ formatNumber(hour.wind_kph) }} km/h</span>
          </div>
        </div>
      </div>

      <div v-if="sunlightEntries.length" class="sunlight-grid">
        <div v-for="item in sunlightEntries" :key="item.label" class="sunlight-item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>

      <div v-if="context.recommendations?.length" class="recommendation-list">
        <div
          v-for="recommendation in context.recommendations"
          :key="recommendation.code || recommendation.title"
          class="recommendation-row"
          :class="`severity-${recommendation.severity || 'info'}`"
        >
          <TriangleAlert v-if="recommendation.severity === 'warning'" :size="16" aria-hidden="true" />
          <Lightbulb v-else :size="16" aria-hidden="true" />
          <div>
            <strong>{{ recommendation.title }}</strong>
            <p>{{ recommendation.detail }}</p>
          </div>
        </div>
      </div>
    </template>

    <footer v-if="context.weather?.provider || context.weather?.updated_at" class="data-source">
      数据源 {{ context.weather?.provider || '平台' }}<span v-if="context.weather?.updated_at"> · 更新于 {{ formatUpdatedAt(context.weather.updated_at) }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AlertCircle, CloudSun, Lightbulb, MapPin, MapPinned, TriangleAlert } from 'lucide-vue-next'
import LocationMap from '@/components/location/LocationMap.vue'
import type { AIShootContext, AIShootContextPlace } from '@/api/ai'

const props = withDefaults(defineProps<{ context: AIShootContext; disabled?: boolean }>(), {
  disabled: false,
})
const emit = defineEmits<{ (event: 'select-candidate', candidate: AIShootContextPlace): void }>()

const context = computed(() => props.context)
const hourly = computed(() => context.value.weather?.hourly || [])
// 同时排除缺失值与 NaN，防止地图组件收到无效坐标。
const hasCoordinates = computed(() => Number.isFinite(context.value.place?.latitude) && Number.isFinite(context.value.place?.longitude))
const isAmbiguous = computed(() => context.value.status === 'ambiguous')
const statusLabel = computed(() => ({ success: '可用', partial: '部分可用', ambiguous: '待确认', failed: '不可用' }[context.value.status] || '拍摄信息'))
const weatherTitle = computed(() => context.value.weather?.forecast_date ? `${context.value.weather.forecast_date} · 逐小时` : '逐小时天气')
const sunlightEntries = computed(() => {
  const sunlight = context.value.sunlight || {}
  // 只输出后端实际提供的时段，partial 响应不会留下空占位项。
  return [
    ['日出', sunlight.sunrise],
    ['黄金时刻', sunlight.golden_hour_start && sunlight.golden_hour_end ? `${sunlight.golden_hour_start}-${sunlight.golden_hour_end}` : null],
    ['日落', sunlight.sunset],
    ['蓝调时刻结束', sunlight.blue_hour_end],
  ].filter((item): item is [string, string] => Boolean(item[1])).map(([label, value]) => ({ label, value }))
})

function formatNumber(value?: number | null): string {
  return value === null || value === undefined ? '--' : String(Math.round(value))
}

function formatTemperature(value?: number | null): string {
  return value === null || value === undefined ? '--' : `${Math.round(value)}°`
}

function formatUpdatedAt(value: string): string {
  return value.replace('T', ' ').replace(/Z$/, '')
}
</script>

<style scoped>
.shoot-context-card { width: 100%; overflow: hidden; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--ink); }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 12px 14px; border-bottom: 1px solid var(--neu-light); box-shadow: 0 1px 0 var(--neu-shade-soft); }
.title-group { display: flex; min-width: 0; align-items: center; gap: 9px; color: var(--brand); }
.title-group > div { min-width: 0; }
.eyebrow { margin: 0 0 2px; color: var(--ink-tertiary); font-size: 10px; }
h3 { margin: 0; overflow: hidden; font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.status-label { flex-shrink: 0; padding: 3px 7px; border-radius: var(--radius-sm); background: var(--brand-soft); color: var(--brand); font-size: 11px; font-weight: 600; }
.status-partial .status-label, .status-ambiguous .status-label { background: rgba(139, 105, 20, .12); color: var(--warning); }
.status-failed .status-label { background: rgba(197, 48, 48, .1); color: var(--danger); }
.map-frame { height: 170px; border-bottom: 1px solid var(--neu-light); box-shadow: 0 1px 0 var(--neu-shade-soft); }
.address-row { display: flex; align-items: flex-start; gap: 6px; padding: 10px 14px 0; color: var(--ink-secondary); font-size: 12px; line-height: 1.45; }
.state-block { display: flex; align-items: flex-start; gap: 10px; padding: 18px 14px; color: var(--warning); }
.state-block > div { min-width: 0; }
.state-block strong { color: var(--ink); font-size: var(--text-sm); }
.state-block p { margin: 4px 0 0; color: var(--ink-secondary); font-size: 12px; line-height: 1.5; }
.candidate-list { display: grid; gap: 8px; margin-top: 12px; }
.candidate-button { display: flex; width: 100%; min-height: 44px; align-items: center; gap: 9px; padding: 8px 10px; border: 0; border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-raise); color: var(--brand); text-align: left; touch-action: manipulation; transition: opacity 160ms ease, box-shadow 160ms ease; }
.candidate-button > span { display: grid; min-width: 0; gap: 2px; }
.candidate-button strong { color: var(--ink); font-size: 12px; }
.candidate-button small { color: var(--ink-secondary); font-size: 11px; line-height: 1.4; }
.candidate-button:active:not(:disabled) { box-shadow: var(--neu-inset); }
.candidate-button:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.candidate-button:disabled { cursor: default; opacity: .45; }
.partial-note { display: flex; align-items: center; gap: 6px; padding: 10px 14px 0; color: var(--warning); font-size: 12px; }
.weather-section, .recommendation-list { padding: 14px; }
.section-heading { display: flex; align-items: center; gap: 6px; margin-bottom: 9px; color: var(--ink-secondary); font-size: 12px; font-weight: 600; }
.weather-strip { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 2px; }
.weather-hour { display: grid; min-width: 80px; gap: 3px; padding: 8px; border: 0; border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); }
.hour-time, .hour-meta, .sunlight-item span { color: var(--ink-tertiary); font-size: 10px; }
.weather-hour strong { font-size: var(--text-base); }
.hour-meta { white-space: nowrap; }
.sunlight-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1px; margin: 0 14px; border: 0; background: var(--border-light); box-shadow: var(--neu-raise); }
.sunlight-item { display: grid; gap: 3px; padding: 8px 10px; background: var(--paper); }
.sunlight-item strong { font-size: 12px; }
.recommendation-list { display: grid; gap: 8px; }
.recommendation-row { display: flex; align-items: flex-start; gap: 8px; padding: 9px; border-left: 2px solid var(--brand); background: var(--brand-soft); }
.recommendation-row.severity-warning { border-left-color: var(--warning); background: rgba(139, 105, 20, .08); }
.recommendation-row strong { font-size: 12px; }
.recommendation-row p { margin: 2px 0 0; color: var(--ink-secondary); font-size: 11px; line-height: 1.45; }
.data-source { padding: 0 14px 12px; color: var(--ink-tertiary); font-size: 10px; }
@media (prefers-reduced-motion: reduce) { .weather-strip { scroll-behavior: auto; } .candidate-button { transition: none; } }
</style>
