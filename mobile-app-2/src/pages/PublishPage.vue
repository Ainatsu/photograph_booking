<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <main class="page-shell">
        <AppTopBar :show-search="false" @left-action="noop" />
        <!--
          骨架占位。这个页面在参照实现里没有任何入站导航：第三个 Tab 按钮打开的是
          PublishActionSheet 而不是导航到这里，所以它只能靠手输 URL 到达。
          去留待定，见 PAGES.md §2.1。
        -->
        <StatePanel
          title="发布"
          description="此路由在参照实现中无入站入口。保留以维持 URL 可达，去留待决定。"
        />
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { IonContent, IonPage } from '@ionic/vue'
import AppTopBar from '@/components/AppTopBar.vue'
import StatePanel from '@/components/StatePanel.vue'

function noop() {
  // AI 入口在后续步骤接入
}
</script>
