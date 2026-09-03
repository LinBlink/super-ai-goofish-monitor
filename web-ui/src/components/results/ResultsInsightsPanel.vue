<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ResultInsights } from '@/types/result.d.ts'
import MinPriceChart from './MinPriceChart.vue'
import { formatDateTime } from '@/i18n'

const props = defineProps<{
  insights: ResultInsights | null
  selectedTaskLabel?: string | null
}>()
const { t } = useI18n()

const summaryCards = computed(() => {
  if (!props.insights) return []
  const market = props.insights.market_summary
  const history = props.insights.history_summary
  return [
    {
      label: t('results.insights.currentAvg'),
      value: market.avg_price ? `¥${market.avg_price}` : '—',
      hint: t('results.insights.sampleCount', { count: market.sample_count || 0 }),
    },
    {
      label: t('results.insights.historyAvg'),
      value: history.avg_price ? `¥${history.avg_price}` : '—',
      hint: t('results.insights.uniqueItems', { count: history.unique_items || 0 }),
    },
    {
      label: t('results.insights.currentMin'),
      value: market.min_price ? `¥${market.min_price}` : '—',
      hint: market.max_price
        ? t('results.insights.highestPrice', { price: market.max_price })
        : t('results.insights.noRange'),
    },
  ]
})

const latestSnapshotText = computed(() => {
  if (!props.insights?.latest_snapshot_at) return t('results.insights.noSnapshot')
  return t('results.insights.latestSnapshot', {
    time: formatDateTime(props.insights.latest_snapshot_at, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }),
  })
})
</script>

<template>
  <section class="xy-card-flat p-3">
    <header class="mb-2">
      <p class="text-[10px] font-semibold uppercase tracking-widest" style="color: hsl(56 100% 36%)">
        Market Intelligence
      </p>
      <h2 class="mt-0.5 text-base font-black tracking-tight text-foreground">
        {{ selectedTaskLabel || t('results.insights.defaultTitle') }}
      </h2>
      <p class="mt-0.5 text-[12px] text-slate-500">{{ t('results.insights.subtitle') }}</p>
    </header>

    <div class="grid gap-2 md:grid-cols-3">
      <article
        v-for="card in summaryCards"
        :key="card.label"
        class="xy-card-flat p-2.5"
      >
        <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">{{ card.label }}</p>
        <p class="mt-1 text-lg font-black tabular text-foreground">{{ card.value }}</p>
        <p class="mt-0.5 text-[11px] text-slate-500">{{ card.hint }}</p>
      </article>
    </div>

    <div class="mt-2 grid gap-2 sm:grid-cols-3">
      <div class="xy-card-flat px-3 py-2 text-[12px] text-slate-600">
        {{ t('results.insights.currentMedian') }}
        <span class="font-semibold text-foreground">
          {{ insights?.market_summary.median_price ? `¥${insights.market_summary.median_price}` : '—' }}
        </span>
      </div>
      <div class="xy-card-flat px-3 py-2 text-[12px] text-slate-600">
        {{ t('results.insights.historyMin') }}
        <span class="font-semibold text-foreground">
          {{ insights?.history_summary.min_price ? `¥${insights.history_summary.min_price}` : '—' }}
        </span>
      </div>
      <div class="xy-card-flat px-3 py-2 text-[12px] text-slate-600">
        {{ t('results.insights.historyMax') }}
        <span class="font-semibold text-foreground">
          {{ insights?.history_summary.max_price ? `¥${insights.history_summary.max_price}` : '—' }}
        </span>
      </div>
    </div>

    <p class="mt-2 text-[11px] text-slate-400">{{ latestSnapshotText }}</p>

    <div
      class="mt-2 rounded-xl p-2"
      style="background-color: hsl(56 100% 95%)"
    >
      <p class="text-[10px] font-semibold uppercase tracking-wider" style="color: hsl(56 100% 36%)">
        {{ t('results.insights.snapshotCount', { count: insights?.market_summary.sample_count || 0 }) }}
      </p>
      <p class="mt-1 text-[12px] leading-relaxed text-slate-700">
        {{ t('results.insights.trendReading') }}
      </p>
    </div>

    <div v-if="(insights?.daily_trend?.length ?? 0) > 0" class="mt-2">
      <MinPriceChart
        :points="(insights?.daily_trend || []).map((p) => ({ day: p.day, min_price: p.min_price }))"
        :height="80"
        :width="600"
      />
    </div>
  </section>
</template>




