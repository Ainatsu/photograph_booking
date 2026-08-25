export interface AssistantRevealStep {
  visibleCount: number
  delayMs: number
}

const DEFAULT_MAX_TOTAL_DELAY_MS = 1600

function segmentDelayMs(segment: string): number {
  return Math.min(Math.max(180 + segment.length * 2, 180), 360)
}

/**
 * Build an ordered reveal schedule for assistant bubbles.
 *
 * Delays are cumulative so callbacks cannot race out of order. Once the total
 * duration reaches the cap, the final step reveals every remaining segment.
 */
export function buildAssistantRevealSchedule(
  segments: string[],
  maxTotalDelayMs = DEFAULT_MAX_TOTAL_DELAY_MS,
): AssistantRevealStep[] {
  if (segments.length <= 1) return []

  const steps: AssistantRevealStep[] = []
  let accumulatedDelay = 0

  for (let index = 1; index < segments.length; index++) {
    accumulatedDelay = Math.min(
      maxTotalDelayMs,
      accumulatedDelay + segmentDelayMs(segments[index]),
    )
    const reachedCap = accumulatedDelay >= maxTotalDelayMs
    steps.push({
      visibleCount: reachedCap ? segments.length : index + 1,
      delayMs: accumulatedDelay,
    })
    if (reachedCap) break
  }

  return steps
}
