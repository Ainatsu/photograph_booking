import { describe, expect, it } from 'vitest'
import { getPackagePreviewUrl, getWorkMediaUrls, getWorkPreviewUrl, resolveMediaUrl } from './media'

describe('media utilities', () => {
  it('keeps absolute and browser-owned URLs unchanged', () => {
    expect(resolveMediaUrl('https://images.example/work.jpg')).toBe('https://images.example/work.jpg')
    expect(resolveMediaUrl('data:image/png;base64,abc')).toBe('data:image/png;base64,abc')
    expect(resolveMediaUrl('blob:http://localhost/item')).toBe('blob:http://localhost/item')
  })

  it('normalizes relative backend media paths', () => {
    expect(resolveMediaUrl('/static/work.jpg')).toBe('/static/work.jpg')
    expect(resolveMediaUrl('static/work.jpg')).toBe('/static/work.jpg')
  })

  it('prefers lightweight work previews and keeps full media order', () => {
    const work = {
      id: 'work-1',
      url: '/static/original.jpg',
      images: ['/static/one.jpg', '/static/two.jpg'],
      thumbnail_url: '/static/thumb.jpg',
    }
    expect(getWorkPreviewUrl(work)).toBe('/static/thumb.jpg')
    expect(getWorkMediaUrls(work)).toEqual(['/static/one.jpg', '/static/two.jpg'])
  })

  it('prefers package thumbnails before original samples', () => {
    expect(
      getPackagePreviewUrl({
        id: 'package-1',
        price: 699,
        sample_thumbnails: ['/static/thumb.jpg'],
        samples: ['/static/original.jpg'],
      }),
    ).toBe('/static/thumb.jpg')
  })
})
