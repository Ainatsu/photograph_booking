const DB_NAME = 'photographer-booking-work-drafts'
const DB_VERSION = 1
const STORE_NAME = 'drafts'

const openDraftDb = () => new Promise((resolve, reject) => {
  const request = indexedDB.open(DB_NAME, DB_VERSION)

  request.onupgradeneeded = () => {
    const db = request.result
    if (!db.objectStoreNames.contains(STORE_NAME)) {
      db.createObjectStore(STORE_NAME, { keyPath: 'id' })
    }
  }

  request.onsuccess = () => resolve(request.result)
  request.onerror = () => reject(request.error)
})

const runStore = async (mode, action) => {
  const db = await openDraftDb()
  return new Promise((resolve, reject) => {
    let request
    const tx = db.transaction(STORE_NAME, mode)

    try {
      const store = tx.objectStore(STORE_NAME)
      request = action(store)
    } catch (error) {
      db.close()
      reject(error)
      return
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
    tx.oncomplete = () => db.close()
    tx.onerror = () => {
      db.close()
      reject(tx.error)
    }
  })
}

export const createDraftId = () => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `draft-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const normalizeTags = (tags) => (
  Array.isArray(tags)
    ? tags.map((tag) => String(tag || '').trim()).filter(Boolean)
    : []
)

const toFileRecord = (file, index) => {
  const source = file?.raw || file
  if (!source) return null

  if (globalThis.Blob && source.blob instanceof Blob) {
    return {
      name: String(source.name || `作品文件${index + 1}`),
      type: String(source.type || source.blob.type || ''),
      lastModified: Number(source.lastModified || Date.now()),
      size: Number(source.size || source.blob.size || 0),
      blob: source.blob,
    }
  }

  if (globalThis.Blob && source instanceof Blob) {
    const type = source.type || ''
    return {
      name: String(source.name || `作品文件${index + 1}`),
      type,
      lastModified: Number(source.lastModified || Date.now()),
      size: Number(source.size || 0),
      blob: source.slice(0, source.size, type),
    }
  }

  return null
}

const hydrateFile = (file, index) => {
  if (!file) return null

  if (globalThis.File && file instanceof File) return file

  if (globalThis.File && globalThis.Blob && file instanceof Blob) {
    return new File([file], file.name || `作品文件${index + 1}`, {
      type: file.type || '',
      lastModified: file.lastModified || Date.now(),
    })
  }

  if (globalThis.File && globalThis.Blob && file.blob instanceof Blob) {
    return new File([file.blob], file.name || `作品文件${index + 1}`, {
      type: file.type || file.blob.type || '',
      lastModified: file.lastModified || Date.now(),
    })
  }

  return null
}

const hydrateDraft = (draft) => {
  if (!draft) return null
  return {
    ...draft,
    tags: normalizeTags(draft.tags),
    files: (Array.isArray(draft.files) ? draft.files : [])
      .map(hydrateFile)
      .filter(Boolean),
    coverFile: hydrateFile(draft.coverFile, 0),
  }
}

export const saveWorkDraft = async ({
  id,
  userId,
  mediaType,
  title,
  tags,
  description,
  files,
  coverFile,
}) => {
  const now = new Date().toISOString()
  const draft = {
    id: id || createDraftId(),
    userId: String(userId || ''),
    mediaType: mediaType || 'image',
    title: String(title || ''),
    tags: normalizeTags(tags),
    description: String(description || ''),
    files: (Array.isArray(files) ? files : [])
      .map(toFileRecord)
      .filter(Boolean),
    coverFile: toFileRecord(coverFile, 0),
    updatedAt: now,
    createdAt: now,
  }

  const existing = id ? await getWorkDraft(id) : null
  if (existing?.createdAt) draft.createdAt = existing.createdAt

  await runStore('readwrite', (store) => store.put(draft))
  return hydrateDraft(draft)
}

export const getWorkDraft = async (id) => {
  if (!id) return null
  const draft = await runStore('readonly', (store) => store.get(id))
  return hydrateDraft(draft)
}

export const deleteWorkDraft = async (id) => {
  if (!id) return
  await runStore('readwrite', (store) => store.delete(id))
}

export const listWorkDrafts = async (userId) => {
  const all = await runStore('readonly', (store) => store.getAll())
  const currentUserId = String(userId || '')
  return (all || [])
    .filter((draft) => String(draft.userId || '') === currentUserId)
    .sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')))
    .map(hydrateDraft)
    .filter(Boolean)
}
