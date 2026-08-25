<template>
  <div class="region-selector">
    <el-select
      v-model="countryCode"
      filterable
      clearable
      placeholder="选择国家或地区"
      class="region-control"
      @change="handleCountryChange"
    >
      <el-option
        v-for="country in countryOptions"
        :key="country.value"
        :label="country.label"
        :value="country.value"
      />
    </el-select>
    <el-cascader
      v-if="countryCode === 'CN'"
      v-model="chinaRegion"
      :options="chinaRegionOptions"
      :props="{ expandTrigger: 'hover' }"
      filterable
      clearable
      class="region-control"
      placeholder="选择省份与城市"
      @change="emitValue"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import {
  chinaRegionOptions,
  countryOptions,
  findChinaRegion,
  findCountryCode,
  formatRegionValue,
} from '@/utils/regionOptions'

const props = defineProps({ modelValue: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])

const countryCode = ref('')
const chinaRegion = ref([])
let syncing = false

const syncFromValue = (value) => {
  syncing = true
  countryCode.value = findCountryCode(value)
  chinaRegion.value = countryCode.value === 'CN' ? findChinaRegion(value) : []
  syncing = false
}

const emitValue = () => {
  if (syncing) return
  emit('update:modelValue', formatRegionValue(countryCode.value, chinaRegion.value))
}

const handleCountryChange = () => {
  chinaRegion.value = []
  emitValue()
}

watch(() => props.modelValue, syncFromValue, { immediate: true })
</script>

<style scoped>
.region-selector {
  display: flex;
  width: 100%;
  flex-wrap: wrap;
  gap: 10px;
}

.region-control {
  flex: 1 1 220px;
}
</style>
