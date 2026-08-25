import { ref } from 'vue'
import {
  createAIConversation,
  getAIConversations,
  getAIMessages,
} from '../api/ai'

const conversationId = ref(null)
const messages = ref([])
const loadingMessages = ref(false)

let initializedToken = null
let initializationPromise = null

const clearState = () => {
  conversationId.value = null
  messages.value = []
  loadingMessages.value = false
  initializationPromise = null
}

const syncToken = () => {
  const token = localStorage.getItem('token')
  if (token !== initializedToken) {
    initializedToken = token
    clearState()
  }
  return token
}

const reloadMessages = async () => {
  if (!conversationId.value) {
    messages.value = []
    return
  }
  const response = await getAIMessages(conversationId.value, { limit: 200 })
  messages.value = response.data || []
}

const initializeConversation = async () => {
  const token = syncToken()
  if (!token) return
  if (conversationId.value) return
  if (initializationPromise) return initializationPromise

  loadingMessages.value = true
  initializationPromise = (async () => {
    const response = await getAIConversations()
    if (response.data?.length) {
      conversationId.value = response.data[0].id
    } else {
      const created = await createAIConversation()
      conversationId.value = created.data.id
    }
    await reloadMessages()
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
  messages,
  loadingMessages,
  initializeConversation,
  reloadMessages,
  appendMessages,
})
