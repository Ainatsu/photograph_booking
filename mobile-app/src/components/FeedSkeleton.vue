<template>
  <div :class="variant === 'masonry' ? 'masonry' : 'list'" aria-label="正在加载" aria-busy="true">
    <div v-for="index in count" :key="index" class="skeleton-card" :class="`card-${index % 3}`">
      <div class="skeleton media" />
      <div class="content">
        <div class="skeleton line wide" />
        <div class="skeleton line short" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    count?: number
    variant?: 'masonry' | 'list'
  }>(),
  { count: 6, variant: 'list' },
)
</script>

<style scoped>
.masonry {
  columns: 2;
  column-gap: var(--space-3);
}

.list {
  display: grid;
  gap: var(--space-4);
}

.skeleton-card {
  overflow: hidden;
  margin-bottom: var(--space-3);
  break-inside: avoid;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
}

.list .skeleton-card {
  margin: 0;
}

.media {
  aspect-ratio: 4 / 3;
}

.masonry .card-0 .media { aspect-ratio: 4 / 5; }
.masonry .card-1 .media { aspect-ratio: 1 / 1; }
.masonry .card-2 .media { aspect-ratio: 3 / 4; }

.content {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3);
}

.skeleton {
  background: var(--paper-deep);
  animation: skeleton-pulse 1.2s ease-in-out infinite alternate;
}

.line {
  height: 12px;
  border-radius: var(--radius-pill);
}

.wide { width: 78%; }
.short { width: 48%; }

@keyframes skeleton-pulse {
  from { opacity: 0.62; }
  to { opacity: 1; }
}
</style>
