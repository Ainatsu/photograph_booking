import type { AgentTask, AgentTaskType } from '@/types/agentTask'

type RouteConfig = { name: string; requires?: string[] }

export const agentTaskRouteMap: Record<AgentTaskType, RouteConfig | null> = {
  create_project: { name: 'publish-project' },
  publish_package: { name: 'publish-package' },
  publish_work: { name: 'publish-work' },
  project_application: { name: 'project-apply', requires: ['project_id'] },
  // Missing fields are validated by the destination page, not by navigation.
  create_booking: { name: 'booking', requires: ['photographer_id', 'package_id'] },
  // Inspiration creation is completed in chat and opened from its quick-entry card.
  create_inspiration: null,
}

export function getAgentTaskRoute(task: AgentTask): { name: string; params?: Record<string, string>; query?: Record<string, string> } | null {
  const config = agentTaskRouteMap[task.task_type]
  if (!config) return null
  const target = task.target || {}
  if ((config.requires || []).some((key) => target[key] === undefined || target[key] === null || target[key] === '')) return null
  const route: { name: string; params?: Record<string, string>; query?: Record<string, string> } = {
    name: config.name,
    query: { agentTaskId: task.task_id, from: 'ai-assistant' },
  }
  if (task.task_type === 'project_application') route.params = { projectId: String(target.project_id) }
  if (task.task_type === 'create_booking') {
    if (target.photographer_id !== undefined && target.photographer_id !== null && target.photographer_id !== '') {
      route.params = { userId: String(target.photographer_id) }
    }
    if (target.package_id !== undefined && target.package_id !== null && target.package_id !== '') {
      route.query!.packageId = String(target.package_id)
    }
  }
  return route
}
