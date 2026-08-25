import api from './client'
import type {
  ProjectBrief,
  ProjectApplication,
  ProjectApplicationPayload,
  ProjectSelectionResponse,
} from '@/types/discovery'
import type { ProjectUpdatePayload } from '@/types/publishing'

export async function getMyProjects(status?: string): Promise<ProjectBrief[]> {
  const { data } = await api.get<ProjectBrief[]>('/projects/my', {
    params: { status: status || undefined, skip: 0, limit: 100 },
  })
  return data
}

export async function getMyProjectApplications(status?: string): Promise<ProjectApplication[]> {
  const { data } = await api.get<ProjectApplication[]>('/projects/my-applications', {
    params: { status: status || undefined, skip: 0, limit: 100 },
  })
  return data
}

export async function updateProject(
  projectId: number,
  payload: ProjectUpdatePayload,
): Promise<ProjectBrief> {
  const { data } = await api.put<ProjectBrief>(`/projects/${projectId}`, payload)
  return data
}

export async function publishProject(projectId: number): Promise<ProjectBrief> {
  const { data } = await api.put<ProjectBrief>(`/projects/${projectId}/publish`)
  return data
}

export async function closeProject(projectId: number, reason: string): Promise<ProjectBrief> {
  const { data } = await api.put<ProjectBrief>(`/projects/${projectId}/close`, { reason })
  return data
}

export async function applyToProject(
  projectId: number,
  payload: ProjectApplicationPayload,
): Promise<ProjectApplication> {
  const { data } = await api.post<ProjectApplication>(`/projects/${projectId}/applications`, payload)
  return data
}

export async function updateMyProjectApplication(
  projectId: number,
  payload: ProjectApplicationPayload,
): Promise<ProjectApplication> {
  const { data } = await api.put<ProjectApplication>(`/projects/${projectId}/applications/me`, payload)
  return data
}

export async function withdrawMyProjectApplication(projectId: number): Promise<ProjectApplication> {
  const { data } = await api.put<ProjectApplication>(`/projects/${projectId}/applications/me/withdraw`)
  return data
}

export async function selectProjectApplication(
  projectId: number,
  applicationId: number,
): Promise<ProjectSelectionResponse> {
  const { data } = await api.post<ProjectSelectionResponse>(
    `/projects/${projectId}/applications/${applicationId}/select`,
  )
  return data
}
