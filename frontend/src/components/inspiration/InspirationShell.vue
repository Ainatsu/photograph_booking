<template>
  <header class="inspiration-shell">
    <div>
      <router-link to="/profile" class="eyebrow">个人工作区</router-link>
      <h1>灵感仓库</h1>
      <p>收集画面、文字与地点，让下一次拍摄从清晰的念头开始。</p>
    </div>
    <div class="shell-actions">
      <nav aria-label="灵感视图">
        <router-link to="/inspirations" exact-active-class="is-active"><LayoutGrid :size="18" />仓库</router-link>
        <router-link to="/inspirations/map" active-class="is-active"><Map :size="18" />地图</router-link>
      </nav>
      <router-link to="/inspirations/new" class="new-button"><Plus :size="19" />新建灵感</router-link>
    </div>
  </header>
</template>

<script setup>
import { LayoutGrid, Map, Plus } from 'lucide-vue-next'
</script>

<style scoped>
.inspiration-shell { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; padding:40px 0 24px; border-bottom:var(--border-default); }
.eyebrow { font-size:var(--text-sm); color:var(--color-brand); font-weight:700; }
h1 { margin:6px 0 4px; font-size:clamp(28px,4vw,44px); line-height:1.15; }
p { margin:0; color:var(--color-ink-secondary); }
.shell-actions, nav { display:flex; align-items:center; gap:8px; }
nav { padding:4px; border:var(--border-default); background:var(--color-paper-light); border-radius:var(--radius-md); }
nav a, .new-button { min-height:44px; display:inline-flex; align-items:center; justify-content:center; gap:8px; padding:0 16px; border-radius:var(--radius-sm); font-weight:700; text-decoration:none; white-space:nowrap; }
nav a { color:var(--color-ink-secondary); }
nav a.is-active { color:var(--color-brand); background:var(--color-brand-light); }
.new-button { color:#fff !important; background:var(--color-brand); }
@media(max-width:700px){.inspiration-shell{align-items:stretch;flex-direction:column;padding-top:24px}.shell-actions{justify-content:space-between}.shell-actions nav{flex:1}.shell-actions nav a{flex:1}.new-button{padding:0 12px}}
</style>
