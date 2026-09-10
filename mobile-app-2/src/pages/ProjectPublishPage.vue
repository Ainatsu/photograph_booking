<template>
  <ion-page>
    <DetailHeader title="发布拍摄需求" />
    <ion-content class="page-content">
      <main class="page-shell">
        <!-- 骨架占位：内容见 PAGES.md §9 第 6 步。 -->
        <StatePanel
          title="发布拍摄需求"
          description="骨架阶段占位。预算、地点、日期与参考图在后续步骤实现。"
        />
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { IonContent, IonPage } from '@ionic/vue'
import DetailHeader from '@/components/DetailHeader.vue'
import StatePanel from '@/components/StatePanel.vue'
</script>
