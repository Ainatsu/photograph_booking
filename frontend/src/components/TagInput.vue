<template>
  <el-input-tag
    class="tag-input"
    :model-value="modelValue"
    :placeholder="placeholder"
    :aria-label="placeholder"
    :delimiter="TAG_DELIMITER"
    tag-type="primary"
    save-on-blur
    @update:model-value="updateTags"
  />
</template>

<script setup>
defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  placeholder: {
    type: String,
    default: '输入后按回车添加'
  }
})

const emit = defineEmits(['update:modelValue'])

const TAG_DELIMITER = /[,\uFF0C\u3001\n]+/

const updateTags = (tags = []) => {
  const uniqueTags = [...new Set(
    tags
      .map((tag) => String(tag).trim())
      .filter(Boolean)
  )]
  emit('update:modelValue', uniqueTags)
}
</script>

<style scoped>
.tag-input {
  width: 100%;
}
</style>
