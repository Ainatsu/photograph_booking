import api from './client'
import type {
  PackageOffer,
  PhotographerProfile,
  ProjectBrief,
  ProjectDetailPayload,
  RecommendationResponse,
  WorkItem,
} from '@/types/discovery'

export interface DiscoverySearchParams {
  query?: string
  city?: string
  style?: string
  budget_min?: number | null
  budget_max?: number | null
  skip?: number
  limit?: number
}

export interface DiscoverySearchResults {
  works: WorkItem[]
  photographers: PhotographerProfile[]
  packages: PackageOffer[]
  projects: ProjectBrief[]
}

function compactParams(params: Record<string, string | number | null | undefined>) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined),
  )
}

function normalizedSearchParams(params: DiscoverySearchParams) {
  return {
    query: params.query?.trim(),
    city: params.city?.trim(),
    style: params.style?.trim(),
    budget_min: params.budget_min,
    budget_max: params.budget_max,
    skip: params.skip,
    limit: params.limit,
  }
}

export async function getWorks(params: DiscoverySearchParams = {}): Promise<WorkItem[]> {
  const search = normalizedSearchParams(params)
  const { data } = await api.get<WorkItem[]>('/photographers/works', {
    params: compactParams({
      query: search.query,
      city: search.city,
      style: search.style,
      skip: search.skip ?? 0,
      limit: search.limit ?? 60,
    }),
  })
  return data
}

export async function getWorkFeed(): Promise<WorkItem[]> {
  try {
    const { data } = await api.get<RecommendationResponse<WorkItem>>('/recommendations/works', {
      params: { limit: 40, scene: 'home_feed' },
    })
    return data.items || []
  } catch {
    return getWorks()
  }
}

export async function getPhotographers(
  params: DiscoverySearchParams = {},
): Promise<PhotographerProfile[]> {
  const search = normalizedSearchParams(params)
  const { data } = await api.get<PhotographerProfile[]>('/photographers/profiles', {
    params: compactParams({
      query: search.query,
      city: search.city,
      style: search.style,
      skip: search.skip ?? 0,
      limit: search.limit ?? 40,
    }),
  })
  return data
}

export async function getPackages(params: DiscoverySearchParams = {}): Promise<PackageOffer[]> {
  const search = normalizedSearchParams(params)
  const { data } = await api.get<PackageOffer[]>('/photographers/packages', {
    params: compactParams({
      query: search.query,
      city: search.city,
      style: search.style,
      budget_min: search.budget_min,
      budget_max: search.budget_max,
      skip: search.skip ?? 0,
      limit: search.limit ?? 60,
    }),
  })
  return data
}

export async function getPackageFeed(): Promise<PackageOffer[]> {
  try {
    const { data } = await api.get<RecommendationResponse<PackageOffer>>(
      '/recommendations/packages',
      { params: { limit: 30 } },
    )
    return data.items || []
  } catch {
    return getPackages()
  }
}

export async function getProjects(params: DiscoverySearchParams & { customer_id?: number } = {}): Promise<ProjectBrief[]> {
  const search = normalizedSearchParams(params)
  const { data } = await api.get<ProjectBrief[]>('/projects/', {
    params: compactParams({
      query: search.query,
      city: search.city,
      style_tags: search.style,
      budget_min: search.budget_min,
      budget_max: search.budget_max,
      customer_id: (params as Record<string, unknown>).customer_id as number | undefined,
      skip: search.skip ?? 0,
      limit: search.limit ?? 30,
    }),
  })
  return data
}

export async function searchDiscovery(
  params: DiscoverySearchParams,
): Promise<DiscoverySearchResults> {
  const shared = { ...params, skip: params.skip ?? 0, limit: params.limit ?? 60 }
  const [works, photographers, packages, projects] = await Promise.all([
    getWorks(shared),
    getPhotographers(shared),
    getPackages(shared),
    getProjects(shared),
  ])
  return { works, photographers, packages, projects }
}

export async function getWorkDetail(id: string): Promise<WorkItem> {
  const { data } = await api.get<WorkItem>(`/photographers/works/${id}`)
  return data
}

export async function getPhotographerDetail(userId: number): Promise<PhotographerProfile> {
  const { data } = await api.get<PhotographerProfile>(`/photographers/profile/${userId}`)
  return data
}

export async function getPackageDetail(id: string): Promise<PackageOffer> {
  const { data } = await api.get<PackageOffer>(`/photographers/packages/${id}`)
  return data
}

export async function getProjectDetail(id: number): Promise<ProjectDetailPayload> {
  const { data } = await api.get<ProjectDetailPayload>(`/projects/${id}`)
  return data
}
