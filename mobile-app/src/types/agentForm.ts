import type { AIMessage } from '@/api/ai'

export type AgentTaskType =
  | 'create_project'
  | 'publish_package'
  | 'publish_work'
  | 'project_application'
  | 'create_booking'

export type AgentTaskStatus =
  | 'editing'
  | 'submitting'
  | 'invalid'
  | 'draft_unavailable'
  | 'published'
  | 'cancelled'
  | 'failed'

export type AgentTaskAction = 'publish' | 'save_draft' | 'cancel'

export interface AgentFormCard {
  task_id: string
  task_type: AgentTaskType
  status: AgentTaskStatus
  schema_version: number
  target: Record<string, unknown>
  initial_fields: Record<string, unknown>
  field_errors: Record<string, string>
  media: { existing: string[]; limits: Record<string, number> }
  actions: AgentTaskAction[]
  revision: number
  result?: Record<string, unknown>
}

export type AgentFormFieldType = 'text' | 'textarea' | 'number' | 'date' | 'datetime-local' | 'select' | 'tags'

export interface AgentFormFieldDefinition {
  key: string
  label: string
  type: AgentFormFieldType
  required?: boolean
  min?: number
  max?: number
  options?: Array<{ label: string; value: string }>
  help?: string
}

export const agentFormDefinitions: Record<AgentTaskType, AgentFormFieldDefinition[]> = {
  create_project: [
    { key: 'title', label: '企划标题', type: 'text', required: true },
    { key: 'description', label: '需求描述', type: 'textarea', required: true },
    { key: 'category', label: '拍摄类别', type: 'select', options: [{ label: '其他', value: 'other' }, { label: '人像', value: 'portrait' }, { label: '婚礼', value: 'wedding' }, { label: '商业', value: 'commercial' }] },
    { key: 'style_tags', label: '风格标签', type: 'tags', help: '用逗号分隔多个标签' },
    { key: 'city', label: '拍摄城市', type: 'text', required: true },
    { key: 'location_text', label: '拍摄地点', type: 'text' },
    { key: 'shoot_date_start', label: '开始时间', type: 'datetime-local' },
    { key: 'shoot_date_end', label: '结束时间', type: 'datetime-local' },
    { key: 'duration_minutes', label: '预计时长（分钟）', type: 'number', min: 1 },
    { key: 'budget_min', label: '预算下限', type: 'number', min: 0 },
    { key: 'budget_max', label: '预算上限', type: 'number', min: 0 },
    { key: 'deliverables', label: '交付要求', type: 'textarea' },
  ],
  publish_package: [
    { key: 'name', label: '方案名称', type: 'text', required: true },
    { key: 'description', label: '方案简介', type: 'textarea' },
    { key: 'price', label: '价格', type: 'number', required: true, min: 0 },
    { key: 'duration', label: '拍摄时长（分钟）', type: 'number', required: true, min: 1 },
    { key: 'styles', label: '风格标签', type: 'tags', help: '用逗号分隔多个标签' },
    { key: 'city', label: '服务城市', type: 'text' },
    { key: 'service_location', label: '服务范围', type: 'text' },
    { key: 'includes', label: '服务内容', type: 'tags', help: '用逗号分隔多个项目' },
    { key: 'image_count', label: '精修张数', type: 'number', min: 0 },
    { key: 'delivery_days', label: '交付天数', type: 'number', min: 1 },
  ],
  publish_work: [
    { key: 'title', label: '作品标题', type: 'text' },
    { key: 'description', label: '作品说明', type: 'textarea' },
    { key: 'tags', label: '风格标签', type: 'tags', help: '用逗号分隔多个标签' },
  ],
  project_application: [
    { key: 'proposal_text', label: '应邀说明', type: 'textarea', required: true },
    { key: 'price_quote', label: '报价', type: 'number', required: true, min: 1 },
    { key: 'package_snapshot', label: '关联方案摘要', type: 'text' },
    { key: 'revision_note', label: '补充说明', type: 'textarea' },
  ],
  create_booking: [
    { key: 'appointment_date', label: '预约日期', type: 'date', required: true },
    { key: 'notes', label: '备注', type: 'textarea', max: 500, help: '最多 500 字' },
  ],
}

export function taskTypeLabel(type: AgentTaskType): string {
  return {
    create_project: '发布企划',
    publish_package: '发布方案',
    publish_work: '发布作品',
    project_application: '申请企划',
    create_booking: '预约拍摄',
  }[type]
}

export function primaryActionLabel(type: AgentTaskType): string {
  return type === 'create_booking' ? '确认预约' : type === 'project_application' ? '确认申请' : '确认发布'
}

export function toAgentFormData(type: AgentTaskType, fields: Record<string, unknown>): Record<string, unknown> {
  const next = { ...fields }
  for (const key of ['style_tags', 'styles', 'tags', 'includes']) {
    if (typeof next[key] === 'string') {
      next[key] = next[key]
        .split(/[，,、\n]+/)
        .map((item) => item.trim())
        .filter(Boolean)
    }
  }
  for (const key of ['duration_minutes', 'duration', 'price', 'image_count', 'delivery_days', 'budget_min', 'budget_max', 'price_quote']) {
    if (next[key] === '') delete next[key]
    else if (typeof next[key] === 'string' && next[key].trim()) next[key] = Number(next[key])
  }
  return next
}

export function cardFromMessage(message: AIMessage): AgentFormCard | null {
  const card = message.metadata?.agent_form_card
  if (!card || typeof card !== 'object') return null
  return card as AgentFormCard
}
