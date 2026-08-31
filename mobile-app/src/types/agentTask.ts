export type AgentTaskType =
  | 'create_project'
  | 'publish_package'
  | 'publish_work'
  | 'project_application'
  | 'create_booking'
  | 'create_inspiration'
  | 'generate_image'

export type AgentTaskStatus = 'collecting' | 'awaiting_reference_image' | 'queued' | 'editing_page' | 'submitting' | 'generating' | 'saving' | 'partial' | 'failed' | 'completed' | 'cancelled' | 'expired'

export interface AgentTaskSummaryLine {
  label: string
  value: string
}

export interface AgentTask {
  task_id: string
  conversation_id: number | string
  task_type: AgentTaskType
  status: AgentTaskStatus
  schema_version: number
  revision: number
  target: Record<string, unknown>
  fields: Record<string, unknown>
  media_assets?: unknown[]
  summary: {
    title: string
    lines: AgentTaskSummaryLine[]
    collected_count: number
    missing_required_count: number
    missing_required_fields: string[]
    missing_required_labels: string[]
    media_count: number
    can_commit: boolean
    requires_editor: boolean
    next_question?: string | null
    commit_label?: string | null
    edit_label: string
  }
  result?: Record<string, unknown> | null
  updated_at?: string | null
}
