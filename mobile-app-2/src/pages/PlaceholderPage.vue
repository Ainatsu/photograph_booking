<template>
  <ion-page>
    <DetailHeader :title="title" :default-href="defaultHref" />
    <ion-content class="page-content">
      <main class="page-shell">
        <!--
          路由已登记但页面尚未实现时的统一占位。
          列出本应用所有已登记路由、逐页替换见 PAGES.md §9 的建造顺序。
        -->
        <StatePanel
          :title="title"
          :description="`「${route.path}」已登记路由，页面内容尚未实现。`"
        />
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { IonContent, IonPage } from '@ionic/vue'
import DetailHeader from '@/components/DetailHeader.vue'
import StatePanel from '@/components/StatePanel.vue'

const props = withDefaults(
  defineProps<{
    title?: string
    defaultHref?: string
  }>(),
  { title: '待实现', defaultHref: '/tabs/discover' },
)

const route = useRoute()
const title = computed(() => props.title)
</script>
