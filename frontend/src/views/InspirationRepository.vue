<template>
  <main class="page">
    <InspirationShell />
    <section class="toolbar" aria-label="筛选灵感">
      <el-input v-model="query" clearable placeholder="搜索标题、摘要或地点" :prefix-icon="Search" @input="scheduleLoad" />
      <el-select v-model="status" aria-label="状态筛选" @change="load"><el-option label="全部状态" value=""/><el-option label="草稿" value="draft"/><el-option label="已保存" value="saved"/></el-select>
    </section>
    <div v-if="loading" class="grid" aria-label="加载中"><el-skeleton v-for="n in 6" :key="n" animated><template #template><el-skeleton-item variant="image" class="skeleton-cover"/><el-skeleton-item variant="h3"/><el-skeleton-item variant="text"/></template></el-skeleton></div>
    <el-result v-else-if="error" icon="error" title="灵感加载失败" sub-title="请检查网络后重试"><template #extra><el-button @click="load">重新加载</el-button></template></el-result>
    <section v-else-if="items.length" class="grid" aria-live="polite"><InspirationCard v-for="item in items" :key="item.id" :item="item" /></section>
    <el-empty v-else :description="query || status ? '没有符合条件的灵感' : '仓库还是空的，先收藏第一个画面吧'"><router-link to="/inspirations/new"><el-button type="primary">创建第一条灵感</el-button></router-link></el-empty>
  </main>
</template>
<script setup>
import { onMounted, ref } from 'vue'; import { Search } from 'lucide-vue-next'; import { getInspirations } from '../api/inspiration'; import InspirationShell from '../components/inspiration/InspirationShell.vue'; import InspirationCard from '../components/inspiration/InspirationCard.vue'
const items=ref([]),loading=ref(true),error=ref(false),query=ref(''),status=ref('');let timer
const load=async()=>{loading.value=true;error.value=false;try{items.value=(await getInspirations({query:query.value||undefined,status:status.value||undefined,limit:60})).data}catch{error.value=true}finally{loading.value=false}}
const scheduleLoad=()=>{clearTimeout(timer);timer=setTimeout(load,300)};onMounted(load)
</script>
<style scoped>.page{padding:0 var(--content-gutter) 64px}.toolbar{display:grid;grid-template-columns:minmax(240px,520px) 150px;gap:12px;margin:24px 0}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.skeleton-cover{width:100%;height:220px;margin-bottom:14px}@media(max-width:950px){.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.toolbar,.grid{grid-template-columns:1fr}.toolbar{margin:18px 0}}</style>
