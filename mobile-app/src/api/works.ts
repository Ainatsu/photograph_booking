import api from './client'
import type { WorkItem } from '@/types/discovery'
import type { WorkPublishMetadata, WorkPublishResponse } from '@/types/publishing'

export async function updateWorkMetadata(
  workId: string,
  metadata: WorkPublishMetadata,
): Promise<WorkItem> {
  const { data } = await api.put<WorkPublishResponse>(`/photographers/works/${workId}`, metadata)
  return data.work
}
