import { describe, expect, it } from 'vitest'
import { getAgentTaskRoute } from './agentTaskRoutes'

describe('getAgentTaskRoute', () => {
  it('keeps booking editor bound to both photographer and selected package', () => {
    const route = getAgentTaskRoute({
      task_id: 'task-1',
      conversation_id: 1,
      task_type: 'create_booking',
      status: 'collecting',
      schema_version: 2,
      revision: 1,
      target: { photographer_id: 4, package_id: 'pkg-18ac' },
      fields: {},
      summary: {} as any,
    })

    expect(route).toEqual({
      name: 'booking',
      params: { userId: '4' },
      query: { agentTaskId: 'task-1', from: 'ai-assistant', packageId: 'pkg-18ac' },
    })
  })

  it('does not open an unbound photographer booking page', () => {
    expect(getAgentTaskRoute({
      task_id: 'task-2', conversation_id: 1, task_type: 'create_booking', status: 'collecting',
      schema_version: 2, revision: 1, target: { photographer_id: 4 }, fields: {}, summary: {} as any,
    })).toBeNull()
  })

  it('does not route completed inspiration creation through a task editor', () => {
    expect(getAgentTaskRoute({
      task_id: 'task-3', conversation_id: 1, task_type: 'create_inspiration', status: 'completed',
      schema_version: 1, revision: 2, target: {}, fields: { inspiration_id: 9 }, summary: {} as any,
    })).toBeNull()
  })
})
