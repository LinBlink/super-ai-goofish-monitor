<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

interface TrendPoint {
  day: string
  avg_price: number | null
  median_price: number | null
  min_price?: number | null
  max_price?: number | null
}

type ChartMode = 'full' | 'min-only'
type TooltipSize = 'default' | 'large'

const props = withDefaults(
  defineProps<{
    points: TrendPoint[]
    mode?: ChartMode
    height?: number
    tooltipSize?: TooltipSize
  }>(),
  { mode: 'full', height: 240, tooltipSize: 'default' },
)
const { t } = useI18n()
const isMinOnly = computed(() => props.mode === 'min-only')
const showAvg = ref(false)
const showMedian = ref(false)
const showMin = ref(true)
const showMinTrend = ref(true)

const chartContainerRef = ref<HTMLDivElement | null>(null)
const chartWidth = ref(720)
let resizeObserver: ResizeObserver | null = null

function observeChartContainer() {
  resizeObserver?.disconnect()
  const container = chartContainerRef.value
  if (!container || typeof ResizeObserver === 'undefined') return

  resizeObserver = new ResizeObserver(([entry]) => {
    if (entry && entry.contentRect.width > 0) {
      chartWidth.value = Math.round(entry.contentRect.width)
    }
  })
  resizeObserver.observe(container)
}

const chartHeight = computed(() => props.height)
const paddingX = 24
const plotTop = 46
const axisLabelHeight = 20
const extremeLabelGap = 34
const plotBottom = computed(() => chartHeight.value - axisLabelHeight - extremeLabelGap)

const validPoints = computed(() => {
  if (isMinOnly.value) {
    return props.points.filter((point) => typeof point.min_price === 'number')
  }
  return props.points.filter(
    (point) => [point.avg_price, point.median_price, point.min_price].some(
      (value) => typeof value === 'number',
    ),
  )
})

watch(
  () => validPoints.value.length,
  async () => {
    await nextTick()
    observeChartContainer()
  },
  { immediate: true, flush: 'post' },
)

onBeforeUnmount(() => resizeObserver?.disconnect())

const valueRange = computed(() => {
  const values = validPoints.value
    .flatMap((point) => [
      ...(!isMinOnly.value && showAvg.value ? [point.avg_price] : []),
      ...(!isMinOnly.value && showMedian.value ? [point.median_price] : []),
      ...(showMin.value || showMinTrend.value ? [point.min_price] : []),
    ])
    .filter((value): value is number => typeof value === 'number')
  if (values.length === 0) return { min: 0, max: 1 }
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) return { min: min - 1, max: max + 1 }
  return { min, max }
})

const dateTickIndices = computed(() => {
  const pointCount = validPoints.value.length
  if (pointCount === 0) return new Set<number>()

  // Reserve enough horizontal room for an MM-DD label and distribute the
  // selected dates across the complete range, always retaining both ends.
  const maxTickCount = Math.max(2, Math.floor((chartWidth.value - paddingX * 2) / 64))
  const tickCount = Math.min(pointCount, maxTickCount)
  if (tickCount === 1) return new Set([0])

  return new Set(
    Array.from({ length: tickCount }, (_, index) =>
      Math.round((index * (pointCount - 1)) / (tickCount - 1)),
    ),
  )
})

function resolveX(index: number) {
  if (validPoints.value.length <= 1) return chartWidth.value / 2
  const usableWidth = chartWidth.value - paddingX * 2
  return paddingX + (usableWidth / (validPoints.value.length - 1)) * index
}
function resolveY(value: number) {
  const usableHeight = plotBottom.value - plotTop
  const ratio = (value - valueRange.value.min) / (valueRange.value.max - valueRange.value.min)
  return plotBottom.value - ratio * usableHeight
}
function labelAnchor(index: number) {
  if (validPoints.value.length <= 1) return 'middle'
  if (index === 0) return 'start'
  if (index === validPoints.value.length - 1) return 'end'
  return 'middle'
}
function labelX(index: number) {
  const anchor = labelAnchor(index)
  const x = resolveX(index)
  if (anchor === 'start') return x + 6
  if (anchor === 'end') return x - 6
  return x
}
function buildPath(values: Array<number | null>) {
  return values
    .map((value, index) => {
      if (value === null || value === undefined) return null
      const prefix = index === 0 ? 'M' : 'L'
      return `${prefix} ${resolveX(index)} ${resolveY(value)}`
    })
    .filter(Boolean)
    .join(' ')
}

function buildSmoothPath(values: Array<number | null>) {
  const coordinates = values
    .map((value, index) =>
      typeof value === 'number'
        ? { x: resolveX(index), y: resolveY(value) }
        : null,
    )
    .filter((point): point is { x: number; y: number } => point !== null)
  if (coordinates.length === 0) return ''
  const first = coordinates[0]!
  if (coordinates.length === 1) return `M ${first.x} ${first.y}`

  let path = `M ${first.x} ${first.y}`
  for (let index = 0; index < coordinates.length - 1; index += 1) {
    const previous = coordinates[Math.max(0, index - 1)]!
    const current = coordinates[index]!
    const next = coordinates[index + 1]!
    const following = coordinates[Math.min(coordinates.length - 1, index + 2)]!
    const control1X = current.x + (next.x - previous.x) / 6
    const control1Y = current.y + (next.y - previous.y) / 6
    const control2X = next.x - (following.x - current.x) / 6
    const control2Y = next.y - (following.y - current.y) / 6
    path += ` C ${control1X} ${control1Y}, ${control2X} ${control2Y}, ${next.x} ${next.y}`
  }
  return path
}

const avgPath = computed(() =>
  isMinOnly.value ? '' : buildPath(validPoints.value.map((p) => p.avg_price)),
)
const medianPath = computed(() =>
  isMinOnly.value ? '' : buildPath(validPoints.value.map((p) => p.median_price)),
)
const minPath = computed(() =>
  buildPath(validPoints.value.map((p) => (typeof p.min_price === 'number' ? p.min_price : null))),
)
const minTrendValues = computed(() => {
  const values = validPoints.value.map((point) => point.min_price)
  return values.map((value, index) => {
    if (typeof value !== 'number') return null
    const windowValues = values
      .slice(Math.max(0, index - 1), Math.min(values.length, index + 2))
      .filter((candidate): candidate is number => typeof candidate === 'number')
    return windowValues.reduce((sum, candidate) => sum + candidate, 0) / windowValues.length
  })
})
const minTrendPath = computed(() => buildSmoothPath(minTrendValues.value))
const areaPath = computed(() => {
  if (!avgPath.value || validPoints.value.length === 0) return ''
  const firstX = resolveX(0)
  const lastX = resolveX(validPoints.value.length - 1)
  return `${avgPath.value} L ${lastX} ${plotBottom} L ${firstX} ${plotBottom} Z`
})

function minCurveValue(point: TrendPoint): number | null {
  return typeof point.min_price === 'number' ? point.min_price : null
}

const highPoint = computed<{ index: number; point: TrendPoint } | null>(() => {
  let best: { index: number; point: TrendPoint } | null = null
  validPoints.value.forEach((point, index) => {
    const value = minCurveValue(point)
    if (value === null) return
    const bestValue = best ? minCurveValue(best.point) : null
    if (bestValue === null || value > bestValue) best = { index, point }
  })
  return best
})
const lowPoint = computed<{ index: number; point: TrendPoint } | null>(() => {
  let best: { index: number; point: TrendPoint } | null = null
  validPoints.value.forEach((point, index) => {
    const value = minCurveValue(point)
    if (value === null) return
    const bestValue = best ? minCurveValue(best.point) : null
    if (bestValue === null || value < bestValue) best = { index, point }
  })
  return best
})

const svgRef = ref<SVGSVGElement | null>(null)
const hoverIndex = ref<number | null>(null)
const hoverPoint = computed(() =>
  hoverIndex.value === null ? null : (validPoints.value[hoverIndex.value] ?? null),
)
const isLargeTooltip = computed(() => props.tooltipSize === 'large')
const tipWidth = computed(() => (isLargeTooltip.value ? 280 : 220))
const tipHeight = computed(() => (isLargeTooltip.value ? 164 : 140))
const tipTitleSize = computed(() => (isLargeTooltip.value ? 17 : 14))
const tipTextSize = computed(() => (isLargeTooltip.value ? 16 : 13))
const tipLineY = computed(() =>
  isLargeTooltip.value ? [54, 80, 106, 132] : [46, 68, 90, 112],
)
function onMove(e: MouseEvent) {
  const svg = svgRef.value
  if (!svg || validPoints.value.length === 0) return
  const rect = svg.getBoundingClientRect()
  const vbAspect = chartWidth.value / chartHeight.value
  const svgAspect = rect.width / rect.height
  let renderedWidth: number
  let offsetX: number
  if (svgAspect > vbAspect) {
    const renderedHeight = rect.height
    renderedWidth = renderedHeight * vbAspect
    offsetX = (rect.width - renderedWidth) / 2
  } else {
    renderedWidth = rect.width
    offsetX = 0
  }
  const x = ((e.clientX - rect.left - offsetX) / renderedWidth) * chartWidth.value
  let best = 0
  let bestDist = Infinity
  validPoints.value.forEach((_, i) => {
    const d = Math.abs(resolveX(i) - x)
    if (d < bestDist) {
      bestDist = d
      best = i
    }
  })
  hoverIndex.value = best
}
function onLeave() {
  hoverIndex.value = null
}
function tipX() {
  if (hoverIndex.value === null) return 4
  return Math.max(4, Math.min(resolveX(hoverIndex.value) + 10, chartWidth.value - tipWidth.value - 4))
}
function fmt(v: number | null | undefined) {
  return typeof v === 'number' ? `¥${v}` : '—'
}
</script>

<template>
  <div class="app-surface-subtle p-4">
    <div class="mb-1 flex flex-col gap-3 text-xs uppercase tracking-[0.22em] text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>{{ isMinOnly ? t('results.chart.dipHeader') : t('results.chart.fullHeader') }}</span>
      <div class="flex flex-wrap items-center gap-2">
        <template v-if="isMinOnly">
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-1.5 py-1 transition-opacity"
            :class="showMin ? 'opacity-100' : 'opacity-35 line-through'"
            :aria-pressed="showMin"
            @click.stop="showMin = !showMin"
          >
            <span class="h-2.5 w-2.5 rounded-full bg-emerald-600" />
            {{ t('results.chart.minPrice') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-1.5 py-1 transition-opacity"
            :class="showMinTrend ? 'opacity-100' : 'opacity-35 line-through'"
            :aria-pressed="showMinTrend"
            @click.stop="showMinTrend = !showMinTrend"
          >
            <span class="h-1 w-4 rounded-full bg-violet-600" />
            {{ t('results.chart.minTrend') }}
          </button>
        </template>
        <template v-else>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-1.5 py-1 transition-opacity"
            :class="showAvg ? 'opacity-100' : 'opacity-35 line-through'"
            :aria-pressed="showAvg"
            @click.stop="showAvg = !showAvg"
          >
            <span class="h-2.5 w-2.5 rounded-full bg-sky-600" />
            {{ t('results.chart.avgPrice') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-1.5 py-1 transition-opacity"
            :class="showMedian ? 'opacity-100' : 'opacity-35 line-through'"
            :aria-pressed="showMedian"
            @click.stop="showMedian = !showMedian"
          >
            <span class="h-2.5 w-2.5 rounded-full bg-amber-500" />
            {{ t('results.chart.medianPrice') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-1.5 py-1 transition-opacity"
            :class="showMin ? 'opacity-100' : 'opacity-35 line-through'"
            :aria-pressed="showMin"
            @click.stop="showMin = !showMin"
          >
            <span class="h-2.5 w-2.5 rounded-full bg-emerald-600" />
            {{ t('results.chart.minPrice') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-1.5 py-1 transition-opacity"
            :class="showMinTrend ? 'opacity-100' : 'opacity-35 line-through'"
            :aria-pressed="showMinTrend"
            @click.stop="showMinTrend = !showMinTrend"
          >
            <span class="h-1 w-4 rounded-full bg-violet-600" />
            {{ t('results.chart.minTrend') }}
          </button>
        </template>
      </div>
    </div>
    <p class="mb-3 text-[11px] normal-case tracking-normal text-slate-400">
      {{ t('results.chart.aiSourceNote') }}
    </p>

    <div v-if="validPoints.length === 0" class="rounded-2xl border border-dashed border-slate-200 bg-white/70 px-4 py-10 text-center text-sm text-slate-500">
      {{ t('results.chart.noTrend') }}
    </div>

    <div v-else ref="chartContainerRef" class="w-full">
      <svg
        ref="svgRef"
        :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
        :style="{ height: chartHeight + 'px' }"
        class="w-full"
        role="img"
        :aria-label="t('results.chart.noTrend')"
        @mousemove="onMove"
        @mouseleave="onLeave"
      >
        <defs>
          <linearGradient id="avg-area-fill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#0284c7" stop-opacity="0.24" />
            <stop offset="100%" stop-color="#0284c7" stop-opacity="0" />
          </linearGradient>
        </defs>

        <g>
          <line
            v-for="index in 4"
            :key="index"
            :x1="paddingX"
            :x2="chartWidth - paddingX"
            :y1="plotTop + ((plotBottom - plotTop) / 3) * (index - 1)"
            :y2="plotTop + ((plotBottom - plotTop) / 3) * (index - 1)"
            stroke="#cbd5e1"
            stroke-dasharray="4 6"
          />
        </g>

        <path v-if="!isMinOnly && showAvg" :d="areaPath" fill="url(#avg-area-fill)" />
        <path v-if="!isMinOnly && showAvg" :d="avgPath" fill="none" stroke="#0284c7" stroke-width="4" stroke-linecap="round" />
        <path v-if="!isMinOnly && showMedian" :d="medianPath" fill="none" stroke="#f59e0b" stroke-width="3" stroke-dasharray="8 6" stroke-linecap="round" />
        <path v-if="showMin" :d="minPath" fill="none" stroke="#059669" stroke-width="2.5" stroke-dasharray="2 5" stroke-linecap="round" />
        <path
          v-if="showMinTrend"
          :d="minTrendPath"
          fill="none"
          stroke="#7c3aed"
          stroke-width="4"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity="0.9"
        />

        <g v-for="(point, index) in validPoints" :key="point.day">
          <template v-if="!isMinOnly">
            <circle v-if="showAvg && typeof point.avg_price === 'number'" :cx="resolveX(index)" :cy="resolveY(point.avg_price)" r="5" fill="#0284c7" />
            <circle v-if="showMedian && typeof point.median_price === 'number'" :cx="resolveX(index)" :cy="resolveY(point.median_price)" r="4" fill="#f59e0b" />
          </template>
          <circle
            v-if="showMin && typeof point.min_price === 'number'"
            :cx="resolveX(index)"
            :cy="resolveY(point.min_price)"
            r="3.5"
            fill="#059669"
          />
          <text
            v-if="dateTickIndices.has(index)"
            :x="resolveX(index)"
            :y="chartHeight - 6"
            text-anchor="middle"
            fill="#64748b"
            font-size="13"
          >
            {{ point.day.slice(5) }}
          </text>
        </g>

        <g v-if="highPoint && (showMin || showMinTrend)">
          <circle
            :cx="resolveX(highPoint.index)"
            :cy="resolveY(minCurveValue(highPoint.point) as number)"
            r="7"
            fill="none"
            stroke="#e11d48"
            stroke-width="2.5"
          />
          <text
            :x="labelX(highPoint.index)"
            :y="resolveY(minCurveValue(highPoint.point) as number) - 14"
            :text-anchor="labelAnchor(highPoint.index)"
            fill="#e11d48"
            font-size="13"
            font-weight="600"
          >
            {{ t('results.chart.highMark', { price: minCurveValue(highPoint.point) }) }}
          </text>
        </g>

        <g v-if="lowPoint && (showMin || showMinTrend) && lowPoint.index !== highPoint?.index">
          <circle
            :cx="resolveX(lowPoint.index)"
            :cy="resolveY(minCurveValue(lowPoint.point) as number)"
            r="7"
            fill="none"
            stroke="#16a34a"
            stroke-width="2.5"
          />
          <text
            :x="labelX(lowPoint.index)"
            :y="resolveY(minCurveValue(lowPoint.point) as number) + 20"
            :text-anchor="labelAnchor(lowPoint.index)"
            fill="#16a34a"
            font-size="13"
            font-weight="600"
          >
            {{ t('results.chart.lowMark', { price: minCurveValue(lowPoint.point) }) }}
          </text>
        </g>

        <g v-if="hoverIndex !== null && hoverPoint">
          <line
            :x1="resolveX(hoverIndex)"
            :x2="resolveX(hoverIndex)"
            :y1="plotTop"
            :y2="plotBottom"
            stroke="#94a3b8"
            stroke-width="1"
            stroke-dasharray="3 3"
          />
          <g :transform="`translate(${tipX()}, ${plotTop})`">
            <rect :width="tipWidth" :height="tipHeight" rx="10" fill="rgba(15,23,42,0.94)" />
            <text x="14" y="26" fill="#e2e8f0" :font-size="tipTitleSize" font-weight="700">{{ hoverPoint.day }}</text>
            <text v-if="!isMinOnly && showAvg" x="14" :y="tipLineY[0]" fill="#7dd3fc" :font-size="tipTextSize">均 {{ fmt(hoverPoint.avg_price) }}</text>
            <text v-if="!isMinOnly && showMedian" x="14" :y="tipLineY[1]" fill="#fcd34d" :font-size="tipTextSize">中 {{ fmt(hoverPoint.median_price) }}</text>
            <text v-if="showMin || showMinTrend" x="14" :y="tipLineY[2]" fill="#6ee7b7" :font-size="tipTextSize">低 {{ fmt(hoverPoint.min_price) }}</text>
            <text x="14" :y="tipLineY[3]" fill="#fca5a5" :font-size="tipTextSize">高 {{ fmt(hoverPoint.max_price) }}</text>
          </g>
        </g>
      </svg>
    </div>
  </div>
</template>
