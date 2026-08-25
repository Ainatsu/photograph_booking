<template>
  <div class="follow-counts">
    <span
      :class="['count-item', { clickable: clickable }]"
      @click="clickable && $emit('show-following')"
    >
      关注：<strong>{{ followingCount }}</strong>
    </span>
    <span class="count-divider">|</span>
    <span
      :class="['count-item', { clickable: clickable }]"
      @click="clickable && $emit('show-followers')"
    >
      粉丝：<strong>{{ followerCount }}</strong>
    </span>
  </div>
</template>

<script setup>
defineProps({
  followingCount: { type: Number, default: 0 },
  followerCount: { type: Number, default: 0 },
  clickable: { type: Boolean, default: false },
})

defineEmits(['show-following', 'show-followers'])
</script>

<style scoped>
.follow-counts {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #606266;
  margin-top: 12px;
}
.count-item strong {
  color: #303133;
}
.count-item.clickable {
  cursor: pointer;
  transition: color 0.2s;
}
.count-item.clickable:hover {
  color: #409eff;
}
.count-divider {
  color: #dcdfe6;
}
</style>