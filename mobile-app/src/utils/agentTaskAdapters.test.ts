import { describe, expect, it } from 'vitest'
import type { AgentTask } from '@/types/agentTask'
import { shouldDisplayAgentTaskDock } from './agentTaskAdapters'

function createTask(taskType: AgentTask['task_type']): AgentTask {
  return {
    task_id: 'task-1',
    conversation_id: 1,
    task_type: taskType,
    status: taskType === 'generate_image' ? 'generating' : 'collecting',
    schema_version: 1,
    revision: 1,
    target: {},
    fields: {},
    summary: {} as AgentTask['summary'],
  }
}

describe('shouldDisplayAgentTaskDock', () => {
  it('hides the generic task dock for single-output image generation', () => {
    expect(shouldDisplayAgentTaskDock(createTask('generate_image'))).toBe(false)
  })

  it('hides the generic task dock for inspiration creation, which has its own chat card', () => {
    expect(shouldDisplayAgentTaskDock(createTask('create_inspiration'))).toBe(false)
  })

  it('keeps the generic task dock for editable agent tasks', () => {
    expect(shouldDisplayAgentTaskDock(createTask('create_project'))).toBe(true)
  })
})
