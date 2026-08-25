import type { AgentTask, AgentTaskType } from '@/types/agentTask'

export function taskFields(task: AgentTask, type: AgentTaskType = task.task_type): Record<string, unknown> {
  if (task.task_type !== type) return {}
  return { ...(task.fields || {}) }
}

export function taskFieldPatch(previous: Record<string, unknown>, next: Record<string, unknown>) {
  return Object.keys(next)
    .filter((key) => JSON.stringify(previous[key]) !== JSON.stringify(next[key]))
    .map((field) => ({ field, op: next[field] === null || next[field] === '' ? 'clear' as const : 'set' as const, value: next[field] }))
}
