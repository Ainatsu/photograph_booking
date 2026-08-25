import type { PackageOffer } from '@/types/discovery'

export type PackageStatusFilter = 'all' | 'active' | 'inactive'

export const packageStatusOptions: Array<{ value: PackageStatusFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '已上架' },
  { value: 'inactive', label: '已下架' },
]

export function isPackageActive(pkg: Pick<PackageOffer, 'is_active'>): boolean {
  return pkg.is_active !== false
}

export function filterPackages(
  packages: PackageOffer[],
  status: PackageStatusFilter,
): PackageOffer[] {
  if (status === 'all') return packages
  const active = status === 'active'
  return packages.filter((pkg) => isPackageActive(pkg) === active)
}

export function updatePackageById(
  packages: PackageOffer[],
  packageId: string,
  updates: Partial<PackageOffer>,
): PackageOffer[] {
  let found = false
  const next = packages.map((pkg) => {
    if (String(pkg.id) !== String(packageId)) return pkg
    found = true
    return { ...pkg, ...updates, id: pkg.id }
  })
  if (!found) throw new Error('方案不存在或已被删除，请刷新后重试。')
  return next
}

export function removePackageById(packages: PackageOffer[], packageId: string): PackageOffer[] {
  const next = packages.filter((pkg) => String(pkg.id) !== String(packageId))
  if (next.length === packages.length) throw new Error('方案不存在或已被删除，请刷新后重试。')
  return next
}
