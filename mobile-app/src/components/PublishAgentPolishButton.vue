<template>
  <button
    type="button"
    class="publish-agent-action pressable"
    :disabled="disabled || polishing"
    :aria-busy="polishing"
    @click="polish"
  >
    <ion-spinner v-if="polishing" name="crescent" aria-hidden="true" />
    <WandSparkles v-else :size="18" aria-hidden="true" />
    {{ polishing ? '润色中' : 'Agent 润色' }}
  </button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { IonSpinner } from '@ionic/vue'
import { WandSparkles } from 'lucide-vue-next'
import { getApiErrorMessage } from '@/api/client'
import { polishPublishFields, type PublishPolishContentType } from '@/api/ai'

const props = defineProps<{
  contentType: PublishPolishContentType
  fields: Record<string, unknown>
  disabled?: boolean
}>()

const emit = defineEmits<{
  polished: [fields: Record<string, unknown>, changedCount: number]
  error: [message: string]
  'busy-change': [busy: boolean]
}>()

const polishing = ref(false)

async function polish() {
  if (props.disabled || polishing.value) return
  polishing.value = true
  emit('busy-change', true)
  try {
    const result = await polishPublishFields(props.contentType, props.fields)
    emit('polished', result.fields, result.polished_field_count)
  } catch (error) {
    emit('error', getApiErrorMessage(error))
  } finally {
    polishing.value = false
    emit('busy-change', false)
  }
}
</script>
