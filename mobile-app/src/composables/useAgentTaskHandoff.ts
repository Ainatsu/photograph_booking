import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getApiErrorMessage } from '@/api/client'
import { completeAgentTask, getAgentTask, openAgentTask, patchAgentTask } from '@/api/agentTasks'
import type { AgentTask, AgentTaskType } from '@/types/agentTask'
import { getAgentTaskRoute } from '@/utils/agentTaskRoutes'

export function useAgentTaskHandoff(conversationId?: string | number) {
  const route = useRoute()
  const router = useRouter()
  const task = ref<AgentTask | null>(null)
  const loading = ref(false)
  const error = ref('')
  let saveQueue: Promise<AgentTask | null> = Promise.resolve(null)

  async function load(expectedType?: AgentTaskType) {
    const taskId = String(route.query.agentTaskId || '')
    const resolvedConversationId = conversationId || localStorage.getItem('ai_active_conversation_id')
    if (!resolvedConversationId || !taskId) return null
    loading.value = true
    error.value = ''
    try {
      const loaded = await getAgentTask(resolvedConversationId, taskId)
      if (expectedType && loaded.task_type !== expectedType) throw new Error('任务类型与当前页面不匹配')
      task.value = loaded
      return loaded
    } catch (cause) {
      error.value = getApiErrorMessage(cause)
      return null
    } finally {
      loading.value = false
    }
  }

  async function openAndNavigate(nextTask: AgentTask) {
    const target = getAgentTaskRoute(nextTask)
    const resolvedConversationId = conversationId || localStorage.getItem('ai_active_conversation_id')
    if (!target || !resolvedConversationId) {
      error.value = '任务缺少可信目标，暂时无法打开专门页面'
      return false
    }
    try {
      task.value = await openAgentTask(resolvedConversationId, nextTask.task_id)
      await router.push(target)
      return true
    } catch (cause) {
      error.value = getApiErrorMessage(cause)
      return false
    }
  }

  async function saveOperations(operations: Array<{ field: string; op: 'set' | 'clear'; value?: unknown }>) {
    const run = async () => {
      const resolvedConversationId = conversationId || localStorage.getItem('ai_active_conversation_id')
      if (!resolvedConversationId || !task.value || !operations.length) return task.value
      task.value = await patchAgentTask(resolvedConversationId, task.value.task_id, task.value.revision, operations)
      return task.value
    }
    saveQueue = saveQueue.then(run, run)
    return saveQueue
  }

  async function complete(result?: Record<string, unknown>) {
    const resolvedConversationId = conversationId || localStorage.getItem('ai_active_conversation_id')
    if (!resolvedConversationId || !task.value) return null
    const completed = await completeAgentTask(resolvedConversationId, task.value.task_id, result)
    task.value = null
    return completed
  }

  return { task, loading, error, load, openAndNavigate, saveOperations, complete }
}
