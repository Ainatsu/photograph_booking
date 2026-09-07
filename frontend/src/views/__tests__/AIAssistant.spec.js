import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import AIAssistant from '../../views/AIAssistant.vue'
import { resetAIConversationState } from '../../composables/useAIConversation'

const {
  mockCreate,
  mockGetConversations,
  mockGetMessages,
  mockSendMessage,
  mockUploadImage,
  mockPush,
  mockSearchConversations,
  mockForkConversation,
  mockSaveWorkDraft,
} = vi.hoisted(() => ({
  mockCreate: vi.fn(),
  mockGetConversations: vi.fn(),
  mockGetMessages: vi.fn(),
  mockSendMessage: vi.fn(),
  mockUploadImage: vi.fn(),
  mockPush: vi.fn(),
  mockSearchConversations: vi.fn(),
  mockForkConversation: vi.fn(),
  mockSaveWorkDraft: vi.fn(),
}))

vi.mock('../../api/ai', () => ({
  createAIConversation: (...args) => mockCreate(...args),
  getAIConversations: (...args) => mockGetConversations(...args),
  getAIMessages: (...args) => mockGetMessages(...args),
  sendAIMessage: (...args) => mockSendMessage(...args),
  uploadAIImage: (...args) => mockUploadImage(...args),
  searchAIConversations: (...args) => mockSearchConversations(...args),
  forkAIConversation: (...args) => mockForkConversation(...args),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, replace: mockPush }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('../../utils/workDrafts', () => ({
  saveWorkDraft: (...args) => mockSaveWorkDraft(...args),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}))

const flushPromises = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

const mountAssistant = (props = {}) => mount(AIAssistant, {
  props,
  global: {
    stubs: {
      'el-button': {
        template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        props: ['disabled', 'loading', 'icon', 'circle', 'type', 'size'],
        emits: ['click'],
      },
      'el-tooltip': { template: '<div><slot /></div>' },
      'el-empty': { template: '<div class="el-empty"><slot />{{ description }}</div>', props: ['description'] },
      'el-input': {
        template: '<textarea :id="id" :rows="rows" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @blur="$emit(\'blur\', $event)" @keydown="$emit(\'keydown\', $event)" />',
        props: ['modelValue', 'type', 'rows', 'resize', 'maxlength', 'showWordLimit', 'placeholder', 'disabled', 'id'],
        emits: ['update:modelValue', 'blur', 'keydown'],
      },
      'el-calendar': {
        props: ['modelValue'],
        methods: {
          selectDate() {},
        },
        template: `
          <div class="calendar-stub">
            <slot name="header" date="2026年7月" :select-date="selectDate" />
            <slot
              name="date-cell"
              :data="{ day: '2026-07-21', type: 'current-month', isSelected: false }"
            />
          </div>
        `,
      },
    },
  },
})

describe('AIAssistant', () => {
  beforeEach(() => {
    resetAIConversationState()
    localStorage.clear()
    localStorage.setItem('token', 'test-token')
    mockCreate.mockReset()
    mockGetConversations.mockReset()
    mockGetMessages.mockReset()
    mockSendMessage.mockReset()
    mockUploadImage.mockReset()
    mockPush.mockReset()
    mockSearchConversations.mockReset()
    mockForkConversation.mockReset()
    mockSaveWorkDraft.mockReset()
    mockGetConversations.mockResolvedValue({ data: [] })
    mockGetMessages.mockResolvedValue({ data: [] })
    mockSearchConversations.mockResolvedValue({ data: [] })
    mockForkConversation.mockResolvedValue({ data: { id: 2, title: '分支', updated_at: '2026-06-16T10:00:00' } })
    mockSaveWorkDraft.mockResolvedValue({ id: 'agent-work-draft-1' })
    mockCreate.mockResolvedValue({
      data: { id: 1, title: null, created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' },
    })
    mockSendMessage.mockResolvedValue({
      data: {
        user_message: {
          id: 1,
          conversation_id: 1,
          role: 'user',
          content: '生日写真怎么选风格？',
          created_at: '2026-06-16T10:01:00',
        },
        assistant_message: {
          id: 2,
          conversation_id: 1,
          role: 'assistant',
          content: '可以先看预算、城市和用途。',
          created_at: '2026-06-16T10:01:01',
        },
      },
    })
  })

  it('loads conversations on mount', async () => {
    mountAssistant()
    await flushPromises()

    expect(mockGetConversations).toHaveBeenCalled()
  })

  it('places quick prompts directly above the chat input', async () => {
    const wrapper = mountAssistant({ quickPrompts: ['帮我规划写真', '推荐摄影师'] })
    await flushPromises()

    const inputArea = wrapper.find('.chat-input-area')
    const quickPrompts = inputArea.find('.quick-prompts')
    const inputRow = inputArea.find('.chat-input-row')

    expect(quickPrompts.exists()).toBe(true)
    expect(inputRow.exists()).toBe(true)
    expect(
      quickPrompts.element.compareDocumentPosition(inputRow.element)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('splits assistant replies into natural reveal segments', async () => {
    const wrapper = mountAssistant()
    await flushPromises()

    expect(wrapper.vm.splitResponseSegments('先说第一件事。\n\n再说第二件事。')).toEqual([
      '先说第一件事。',
      '再说第二件事。',
    ])
    expect(wrapper.vm.splitResponseSegments('第一句。第二句。第三句。')).toEqual([
      '第一句。第二句。',
      '第三句。',
    ])
  })

  it('renders each assistant paragraph in its own chat bubble', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '分段回复', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    mockGetMessages.mockResolvedValue({
      data: [{
        id: 2,
        conversation_id: 1,
        role: 'assistant',
        content: '这是第一段。\n\n这是第二段。',
        created_at: '2026-06-16T10:01:01',
      }],
    })

    const wrapper = mountAssistant()
    await flushPromises()

    const bubbles = wrapper.findAll('.segmented-message-bubble .message-content-card')
    expect(bubbles).toHaveLength(2)
    expect(bubbles[0].text()).toContain('这是第一段。')
    expect(bubbles[1].text()).toContain('这是第二段。')
    expect(wrapper.findAll('.message-time')).toHaveLength(1)
  })

  it('renders assistant references as standalone cards', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '作品推荐', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    mockGetMessages.mockResolvedValue({
      data: [{
        id: 2,
        conversation_id: 1,
        role: 'assistant',
        content: '我找到了一组作品。',
        created_at: '2026-06-16T10:01:01',
        metadata: {
          references: {
            photographers: [],
            packages: [],
            portfolio_items: [{ id: 'work-1', title: '窗边光影', url: '/static/work.jpg' }],
          },
        },
      }],
    })

    const wrapper = mountAssistant()
    await flushPromises()

    expect(wrapper.find('.reference-message-bubble').exists()).toBe(true)
    expect(wrapper.find('.reference-panel').exists()).toBe(true)
    expect(wrapper.find('.reference-card').text()).toContain('窗边光影')
  })

  it('creates a new conversation', async () => {
    const wrapper = mountAssistant()
    await flushPromises()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(mockCreate).toHaveBeenCalled()
    expect(mockGetMessages).toHaveBeenCalledWith(1, { limit: 200 })
  })

  it('sends a message and renders the reply', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '生日写真', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    const wrapper = mountAssistant()
    await flushPromises()

    wrapper.vm.inputText = '生日写真怎么选风格？'
    await wrapper.vm.handleSend()
    await flushPromises()

    expect(mockSendMessage).toHaveBeenCalledWith(1, { content: '生日写真怎么选风格？' })
    expect(wrapper.text()).toContain('可以先看预算、城市和用途。')
  })

  it('shares one persisted conversation between page and floating assistants', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '统一会话', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })

    const floatingAssistant = mountAssistant({ embedded: true })
    const pageAssistant = mountAssistant()
    await flushPromises()

    floatingAssistant.vm.inputText = '两个入口应该看到同一条消息'
    await floatingAssistant.vm.handleSend()
    await flushPromises()

    expect(mockGetConversations).toHaveBeenCalledTimes(1)
    expect(mockGetMessages).toHaveBeenCalledTimes(1)
    expect(pageAssistant.text()).toContain('可以先看预算、城市和用途。')
  })

  it('restores floating assistant messages after a page refresh', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '刷新恢复', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:01:01' }],
    })
    mockSendMessage.mockResolvedValue({
      data: {
        user_message: {
          id: 1,
          conversation_id: 1,
          role: 'user',
          content: '刷新后也要保留',
          created_at: '2026-06-16T10:01:00',
        },
        assistant_message: {
          id: 2,
          conversation_id: 1,
          role: 'assistant',
          content: '这条回复来自已持久化的会话。',
          created_at: '2026-06-16T10:01:01',
        },
      },
    })

    const floatingAssistant = mountAssistant({ embedded: true })
    await flushPromises()
    floatingAssistant.vm.inputText = '刷新后也要保留'
    await floatingAssistant.vm.handleSend()
    const sentResponse = await mockSendMessage.mock.results[0].value
    floatingAssistant.unmount()

    resetAIConversationState()
    mockGetMessages.mockResolvedValue({
      data: [
        sentResponse.data.user_message,
        sentResponse.data.assistant_message,
      ],
    })

    const refreshedAssistant = mountAssistant({ embedded: true })
    await flushPromises()

    expect(refreshedAssistant.text()).toContain('刷新后也要保留')
    expect(refreshedAssistant.text()).toContain('这条回复来自已持久化的会话。')
  })

  it('sends page context with messages', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '套餐咨询', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    const pageContext = {
      route_name: 'PackageDetail',
      route_path: '/package/7',
      resource_type: 'package',
      resource_id: '7',
      title: '自然光写真套餐',
    }
    const wrapper = mountAssistant({ pageContext })
    await flushPromises()

    wrapper.vm.inputText = '这个适不适合我？'
    await wrapper.vm.handleSend()
    await flushPromises()

    expect(mockSendMessage).toHaveBeenCalledWith(1, {
      content: '这个适不适合我？',
      page_context: pageContext,
    })
  })

  it('restores a referenced work card from persisted message metadata', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: 'Work inquiry', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    mockGetMessages.mockResolvedValue({
      data: [{
        id: 1,
        conversation_id: 1,
        role: 'user',
        content: 'Tell me about this work.',
        created_at: '2026-06-16T10:01:00',
        metadata: {
          page_context: {
            resource_type: 'portfolio_item',
            resource_id: 'work-1',
            route_path: '/work/work-1',
            title: 'Spring Portrait',
            current_object: { thumbnail_url: '/static/work.jpg' },
          },
        },
      }],
    })

    const wrapper = mountAssistant()
    await flushPromises()

    expect(wrapper.find('.message-context-card').exists()).toBe(true)
    expect(wrapper.find('.message-stack > .message-context-card').exists()).toBe(true)
    expect(wrapper.find('.message-bubble .message-context-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('引用作品')
    expect(wrapper.text()).toContain('Spring Portrait')
  })

  it('renders recommendation references from assistant metadata', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '推荐摄影师', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    mockGetMessages.mockResolvedValue({
      data: [{
        id: 2,
        conversation_id: 1,
        role: 'assistant',
        content: '这些资源更匹配你的需求。',
        created_at: '2026-06-16T10:01:01',
        metadata: {
          references: {
            photographers: [{
              user_id: 9,
              user_display_name: '测试摄影师',
              location: '北京',
              styles: ['日系', '人像'],
            }],
            portfolio_items: [{
              id: 'work-1',
              url: '/static/work.jpg',
              title: '春日写真',
              tag: '人像',
              tags: ['日系'],
              user_display_name: '测试摄影师',
            }],
            packages: [{
              id: 'pkg-1',
              package_name: '个人写真',
              price: 699,
              duration: 120,
              photographer_name: '测试摄影师',
            }],
          },
        },
      }],
    })

    const wrapper = mountAssistant()
    await flushPromises()

    expect(wrapper.text()).toContain('推荐摄影师')
    expect(wrapper.text()).toContain('测试摄影师')
    expect(wrapper.text()).toContain('春日写真')
    expect(wrapper.text()).toContain('个人写真')
  })

  it('renders task state as a task card', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '发布企划', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    mockGetMessages.mockResolvedValue({
      data: [{
        id: 2,
        conversation_id: 1,
        role: 'assistant',
        content: '请直接在企划进度卡片中补充信息。',
        created_at: '2026-06-16T10:01:01',
        metadata: {
          task_state: {
            task_type: 'create_project',
            status: 'awaiting_details',
            slots: {},
            missing_slots: ['city', 'budget_max', 'style', 'date', 'people_count', 'description'],
            pending_action: null,
          },
        },
      }, {
        id: 3,
        conversation_id: 1,
        role: 'assistant',
        content: '我先把企划草稿整理好了。',
        created_at: '2026-06-16T10:02:01',
        metadata: {
          suggested_actions: [{
            type: 'confirm_create_project',
            label: '确认发布企划',
            requires_confirmation: true,
          }],
          task_state: {
            task_type: 'create_project',
            status: 'awaiting_confirmation',
            slots: {
              title: '北京日系写真',
              city: '北京',
              budget_max: 800,
              style: '日系',
              date: '2026-07-20',
              people_count: 1,
              description: '想拍清新自然的人像',
            },
            missing_slots: [],
            pending_action: {
              tool: 'create_project',
              input: {},
            },
          },
        },
      }],
    })

    const wrapper = mountAssistant()
    await flushPromises()

    expect(wrapper.text()).toContain('企划发布任务')
    expect(wrapper.findAll('.task-card')).toHaveLength(1)
    expect(wrapper.find('.task-message-bubble').exists()).toBe(true)
    expect(wrapper.findAll('.project-editor-field')).toHaveLength(10)
    expect(wrapper.find('.project-editor-hint').exists()).toBe(false)
    expect(wrapper.find('.field-location_text .project-editor-label').exists()).toBe(false)
    expect(wrapper.find('.field-title textarea').element.value).toBe('北京日系写真')
    expect(wrapper.find('.field-city textarea').element.value).toBe('北京')
    expect(wrapper.find('.field-description textarea').element.value).toBe('想拍清新自然的人像')
    expect(wrapper.find('.field-description textarea').attributes('rows')).toBe('3')
    expect(wrapper.find('.field-date .project-date-trigger').text()).toContain('2026年7月20日')
    expect(wrapper.find('.field-date .project-time-control input').element.value).toBe('')
    expect(wrapper.text()).toContain('保存为草稿')
    expect(wrapper.text()).toContain('发布')
    expect(wrapper.text()).not.toContain('下一步')
    expect(wrapper.text()).not.toContain('更新草稿')

    await wrapper.find('.field-city textarea').setValue('上海')
    await wrapper.find('.field-city textarea').trigger('blur')
    expect(JSON.parse(localStorage.getItem('ai-project-card-1-3-create_project')).city).toBe('上海')
    expect(wrapper.text()).toContain('拍摄城市已自动保存')

    await wrapper.find('.field-date .project-date-trigger').trigger('click')
    expect(wrapper.find('.project-date-selection').exists()).toBe(true)
    expect(wrapper.find('.field-people_count').exists()).toBe(false)
    expect(wrapper.find('.field-budget_max').exists()).toBe(false)
    expect(wrapper.find('.field-deliverables').exists()).toBe(false)
    expect(wrapper.find('.field-reference_images').exists()).toBe(true)

    await wrapper.find('.project-calendar-day').trigger('click')
    await flushPromises()
    expect(wrapper.find('.project-date-selection').exists()).toBe(false)
    expect(wrapper.find('.field-people_count').exists()).toBe(true)
    expect(JSON.parse(localStorage.getItem('ai-project-card-1-3-create_project')).date).toBe('2026-07-21')

    await wrapper.find('.field-date .project-time-control input').setValue('10:30')
    expect(JSON.parse(localStorage.getItem('ai-project-card-1-3-create_project'))).toEqual(expect.objectContaining({
      date: '2026-07-21',
      time: '10:30',
    }))

    await wrapper.find('.project-editor-actions button:last-child').trigger('click')
    await flushPromises()

    const publishPayload = mockSendMessage.mock.calls.at(-1)[1]
    expect(publishPayload.content).toBe('发布企划')
    expect(publishPayload.task_submission).toEqual(expect.objectContaining({
      task_type: 'create_project',
      action: 'publish',
      skip_reference_images: true,
    }))
    expect(publishPayload.task_submission.slots).toEqual(expect.objectContaining({
      title: '北京日系写真',
      city: '上海',
      budget_max: 800,
      date: '2026-07-21',
      time: '10:30',
    }))
  })

  it('edits, locally saves, and publishes a package from the publisher card', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '发布方案', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    mockGetMessages.mockResolvedValue({
      data: [{
        id: 8,
        conversation_id: 1,
        role: 'assistant',
        content: '方案信息已经整理好了，可以直接修改后发布。',
        created_at: '2026-06-16T10:02:01',
        metadata: {
          task_state: {
            task_type: 'publish_package',
            status: 'awaiting_confirmation',
            slots: {
              package_name: '城市漫步写真',
              city: '香港',
              style: ['人像'],
              price: 1280,
              duration_minutes: 150,
              image_count: 24,
              package_includes: ['底片全送'],
              package_description: '适合个人或情侣的城市漫步写真。',
              sample_images: ['/static/ai/package-sample.jpg'],
            },
            missing_slots: [],
            pending_action: {
              tool: 'publish_package',
              input: {},
            },
          },
        },
      }],
    })

    const wrapper = mountAssistant()
    await flushPromises()

    expect(wrapper.text()).toContain('方案发布任务')
    expect(wrapper.findAll('.project-editor-field')).toHaveLength(9)
    expect(wrapper.find('.field-package_name textarea').element.value).toBe('城市漫步写真')
    expect(wrapper.find('.field-price .project-editor-unit').text()).toBe('元')
    expect(wrapper.find('.field-style .project-editor-helper').text()).toContain('顿号或逗号')
    expect(wrapper.find('.field-sample_images .project-reference-trigger').text()).toContain('已添加 1 张')
    expect(wrapper.text()).toContain('暂存草稿')
    expect(wrapper.text()).toContain('发布方案')

    await wrapper.find('.field-style textarea').setValue('胶片，街拍\n自然光')
    await wrapper.find('.field-style textarea').trigger('blur')
    await wrapper.find('.field-package_includes textarea').setValue('底片全送、两套造型\n线上选片')
    await wrapper.find('.field-package_includes textarea').trigger('blur')
    await wrapper.find('.project-editor-actions button:first-child').trigger('click')

    const storageKey = 'ai-package-card-1-8-publish_package'
    expect(mockSendMessage).not.toHaveBeenCalled()
    expect(JSON.parse(localStorage.getItem(storageKey))).toEqual(expect.objectContaining({
      style: ['胶片', '街拍', '自然光'],
      package_includes: ['底片全送', '两套造型', '线上选片'],
      sample_images: ['/static/ai/package-sample.jpg'],
    }))
    expect(wrapper.text()).toContain('方案草稿已暂存到本机')

    await wrapper.find('.project-editor-actions button:last-child').trigger('click')
    await flushPromises()

    const publishPayload = mockSendMessage.mock.calls.at(-1)[1]
    expect(publishPayload.content).toBe('发布方案')
    expect(publishPayload.task_submission).toEqual(expect.objectContaining({
      task_type: 'publish_package',
      action: 'publish',
      skip_reference_images: false,
    }))
    expect(publishPayload.task_submission.slots).toEqual(expect.objectContaining({
      package_name: '城市漫步写真',
      city: '香港',
      style: ['胶片', '街拍', '自然光'],
      price: 1280,
      duration_minutes: 150,
      image_count: 24,
      package_includes: ['底片全送', '两套造型', '线上选片'],
      package_description: '适合个人或情侣的城市漫步写真。',
      sample_images: ['/static/ai/package-sample.jpg'],
    }))
    expect(localStorage.getItem(storageKey)).toBeNull()
  })

  it('renders a trusted work publisher action, saves the draft, and navigates once', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '发布作品', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    mockGetMessages.mockResolvedValue({
      data: [{
        id: 21,
        conversation_id: 1,
        role: 'assistant',
        content: '作品草稿已经准备好了。',
        created_at: '2026-06-16T10:01:01',
        metadata: {
          client_actions: [{
            type: 'open_work_publisher',
            label: '去发布作品',
            draft: {
              title: '雨夜街头',
              description: '记录雨夜中的城市光影。',
              tags: ['街拍', '夜景'],
            },
          }, {
            type: 'open_untrusted_route',
            label: '不应显示',
            route: '/admin',
          }],
        },
      }],
    })

    const wrapper = mountAssistant()
    await flushPromises()

    expect(wrapper.text()).toContain('去发布作品')
    expect(wrapper.text()).not.toContain('不应显示')

    const button = wrapper.find('.client-actions button')
    await Promise.all([button.trigger('click'), button.trigger('click')])
    await flushPromises()

    expect(mockSaveWorkDraft).toHaveBeenCalledTimes(1)
    expect(mockSaveWorkDraft).toHaveBeenCalledWith(expect.objectContaining({
      mediaType: 'image',
      title: '雨夜街头',
      description: '记录雨夜中的城市光影。',
      tags: ['街拍', '夜景'],
    }))
    expect(mockPush).toHaveBeenCalledWith({
      name: 'UploadWork',
      query: { draftId: 'agent-work-draft-1' },
    })
  })

  it('opens the selected project application and disables an invalid application action', async () => {
    mockGetConversations.mockResolvedValue({
      data: [{ id: 1, title: '应邀企划', created_at: '2026-06-16T10:00:00', updated_at: '2026-06-16T10:00:00' }],
    })
    mockGetMessages.mockResolvedValue({
      data: [{
        id: 22,
        conversation_id: 1,
        role: 'assistant',
        content: '已找到目标企划。',
        created_at: '2026-06-16T10:01:01',
        metadata: {
          client_actions: [{
            type: 'open_project_application',
            label: '填写应邀方案',
            project_id: 42,
          }],
        },
      }, {
        id: 23,
        conversation_id: 1,
        role: 'assistant',
        content: '另一个目标企划缺失。',
        created_at: '2026-06-16T10:02:01',
        metadata: {
          client_actions: [{
            type: 'open_project_application',
            label: '填写另一个应邀方案',
          }],
        },
      }],
    })

    const wrapper = mountAssistant()
    await flushPromises()

    const buttons = wrapper.findAll('.client-actions button')
    expect(buttons).toHaveLength(2)
    expect(buttons[1].attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('缺少目标企划')

    await buttons[0].trigger('click')
    await flushPromises()

    expect(mockPush).toHaveBeenCalledWith({
      name: 'ProjectApply',
      params: { projectId: '42' },
    })
  })

  it('redirects anonymous users to login', async () => {
    localStorage.removeItem('token')
    mountAssistant()
    await flushPromises()

    expect(mockPush).toHaveBeenCalledWith('/login')
  })
})
