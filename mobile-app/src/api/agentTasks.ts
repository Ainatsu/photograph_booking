import api from './client'
import type { AgentTask } from '@/types/agentTask'

export interface AgentTaskCommitResponse {
  task: AgentTask
  assistant_message: {
    id: string
    conversation_id: number | string
    role: 'assistant'
    content: string
    metadata?: Record<string, unknown>
    created_at: string
  }
  receipt: {
    status: 'success' | 'failed'
    content: string
    result: Record<string, unknown>
  }
}

export async function getActiveAgentTask(conversationId: string | number): Promise<AgentTask | null> {
  const { data } = await api.get<AgentTask | null>(`/ai/conversations/${conversationId}/active-task`)
  return data
}

export async function getAgentTask(conversationId: string | number, taskId: string): Promise<AgentTask> {
  const { data } = await api.get<AgentTask>(`/ai/conversations/${conversationId}/tasks/${taskId}`)
  return data
}

export async function openAgentTask(conversationId: string | number, taskId: string): Promise<AgentTask> {
  const { data } = await api.post<AgentTask>(`/ai/conversations/${conversationId}/tasks/${taskId}/open`)
  return data
}

export async function cancelAgentTask(conversationId: string | number, taskId: string): Promise<AgentTask> {
  const { data } = await api.post<AgentTask>(`/ai/conversations/${conversationId}/tasks/${taskId}/cancel`)
  return data
}

export async function commitAgentTask(
  conversationId: string | number,
  taskId: string,
  revision: number,
): Promise<AgentTaskCommitResponse> {
  const { data } = await api.post<AgentTaskCommitResponse>(`/ai/conversations/${conversationId}/tasks/${taskId}/commit`, {
    revision,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

export async function patchAgentTask(
  conversationId: string | number,
  taskId: string,
  revision: number,
  operations: Array<{ field: string; op: 'set' | 'clear'; value?: unknown; confidence?: number; evidence?: string }>,
): Promise<AgentTask> {
  const { data } = await api.patch<AgentTask>(`/ai/conversations/${conversationId}/tasks/${taskId}`, { revision, operations })
  return data
}

export async function completeAgentTask(conversationId: string | number, taskId: string, result?: Record<string, unknown>): Promise<AgentTask> {
  const { data } = await api.post<AgentTask>(`/ai/conversations/${conversationId}/tasks/${taskId}/complete`, { result })
  return data
}
