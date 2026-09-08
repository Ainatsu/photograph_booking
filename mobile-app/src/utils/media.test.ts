import { describe, expect, it } from 'vitest'
import { getInspirationPreviewUrl, getPackagePreviewUrl, getWorkMediaUrls, getWorkPreviewUrl, resolveMediaUrl } from './media'

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

  it('uses inspiration cover_url first and falls back to image blocks', () => {
    expect(getInspirationPreviewUrl({ cover_url: '/static/cover.jpg', content: [] })).toBe('/static/cover.jpg')
    expect(
      getInspirationPreviewUrl({
        cover_url: null,
        content: [
          { type: 'paragraph', text: '想法' },
          { type: 'image', url: '/static/original.jpg', thumb_url: '/static/thumb.jpg' },
        ],
      }),
    ).toBe('/static/thumb.jpg')
    expect(
      getInspirationPreviewUrl({
        cover_url: null,
        content: [{ type: 'image', url: '/static/original.jpg' }],
      }),
    ).toBe('/static/original.jpg')
    expect(getInspirationPreviewUrl({ cover_url: null, content: [{ type: 'paragraph', text: '只有文字' }] })).toBe('')
  })
})
