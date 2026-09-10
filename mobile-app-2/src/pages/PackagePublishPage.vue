<template>
  <ion-page>
    <DetailHeader title="创建摄影方案" />
    <ion-content class="page-content">
      <main class="page-shell">
        <!-- 骨架占位：内容见 PAGES.md §9 第 5 步。 -->
        <StatePanel
          title="创建摄影方案"
          description="骨架阶段占位。价格、时长、成片数量与档期规则在后续步骤实现。"
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
