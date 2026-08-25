/**
 * 将 AI 助手的完整文本按自然段拆分为多个独立气泡显示片段。
 *
 * 拆分规则（按优先级）：
 * 1. 统一 \r\n 为 \n，去除首尾空白。
 * 2. 空内容返回 []。
 * 3. 优先按一个或多个空行拆分自然段。
 * 4. 无空行但有单换行时按单换行拆分。
 * 5. 连续的 Markdown 列表项合并在同一个气泡中。
 * 6. 每段 trim()，过滤空段。
 * 7. 短段落（少于 12 汉字或 24 字符的非标题）与相邻段合并。
 * 8. 一条回复最多 8 个气泡，超过时尾部合并到第 8 个。
 * 9. 最终无有效分段但原文非空时，回退为 [text.trim()]。
 */

const MAX_SEGMENTS = 8
const SHORT_TEXT_LENGTH = 24
const SHORT_CHINESE_CHAR_COUNT = 12

/** 检测文本是否为 Markdown 列表项（行首为 -, *, •, 数字+. 或数字+)） */
function isListLine(line: string): boolean {
  return /^[-*•]\s/.test(line) || /^\d+[.)]\s/.test(line)
}

/** 检测文本是否为标题行 */
function isHeadingLine(line: string): boolean {
  return /^#{1,6}\s/.test(line)
}

/** 统计中文字符数 */
function chineseCharCount(text: string): number {
  return (text.match(/[\u4e00-\u9fff\u3400-\u4dbf]/g) || []).length
}

/** 判断非标题段落是否算「短段」 */
function isShortSegment(text: string): boolean {
  if (isHeadingLine(text.trim())) return false
  const trimmed = text.trim()
  // 列表项块（已合并过的）按自身结构保持独立，不视为短段
  if (isListLine(trimmed)) return false
  // 两个条件同时满足才算短段：总字符少且中文字符少
  return trimmed.length < SHORT_TEXT_LENGTH && chineseCharCount(trimmed) < SHORT_CHINESE_CHAR_COUNT
}

/** 合并连续的列表项 */
function mergeConsecutiveListItems(segments: string[]): string[] {
  const result: string[] = []
  let i = 0
  while (i < segments.length) {
    if (i + 1 < segments.length && isListLine(segments[i]) && isListLine(segments[i + 1])) {
      // Merge consecutive list items
      const merged = [segments[i]]
      while (i + 1 < segments.length && isListLine(segments[i + 1])) {
        i++
        merged.push(segments[i])
      }
      result.push(merged.join('\n'))
    } else {
      result.push(segments[i])
    }
    i++
  }
  return result
}

/** 合并短段落到相邻段 */
function mergeShortSegments(segments: string[]): string[] {
  if (segments.length <= 1) return segments

  const result: string[] = []
  let buffer = segments[0]

  for (let i = 1; i < segments.length; i++) {
    const current = segments[i]
    if (isShortSegment(current)) {
      // Merge short segment into buffer
      buffer = buffer + '\n' + current
    } else {
      result.push(buffer)
      buffer = current
    }
  }
  result.push(buffer)

  // Re-check: if first segment is still short after merging, merge with next
  if (result.length > 1 && isShortSegment(result[0])) {
    const first = result.shift()!
    result[0] = first + '\n' + result[0]
  }

  return result
}

/** 超过 8 个气泡时合并尾部 */
function capSegments(segments: string[]): string[] {
  if (segments.length <= MAX_SEGMENTS) return segments
  const head = segments.slice(0, MAX_SEGMENTS - 1)
  const tail = segments.slice(MAX_SEGMENTS - 1)
  return [...head, tail.join('\n\n')]
}

/**
 * 将 AI 助手回复文本按自然段拆分为气泡片段。
 * 纯函数，无副作用。
 */
export function segmentAssistantReply(text: string): string[] {
  // Step 1: Normalize line endings and trim
  const normalized = text.replace(/\r\n/g, '\n').trim()
  if (!normalized) return []

  let segments: string[]

  // Step 3: Split by one or more blank lines
  if (/\n\n/.test(normalized)) {
    segments = normalized.split(/\n\n+/).map((s) => s.trim()).filter(Boolean)
  }
  // Step 4: No blank lines but has single newlines
  else if (/\n/.test(normalized)) {
    segments = normalized.split(/\n/).map((s) => s.trim()).filter(Boolean)
  } else {
    segments = [normalized]
  }

  if (segments.length === 0) return []

  // Step 5: Merge consecutive list items
  segments = mergeConsecutiveListItems(segments)

  // Step 6: Trim and filter empty
  segments = segments.map((s) => s.trim()).filter(Boolean)

  if (segments.length === 0) return []

  // Step 7: Merge short segments
  segments = mergeShortSegments(segments)

  // Step 8: Cap at MAX_SEGMENTS
  segments = capSegments(segments)

  // Step 9: Fallback
  return segments
}
