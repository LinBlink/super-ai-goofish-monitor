<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { TrendingDown, MapPin, ExternalLink, Tag } from 'lucide-vue-next'
import PriceTrendChart from './PriceTrendChart.vue'
import type { DashboardDipTrendPoint } from '@/types/dashboard.d.ts'

export interface DipProductCardData {
  task_id: number | null
  task_name: string
  keyword: string
  latest_min_price: number
  decline_percent: number
  avg_daily_decline: number
  decline_days: number
  highest_min_price: number
  trend_points: number
  trend: DashboardDipTrendPoint[]
  lowest_item: {
    item_id: string
    title: string
    price: number
    price_display: string
    link: string
    region: string
    snapshot_time: string
  } | null
}

interface Props {
  data: DipProductCardData
}

const props = defineProps<Props>()
const { t } = useI18n()

const trendPoints = computed(() =>
  props.data.trend.map((p) => {
    const min = typeof p.min_price === 'number' ? p.min_price : null
    const avg = typeof p.avg_price === 'number'
      ? p.avg_price
      : (min !== null ? min : null)
    const max = typeof p.max_price === 'number'
      ? p.max_price
      : (avg !== null ? avg : null)
    return {
      day: p.day,
      avg_price: avg,
      median_price: null,
      min_price: min,
      max_price: max,
    }
  }),
)

const declineLabel = computed(() => {
  const v = Math.abs(props.data.decline_percent)
  return v.toFixed(1)
})

function openLowestItem() {
  const link = props.data.lowest_item?.link
  if (link) window.open(link, '_blank', 'noopener,noreferrer')
}

function formatRelativeDay(days: number) {
  if (days <= 0) return ''
  if (days === 1) return `1 ${t('dashboard.deals.day')}`
  return `${days} ${t('dashboard.deals.days')}`
}
</script>

<template>
  <article
    class="xy-card group relative flex flex-col overflow-hidden transition-shadow hover:shadow-xy-hover"
  >
    <!-- 头部：标�?+ 跌幅 -->
    <header class="flex items-start justify-between gap-2 p-3 pb-2">
      <div class="min-w-0 flex-1">
        <h3
          class="line-clamp-2 text-[15px] font-bold leading-tight text-foreground"
          :title="data.task_name"
        >
          {{ data.task_name }}
        </h3>
        <p class="mt-0.5 flex items-center gap-1 text-[11px] text-slate-500">
          <Tag class="h-3 w-3 shrink-0" />
          <span class="truncate">{{ data.keyword }}</span>
        </p>
      </div>
      <div
        class="flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-bold"
        style="background-color: hsl(var(--price) / 0.1); color: hsl(var(--price))"
      >
        <TrendingDown class="h-3 w-3" />
        <span class="tabular">-{{ declineLabel }}%</span>
      </div>
    </header>

    <!-- 主体：左价格 / 右图�?-->
    <div class="grid grid-cols-[auto_1fr] items-end gap-3 px-3 pb-3">
      <div class="leading-none">
        <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {{ t('dashboard.deals.latestMinPrice') }}
        </p>
        <p class="mt-0.5 flex items-baseline gap-0.5">
          <span class="xy-price-sign">¥</span>
          <span class="xy-price text-[26px] tabular">{{ data.latest_min_price }}</span>
        </p>
        <p class="mt-1 text-[10px] text-slate-400 tabular">
          {{ t('dashboard.deals.highestLabel') }} ¥{{ data.highest_min_price }}
        </p>
      </div>
      <PriceTrendChart
        v-if="trendPoints.length > 0"
        :points="trendPoints"
        :height="200"
      />
    </div>

    <!-- 底部：最便宜单品 + 日均 -->
    <div
      v-if="data.lowest_item"
      class="flex items-center justify-between gap-2 border-t border-border bg-muted px-3 py-2 active:bg-muted/80"
      role="button"
      tabindex="0"
      @click="openLowestItem"
      @keyup.enter="openLowestItem"
    >
      <div class="min-w-0 flex-1">
        <p class="line-clamp-1 text-[12px] font-medium text-foreground" :title="data.lowest_item.title">
          {{ data.lowest_item.title || data.lowest_item.item_id }}
        </p>
        <p class="mt-0.5 flex items-center gap-1 text-[10px] text-slate-500">
          <MapPin v-if="data.lowest_item.region" class="h-3 w-3" />
          <span v-if="data.lowest_item.region" class="truncate">{{ data.lowest_item.region }}</span>
          <span v-if="data.decline_days > 0" class="tabular">
            · {{ formatRelativeDay(data.decline_days) }}
            · {{ t('dashboard.deals.avgDailyDeclineShort', { amount: data.avg_daily_decline.toFixed(2) }) }}
          </span>
        </p>
      </div>
      <ExternalLink class="h-3.5 w-3.5 shrink-0 text-slate-400" />
    </div>
  </article>
</template>




