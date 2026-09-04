<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

interface TrendPoint {
  day: string
  avg_price: number | null
  median_price: number | null
  min_price?: number | null
  max_price?: number | null
}

type ChartMode = 'full' | 'min-only'

const props = withDefaults(
  defineProps<{
    points: TrendPoint[]
    mode?: ChartMode
    height?: number
  }>(),
  { mode: 'full', height: 240 },
)
const { t } = useI18n()
const isMinOnly = computed(() => props.mode === 'min-only')

const chartWidth = 720
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
    (point) => point.avg_price !== null && point.avg_price !== undefined,
  )
})

const valueRange = computed(() => {
  const values = isMinOnly.value
    ? validPoints.value.map((p) => p.min_price).filter((v): v is number => typeof v === 'number')
    : validPoints.value
        .flatMap((p) => [p.avg_price, p.median_price, p.min_price, p.max_price])
        .filter((v): v is number => typeof v === 'number')
  if (values.length === 0) return { min: 0, max: 1 }
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) return { min: min - 1, max: max + 1 }
  return { min, max }
})

function resolveX(index: number) {
  if (validPoints.value.length <= 1) return chartWidth / 2
  const usableWidth = chartWidth - paddingX * 2
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

const avgPath = computed(() =>
  isMinOnly.value ? '' : buildPath(validPoints.value.map((p) => p.avg_price)),
)
const medianPath = computed(() =>
  isMinOnly.value ? '' : buildPath(validPoints.value.map((p) => p.median_price)),
)
const minPath = computed(() =>
  buildPath(validPoints.value.map((p) => (typeof p.min_price === 'number' ? p.min_price : null))),
)
const areaPath = computed(() => {
  if (!avgPath.value || validPoints.value.length === 0) return ''
  const firstX = resolveX(0)
  const lastX = resolveX(validPoints.value.length - 1)
  return `${avgPath.value} L ${lastX} ${plotBottom} L ${firstX} ${plotBottom} Z`
})

function highValue(point: TrendPoint): number | null {
  if (isMinOnly.value) {
    return typeof point.min_price === 'number' ? point.min_price : null
  }
  if (typeof point.max_price === 'number') return point.max_price
  if (typeof point.avg_price === 'number') return point.avg_price
  return null
}

function lowValue(point: TrendPoint): number | null {
  if (isMinOnly.value) {
    return typeof point.min_price === 'number' ? point.min_price : null
  }
  if (typeof point.min_price === 'number') return point.min_price
  if (typeof point.avg_price === 'number') return point.avg_price
  return null
}

const highPoint = computed<{ index: number; point: TrendPoint } | null>(() => {
  let best: { index: number; point: TrendPoint } | null = null
  validPoints.value.forEach((point, index) => {
    const value = highValue(point)
    if (value === null) return
    const bestValue = best ? highValue(best.point) : null
    if (bestValue === null || value > bestValue) best = { index, point }
  })
  return best
})
const lowPoint = computed<{ index: number; point: TrendPoint } | null>(() => {
  let best: { index: number; point: TrendPoint } | null = null
  validPoints.value.forEach((point, index) => {
    const value = lowValue(point)
    if (value === null) return
    const bestValue = best ? lowValue(best.point) : null
    if (bestValue === null || value < bestValue) best = { index, point }
  })
  return best
})

const svgRef = ref<SVGSVGElement | null>(null)
const hoverIndex = ref<number | null>(null)
const hoverPoint = computed(() =>
  hoverIndex.value === null ? null : (validPoints.value[hoverIndex.value] ?? null),
)
const tipWidth = 220
const tipHeight = 140
function onMove(e: MouseEvent) {
  const svg = svgRef.value
  if (!svg || validPoints.value.length === 0) return
  const rect = svg.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * chartWidth
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
  return Math.max(4, Math.min(resolveX(hoverIndex.value) + 10, chartWidth - tipWidth - 4))
}
function fmt(v: number | null | undefined) {
  return typeof v === 'number' ? `¥${v}` : '—'
}
</script>

<template>
  <div class="app-surface-subtle p-4">
    <div class="mb-1 flex flex-col gap-3 text-xs uppercase tracking-[0.22em] text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>{{ isMinOnly ? t('results.chart.dipHeader') : t('results.chart.fullHeader') }}</span>
      <div class="flex items-center gap-3">
        <template v-if="isMinOnly">
          <span class="inline-flex items-center gap-1">
            <span class="h-2.5 w-2.5 rounded-full bg-emerald-600" />
            {{ t('results.chart.minPrice') }}
          </span>
        </template>
        <template v-else>
          <span class="inline-flex items-center gap-1">
            <span class="h-2.5 w-2.5 rounded-full bg-sky-600" />
            {{ t('results.chart.avgPrice') }}
          </span>
          <span class="inline-flex items-center gap-1">
            <span class="h-2.5 w-2.5 rounded-full bg-amber-500" />
            {{ t('results.chart.medianPrice') }}
          </span>
          <span class="inline-flex items-center gap-1">
            <span class="h-2.5 w-2.5 rounded-full bg-emerald-600" />
            {{ t('results.chart.minPrice') }}
          </span>
        </template>
      </div>
    </div>
    <p class="mb-3 text-[11px] normal-case tracking-normal text-slate-400">
      {{ t('results.chart.aiSourceNote') }}
    </p>

    <div v-if="validPoints.length === 0" class="rounded-2xl border border-dashed border-slate-200 bg-white/70 px-4 py-10 text-center text-sm text-slate-500">
      {{ t('results.chart.noTrend') }}
    </div>

    <div v-else>
      <svg
        ref="svgRef"
        :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
        :style="{ height: chartHeight + 'px' }"
        class="w-full"
        preserveAspectRatio="none"
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

        <path v-if="!isMinOnly" :d="areaPath" fill="url(#avg-area-fill)" />
        <path v-if="!isMinOnly" :d="avgPath" fill="none" stroke="#0284c7" stroke-width="4" stroke-linecap="round" />
        <path v-if="!isMinOnly" :d="medianPath" fill="none" stroke="#f59e0b" stroke-width="3" stroke-dasharray="8 6" stroke-linecap="round" />
        <path :d="minPath" fill="none" stroke="#059669" stroke-width="2.5" stroke-dasharray="2 5" stroke-linecap="round" />

        <g v-for="(point, index) in validPoints" :key="point.day">
          <template v-if="!isMinOnly">
            <circle :cx="resolveX(index)" :cy="resolveY(point.avg_price as number)" r="5" fill="#0284c7" />
            <circle :cx="resolveX(index)" :cy="resolveY(point.median_price as number)" r="4" fill="#f59e0b" />
          </template>
          <circle
            v-if="typeof point.min_price === 'number'"
            :cx="resolveX(index)"
            :cy="resolveY(point.min_price)"
            r="3.5"
            fill="#059669"
          />
          <text
            :x="resolveX(index)"
            :y="chartHeight - 6"
            text-anchor="middle"
            fill="#64748b"
            font-size="13"
          >
            {{ point.day.slice(5) }}
          </text>
        </g>

        <g v-if="highPoint">
          <circle
            :cx="resolveX(highPoint.index)"
            :cy="resolveY(highValue(highPoint.point) as number)"
            r="7"
            fill="none"
            stroke="#e11d48"
            stroke-width="2.5"
          />
          <text
            :x="labelX(highPoint.index)"
            :y="resolveY(highValue(highPoint.point) as number) - 14"
            :text-anchor="labelAnchor(highPoint.index)"
            fill="#e11d48"
            font-size="13"
            font-weight="600"
          >
            {{ t('results.chart.highMark', { price: highValue(highPoint.point) }) }}
          </text>
        </g>

        <g v-if="lowPoint && lowPoint.index !== highPoint?.index">
          <circle
            :cx="resolveX(lowPoint.index)"
            :cy="resolveY(lowValue(lowPoint.point) as number)"
            r="7"
            fill="none"
            stroke="#16a34a"
            stroke-width="2.5"
          />
          <text
            :x="labelX(lowPoint.index)"
            :y="resolveY(lowValue(lowPoint.point) as number) + 20"
            :text-anchor="labelAnchor(lowPoint.index)"
            fill="#16a34a"
            font-size="13"
            font-weight="600"
          >
            {{ t('results.chart.lowMark', { price: lowValue(lowPoint.point) }) }}
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
            <rect :width="tipWidth" :height="tipHeight" rx="8" fill="rgba(15,23,42,0.94)" />
            <text x="12" y="22" fill="#e2e8f0" font-size="14" font-weight="700">{{ hoverPoint.day }}</text>
            <text x="12" y="46" fill="#7dd3fc" font-size="13">均 {{ fmt(hoverPoint.avg_price) }}</text>
            <text x="12" y="68" fill="#fcd34d" font-size="13">中 {{ fmt(hoverPoint.median_price) }}</text>
            <text x="12" y="90" fill="#6ee7b7" font-size="13">低 {{ fmt(hoverPoint.min_price) }}</text>
            <text x="12" y="112" fill="#fca5a5" font-size="13">高 {{ fmt(hoverPoint.max_price) }}</text>
          </g>
        </g>
      </svg>
    </div>
  </div>
</template>
