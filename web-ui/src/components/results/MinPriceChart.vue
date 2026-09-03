<script setup lang="ts">
import { computed } from 'vue'

interface MinPriceChartPoint {
  day: string
  min_price: number | null
}

interface InternalPoint {
  day: string
  min_price: number
  idx: number
}

interface ExtremePoint {
  idx: number
  value: number
  day: string
}

interface Props {
  points: MinPriceChartPoint[]
  width?: number
  height?: number
  markExtremes?: boolean
  showAxis?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: 240,
  height: 64,
  markExtremes: true,
  showAxis: true,
})

const paddingX = 6
const paddingY = 8

const validPoints = computed<InternalPoint[]>(() => {
  const out: InternalPoint[] = []
  props.points.forEach((p, i) => {
    if (typeof p.min_price === 'number') {
      out.push({ day: p.day, min_price: p.min_price, idx: i })
    }
  })
  return out
})

const yRange = computed(() => {
  const vs = validPoints.value
  if (vs.length === 0) return { min: 0, max: 1 }
  const min = Math.min(...vs.map((p) => p.min_price))
  const max = Math.max(...vs.map((p) => p.min_price))
  if (min === max) return { min: min - 1, max: max + 1 }
  return { min, max }
})

function resolveX(index: number): number {
  const n = validPoints.value.length
  if (n <= 1) return props.width / 2
  const usable = props.width - paddingX * 2
  return paddingX + (usable / (n - 1)) * index
}

function resolveY(value: number): number {
  const usable = props.height - paddingY * 2 - (props.showAxis ? 10 : 0)
  const { min, max } = yRange.value
  const ratio = (value - min) / (max - min)
  return paddingY + (1 - ratio) * usable
}

const pathD = computed(() => {
  return validPoints.value
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${resolveX(i)} ${resolveY(p.min_price)}`)
    .join(' ')
})

const highPoint = computed<ExtremePoint | null>(() => {
  const vs = validPoints.value
  if (vs.length === 0) return null
  let best: InternalPoint | undefined = vs[0]
  for (let i = 1; i < vs.length; i += 1) {
    const cur = vs[i]
    if (cur && (!best || cur.min_price > best.min_price)) best = cur
  }
  if (!best) return null
  return { idx: best.idx, value: best.min_price, day: best.day }
})

const lowPoint = computed<ExtremePoint | null>(() => {
  const vs = validPoints.value
  if (vs.length === 0) return null
  let best: InternalPoint | undefined = vs[0]
  for (let i = 1; i < vs.length; i += 1) {
    const cur = vs[i]
    if (cur && (!best || cur.min_price < best.min_price)) best = cur
  }
  if (!best) return null
  return { idx: best.idx, value: best.min_price, day: best.day }
})

const axisLabels = computed<Array<{ idx: number; text: string }>>(() => {
  const vs = validPoints.value
  if (vs.length === 0) return []
  if (vs.length <= 6) return vs.map((p) => ({ idx: p.idx, text: p.day.slice(5) }))
  const midIdx = Math.floor(vs.length / 2)
  const first = vs[0]
  const mid = vs[midIdx]
  const last = vs[vs.length - 1]
  const picked: InternalPoint[] = []
  if (first) picked.push(first)
  if (mid) picked.push(mid)
  if (last) picked.push(last)
  return picked.map((p) => ({ idx: p.idx, text: p.day.slice(5) }))
})
</script>

<template>
  <div class="w-full">
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      class="block w-full"
      preserveAspectRatio="none"
      role="img"
    >
      <defs>
        <linearGradient id="mpc-fill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#ff4f24" stop-opacity="0.18" />
          <stop offset="100%" stop-color="#ff4f24" stop-opacity="0" />
        </linearGradient>
      </defs>

      <path
        v-if="pathD"
        :d="`${pathD} L ${resolveX(validPoints.length - 1)} ${height - (showAxis ? 12 : paddingY)} L ${resolveX(0)} ${height - (showAxis ? 12 : paddingY)} Z`"
        fill="url(#mpc-fill)"
      />
      <path
        v-if="pathD"
        :d="pathD"
        fill="none"
        stroke="#ff4f24"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />

      <template v-if="markExtremes">
        <g v-if="highPoint">
          <circle
            :cx="resolveX(highPoint.idx)"
            :cy="resolveY(highPoint.value)"
            r="2.5"
            fill="#ffe60f"
            stroke="#1f1f1f"
            stroke-width="0.8"
          />
        </g>
        <g v-if="lowPoint && lowPoint.idx !== highPoint?.idx">
          <circle
            :cx="resolveX(lowPoint.idx)"
            :cy="resolveY(lowPoint.value)"
            r="2.5"
            fill="#14c38e"
            stroke="#1f1f1f"
            stroke-width="0.8"
          />
        </g>
      </template>

      <g v-if="showAxis">
        <text
          v-for="label in axisLabels"
          :key="label.idx"
          :x="resolveX(label.idx)"
          :y="height - 2"
          text-anchor="middle"
          fill="#999"
          font-size="9"
        >
          {{ label.text }}
        </text>
      </g>
    </svg>
  </div>
</template>




