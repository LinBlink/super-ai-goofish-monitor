import { onMounted, onUnmounted, ref } from 'vue'

/**
 * 同步响应媒体查询（移动端断点 ≤ 768px）。
 * SSR 安全，初次渲染返回 false 以避免 hydration mismatch。
 */
export function useMediaQuery(query: string) {
  const matches = ref(false)
  let mql: MediaQueryList | null = null
  let handler: ((e: MediaQueryListEvent) => void) | null = null

  onMounted(() => {
    if (typeof window === 'undefined') return
    mql = window.matchMedia(query)
    matches.value = mql.matches
    const update = (e: MediaQueryListEvent) => {
      matches.value = e.matches
    }
    handler = update
    if (mql.addEventListener) {
      mql.addEventListener('change', update)
    } else {
      // Safari < 14
      mql.addListener(update)
    }
  })

  onUnmounted(() => {
    if (!mql || !handler) return
    if (mql.removeEventListener) {
      mql.removeEventListener('change', handler)
    } else {
      mql.removeListener(handler)
    }
  })

  return matches
}

export function useIsMobile(breakpointPx = 768) {
  return useMediaQuery(`(max-width: ${breakpointPx - 1}px)`)
}