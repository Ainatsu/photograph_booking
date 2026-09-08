import type { AgentTask, AgentTaskType } from '@/types/agentTask'

const DOCK_HIDDEN_TASK_TYPES: AgentTaskType[] = ['generate_image', 'create_inspiration']

export function shouldDisplayAgentTaskDock(task: AgentTask | null | undefined): task is AgentTask {
  return Boolean(task && !DOCK_HIDDEN_TASK_TYPES.includes(task.task_type))
}

export function taskFields(task: AgentTask, type: AgentTaskType = task.task_type): Record<string, unknown> {
  if (task.task_type !== type) return {}
  return { ...(task.fields || {}) }
}

export function taskFieldPatch(previous: Record<string, unknown>, next: Record<string, unknown>) {
  return Object.keys(next)
    .filter((key) => JSON.stringify(previous[key]) !== JSON.stringify(next[key]))
    .map((field) => ({ field, op: next[field] === null || next[field] === '' ? 'clear' as const : 'set' as const, value: next[field] }))
}
