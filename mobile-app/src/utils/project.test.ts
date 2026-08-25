import { describe, expect, it } from 'vitest'
import type { ProjectApplication, ProjectBrief } from '@/types/discovery'
import {
  applicationStatusLabel,
  canCloseProject,
  canEditProject,
  canEditProjectApplication,
  canPublishProject,
  projectStatusLabel,
} from './project'

const project = (status: string): ProjectBrief => ({
  id: 1,
  customer_id: 2,
  title: '港岛人像企划',
  description: '自然光街拍',
  category: 'portrait',
  city: '香港',
  status,
  created_at: '2026-07-23T08:00:00Z',
})

describe('project management helpers', () => {
  it('maps lifecycle states to concise mobile labels', () => {
    expect(projectStatusLabel('draft')).toBe('草稿')
    expect(projectStatusLabel('converted')).toBe('已转订单')
    expect(applicationStatusLabel('selected')).toBe('已被选中')
  })

  it('only enables lifecycle actions for server-supported states', () => {
    expect(canEditProject(project('open'))).toBe(true)
    expect(canEditProject(project('converted'))).toBe(false)
    expect(canPublishProject(project('expired'))).toBe(true)
    expect(canPublishProject(project('open'))).toBe(false)
    expect(canCloseProject(project('draft'))).toBe(true)
    expect(canCloseProject(project('closed'))).toBe(false)
  })

  it('allows application editing only while both application and project are active', () => {
    const application = {
      id: 3,
      project_id: 1,
      photographer_id: 4,
      status: 'submitted',
      proposal_text: '可执行方案',
      price_quote: 1800,
      project: { id: 1, title: '企划', category: 'portrait', city: '香港', status: 'open' },
    } satisfies ProjectApplication

    expect(canEditProjectApplication(application)).toBe(true)
    expect(canEditProjectApplication({ ...application, status: 'selected' })).toBe(false)
    expect(canEditProjectApplication({ ...application, project: { ...application.project, status: 'closed' } })).toBe(false)
  })
})
