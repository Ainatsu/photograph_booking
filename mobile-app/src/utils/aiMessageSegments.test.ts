import { describe, expect, it } from 'vitest'
import { segmentAssistantReply } from './aiMessageSegments'

describe('segmentAssistantReply', () => {
  it('splits by double newlines into natural paragraphs', () => {
    const input = '第一段内容。这里是一整段完整的描述信息。\n\n第二段内容。这里是第二段完整的详细说明。\n\n第三段内容。这里是第三段完整的补充信息。'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(3)
    expect(result[0]).toBe('第一段内容。这里是一整段完整的描述信息。')
    expect(result[1]).toBe('第二段内容。这里是第二段完整的详细说明。')
    expect(result[2]).toBe('第三段内容。这里是第三段完整的补充信息。')
  })

  it('handles single newlines when no blank lines exist', () => {
    const input = '第一行内容。这是第一行完整内容。\n第二行内容。这是第二行完整内容。\n第三行内容。这是第三行完整内容。'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(3)
    expect(result[0]).toBe('第一行内容。这是第一行完整内容。')
    expect(result[1]).toBe('第二行内容。这是第二行完整内容。')
    expect(result[2]).toBe('第三行内容。这是第三行完整内容。')
  })

  it('normalizes Windows line endings', () => {
    const input = '第一段内容。这是第一段完整描述。\r\n\r\n第二段内容。这是第二段完整描述。'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(2)
    expect(result[0]).toBe('第一段内容。这是第一段完整描述。')
    expect(result[1]).toBe('第二段内容。这是第二段完整描述。')
  })

  it('returns empty array for empty string', () => {
    expect(segmentAssistantReply('')).toEqual([])
  })

  it('returns empty array for whitespace-only string', () => {
    expect(segmentAssistantReply('   \n\n  ')).toEqual([])
  })

  it('keeps consecutive list items in one bubble', () => {
    const input = '- 列表项1\n- 列表项2\n- 列表项3'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(1)
    expect(result[0]).toContain('- 列表项1')
    expect(result[0]).toContain('- 列表项2')
    expect(result[0]).toContain('- 列表项3')
  })

  it('keeps numbered list items in one bubble', () => {
    const input = '1. 第一项\n2. 第二项\n3. 第三项'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(1)
    expect(result[0]).toContain('1. 第一项')
    expect(result[0]).toContain('2. 第二项')
    expect(result[0]).toContain('3. 第三项')
  })

  it('merges short leading segments with adjacent segment', () => {
    const input = '好的。\n\n接下来我详细介绍一下拍摄方案的具体内容。方案包括三个主要部分。'
    const result = segmentAssistantReply(input)
    // "好的。" is short (< 24 chars, < 12 Chinese chars), should merge with next
    expect(result).toHaveLength(1)
    expect(result[0]).toContain('好的')
    expect(result[0]).toContain('拍摄方案')
  })

  it('does not treat headings as short segments', () => {
    const input = '# 拍摄方案\n\n这是方案的具体内容。这是更完整的详细说明。'
    const result = segmentAssistantReply(input)
    // Heading should NOT be merged
    expect(result).toHaveLength(2)
    expect(result[0]).toBe('# 拍摄方案')
  })

  it('caps at 8 segments and merges tail into 8th', () => {
    const paragraphs = Array.from({ length: 12 }, (_, i) => `这是第 ${i + 1} 段内容的完整描述和详细说明。`)
    const input = paragraphs.join('\n\n')
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(8)
    // The last segment should contain all remaining content
    expect(result[7]).toContain('这是第 12 段内容的完整描述和详细说明。')
  })

  it('falls back to single segment for text without any line breaks', () => {
    const input = '这是一段没有换行的完整文本内容。'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(1)
    expect(result[0]).toBe(input)
  })

  it('preserves internal single newlines within a paragraph', () => {
    const input = '第一段第一行的完整内容描述\n第一段第二行的完整内容描述\n\n第二段完整内容的详细说明和具体描述。'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(2)
    expect(result[0]).toContain('第一段第一行的完整内容描述')
    expect(result[0]).toContain('第一段第二行的完整内容描述')
    expect(result[1]).toBe('第二段完整内容的详细说明和具体描述。')
  })

  it('handles list items after normal paragraphs', () => {
    const input = '以下是本次为您推荐的专业摄影师列表：\n\n- 摄影师A\n- 摄影师B\n- 摄影师C\n\n以上就是全部推荐内容感谢您的关注。'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(3)
    // List items should be merged
    expect(result[1]).toContain('- 摄影师A')
    expect(result[1]).toContain('- 摄影师B')
    expect(result[1]).toContain('- 摄影师C')
  })

  it('merges short trailing segments', () => {
    // "完毕。" is short, should merge with previous paragraph
    const input = '第一段内容的完整说明和详细描述。\n\n第二段内容的完整说明和详细描述。\n\n快来试试吧！'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(2)
    expect(result[1]).toContain('快来试试吧！')
  })

  it('handles single segment that is list items with blank lines before and after', () => {
    const input = '以下是总结的全部主要内容：\n\n- 优点一\n- 优点二\n- 优点三\n\n以上就是本次总结的全部主要内容和详细信息。'
    const result = segmentAssistantReply(input)
    expect(result).toHaveLength(3)
    expect(result[0]).toBe('以下是总结的全部主要内容：')
    expect(result[1]).toContain('- 优点一')
    expect(result[1]).toContain('- 优点二')
    expect(result[1]).toContain('- 优点三')
    expect(result[2]).toBe('以上就是本次总结的全部主要内容和详细信息。')
  })

  it('handles varied Chinese text with mixed formatting', () => {
    const input = '你好！我是小龟J你的AI摄影助手。\n\n今天来聊聊摄影构图技巧。\n\n首先：\n- 构图要简洁清晰\n- 光线要柔和自然\n- 主体要突出明确\n\n其次，多拍多练才能进步。\n\n加油练习吧！'
    const result = segmentAssistantReply(input)
    // "加油练习吧！" is short, should merge with previous
    expect(result.length).toBeLessThan(6)
    expect(result.some((s) => s.includes('加油练习'))).toBe(true)
  })
})
