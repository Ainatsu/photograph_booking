import { computed, ref } from 'vue'
import {
  createAIConversation,
  getAIConversations,
  getAIMessages,
  updateAIConversation,
  getAIConversationToolPolicy,
  searchAIConversations,
  forkAIConversation,
} from '../api/ai'

const ACTIVE_CONVERSATION_KEY = 'ai_active_conversation_id'

const conversationId = ref(null)
const conversations = ref([])
const messages = ref([])
const loadingMessages = ref(false)
const mutatingConversation = ref(false)
const conversationSearch = ref('')
const toolPolicy = ref(null)
const activeConversation = computed(() => (
  conversations.value.find(item => String(item.id) === String(conversationId.value)) || null
))

let initializedToken = null
let initializationPromise = null
let loadSequence = 0

const clearState = () => {
  conversationId.value = null
  conversations.value = []
  toolPolicy.value = null
  messages.value = []
  loadingMessages.value = false
  initializationPromise = null
  loadSequence += 1
}

const syncToken = () => {
  const token = localStorage.getItem('token')
  if (token !== initializedToken) {
    initializedToken = token
    clearState()
  }
  return token
}

const refreshConversations = async (params = {}) => {
  const response = await getAIConversations({ limit: 100, ...params })
  conversations.value = response.data || []
  return conversations.value
}

const searchConversations = async (query) => {
  conversationSearch.value = query || ''
  if (!conversationSearch.value.trim()) return refreshConversations()
  const response = await searchAIConversations({ q: conversationSearch.value.trim(), limit: 100 })
  conversations.value = response.data || []
  return conversations.value
}

const forkConversation = async (targetId, options = {}) => {
  mutatingConversation.value = true
  try {
    const response = await forkAIConversation(targetId, options)
    const created = response.data
    conversations.value = [created, ...conversations.value]
    await selectConversation(created.id)
    return created
  } finally {
    mutatingConversation.value = false
  }
}

const reloadMessages = async () => {
  const targetId = conversationId.value
  const sequence = ++loadSequence
  if (!targetId) {
    messages.value = []
    return
  }
  const response = await getAIMessages(targetId, { limit: 200 })
  if (sequence === loadSequence && String(targetId) === String(conversationId.value)) {
    messages.value = response.data || []
  }
}

const selectConversation = async (targetId) => {
  if (!targetId) return
  if (String(targetId) === String(conversationId.value) && messages.value.length) return
  loadingMessages.value = true
  conversationId.value = targetId
  try {
    const policyResponse = await getAIConversationToolPolicy(targetId)
    toolPolicy.value = policyResponse.data || null
  } catch {
    toolPolicy.value = null
  }
  localStorage.setItem(ACTIVE_CONVERSATION_KEY, String(targetId))
  messages.value = []
  try {
    await reloadMessages()
  } finally {
    loadingMessages.value = false
  }
}

const createConversation = async (title = null) => {
  mutatingConversation.value = true
  try {
    const response = await createAIConversation(title ? { title } : {})
    const created = response.data
    conversations.value = [created, ...conversations.value]
    await selectConversation(created.id)
    return created
  } finally {
    mutatingConversation.value = false
  }
}

const renameConversation = async (targetId, title) => {
  mutatingConversation.value = true
  try {
    const response = await updateAIConversation(targetId, { title })
    conversations.value = conversations.value.map(item => (
      String(item.id) === String(targetId) ? response.data : item
    ))
    return response.data
  } finally {
    mutatingConversation.value = false
  }
}

const archiveConversation = async (targetId) => {
  mutatingConversation.value = true
  try {
    await updateAIConversation(targetId, { archived: true })
    conversations.value = conversations.value.filter(item => String(item.id) !== String(targetId))
    if (String(conversationId.value) === String(targetId)) {
      const next = conversations.value[0]
      if (next) await selectConversation(next.id)
      else await createConversation()
    }
  } finally {
    mutatingConversation.value = false
  }
}

const initializeConversation = async () => {
  const token = syncToken()
  if (!token) return
  if (conversationId.value && conversations.value.length) return
  if (initializationPromise) return initializationPromise

  loadingMessages.value = true
  initializationPromise = (async () => {
    const available = await refreshConversations()
    const savedId = localStorage.getItem(ACTIVE_CONVERSATION_KEY)
    const selected = available.find(item => String(item.id) === String(savedId)) || available[0]
    if (selected) await selectConversation(selected.id)
    else await createConversation()
  })()

  try {
    await initializationPromise
  } finally {
    loadingMessages.value = false
    initializationPromise = null
  }
}

const appendMessages = (...newMessages) => {
  const existingIds = new Set(messages.value.map(message => message.id))
  const uniqueMessages = newMessages.filter(message => message && !existingIds.has(message.id))
  if (uniqueMessages.length) messages.value.push(...uniqueMessages)
}

export const resetAIConversationState = () => {
  initializedToken = null
  clearState()
}

export const useAIConversation = () => ({
  conversationId,
  conversations,
  activeConversation,
  messages,
  loadingMessages,
  mutatingConversation,
  initializeConversation,
  refreshConversations,
  searchConversations,
  forkConversation,
  reloadMessages,
  selectConversation,
  createConversation,
  toolPolicy,
  renameConversation,
  archiveConversation,
  appendMessages,
})
