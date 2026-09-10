<template>
  <ion-page>
    <DetailHeader title="发布作品" />
    <ion-content class="page-content">
      <main class="page-shell">
        <!-- 骨架占位：内容见 PAGES.md §9 第 5 步。 -->
        <StatePanel
          title="发布作品"
          description="骨架阶段占位。媒体上传、标题与风格标签在后续步骤实现。"
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
