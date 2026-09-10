<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <main class="page-shell">
        <AppTopBar :show-search="false" @left-action="noop" />
        <!-- 骨架占位：内容见 PAGES.md §9 第 8 步。 -->
        <StatePanel
          title="消息"
          description="骨架阶段占位。联系人列表、未读角标与实时消息在后续步骤实现。"
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
