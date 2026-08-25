import { AxiosError } from 'axios'
import api from './client'
import type { PackageOffer, PhotographerProfile } from '@/types/discovery'
import type { PackageCreatePayload, PackagePublishResponse } from '@/types/publishing'
import { removePackageById, updatePackageById } from '@/utils/package'

type PackageWriteItem = PackageOffer | PackageCreatePayload

export async function getPhotographerPackageProfile(
  userId: number,
): Promise<PhotographerProfile | null> {
  try {
    const { data } = await api.get<PhotographerProfile>(`/photographers/profile/${userId}`)
    return data
  } catch (error) {
    if (error instanceof AxiosError && error.response?.status === 404) return null
    throw error
  }
}

export async function getPhotographerPackages(userId: number): Promise<PackageOffer[]> {
  const profile = await getPhotographerPackageProfile(userId)
  return profile?.packages || []
}

export async function replacePhotographerPackages(
  packages: PackageWriteItem[],
): Promise<PhotographerProfile> {
  const { data } = await api.post<PhotographerProfile>('/photographers/profile', { packages })
  return data
}

export async function appendPhotographerPackage(
  userId: number,
  payload: PackageCreatePayload,
): Promise<PackagePublishResponse> {
  const existingPackages = await getPhotographerPackages(userId)
  const profile = await replacePhotographerPackages([...existingPackages, payload])
  const packages = profile.packages || []
  return { profile, package: packages[packages.length - 1] || null }
}

export async function updatePhotographerPackage(
  userId: number,
  packageId: string,
  updates: Partial<PackageOffer>,
): Promise<PhotographerProfile> {
  const packages = await getPhotographerPackages(userId)
  return replacePhotographerPackages(updatePackageById(packages, packageId, updates))
}

export async function setPhotographerPackageActive(
  userId: number,
  packageId: string,
  isActive: boolean,
): Promise<PhotographerProfile> {
  return updatePhotographerPackage(userId, packageId, { is_active: isActive })
}

export async function deletePhotographerPackage(
  userId: number,
  packageId: string,
): Promise<PhotographerProfile> {
  const packages = await getPhotographerPackages(userId)
  return replacePhotographerPackages(removePackageById(packages, packageId))
}
