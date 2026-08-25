import type { ProjectApplication, ProjectBrief } from '@/types/discovery'

export const projectStatusOptions = [
  { value: 'all', label: '全部' },
  { value: 'draft', label: '草稿' },
  { value: 'open', label: '招募中' },
  { value: 'expired', label: '已过期' },
  { value: 'converted', label: '已转订单' },
  { value: 'closed', label: '已关闭' },
] as const

export const applicationStatusOptions = [
  { value: 'all', label: '全部' },
  { value: 'submitted', label: '待结果' },
  { value: 'selected', label: '已选中' },
  { value: 'rejected', label: '未选中' },
  { value: 'withdrawn', label: '已撤回' },
] as const

export function projectStatusLabel(status: string): string {
  return {
    draft: '草稿',
    open: '招募中',
    expired: '已过期',
    converted: '已转订单',
    closed: '已关闭',
    cancelled: '已取消',
  }[status] || '状态待确认'
}

export function applicationStatusLabel(status: string): string {
  return {
    submitted: '待客户选择',
    selected: '已被选中',
    rejected: '未被选中',
    withdrawn: '已撤回',
  }[status] || '状态待确认'
}

export function canEditProject(project: ProjectBrief): boolean {
  return ['draft', 'open', 'expired'].includes(project.status)
}

export function canPublishProject(project: ProjectBrief): boolean {
  return ['draft', 'expired'].includes(project.status)
}

export function canCloseProject(project: ProjectBrief): boolean {
  return ['draft', 'open'].includes(project.status)
}

export function canEditProjectApplication(application: ProjectApplication): boolean {
  return application.status === 'submitted' && application.project?.status === 'open'
}
