import { describe, expect, it } from 'vitest'
import type { PackageOffer } from '@/types/discovery'
import {
  filterPackages,
  isPackageActive,
  removePackageById,
  updatePackageById,
} from './package'

const packages: PackageOffer[] = [
  { id: 'active', name: '已上架方案', price: 699, is_active: true },
  { id: 'legacy', name: '旧方案', price: 899 },
  { id: 'inactive', name: '已下架方案', price: 499, is_active: false },
]

describe('package management helpers', () => {
  it('treats legacy packages without an explicit state as active', () => {
    expect(isPackageActive(packages[1])).toBe(true)
    expect(filterPackages(packages, 'active').map((item) => item.id)).toEqual(['active', 'legacy'])
    expect(filterPackages(packages, 'inactive').map((item) => item.id)).toEqual(['inactive'])
  })

  it('updates the matching package while preserving its id and compatibility fields', () => {
    const source = [{ ...packages[0], copyright_terms: '保留署名权' }]
    const next = updatePackageById(source, 'active', { name: '新版方案', id: 'overwritten' })

    expect(next[0]).toMatchObject({
      id: 'active',
      name: '新版方案',
      copyright_terms: '保留署名权',
    })
    expect(source[0].name).toBe('已上架方案')
  })

  it('removes only the requested package and rejects stale ids', () => {
    expect(removePackageById(packages, 'legacy').map((item) => item.id)).toEqual(['active', 'inactive'])
    expect(() => removePackageById(packages, 'missing')).toThrow('方案不存在')
    expect(() => updatePackageById(packages, 'missing', { price: 1 })).toThrow('方案不存在')
  })
})
