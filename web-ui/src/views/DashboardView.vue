<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDashboard } from '@/composables/useDashboard'
import PriceTrendChart from '@/components/results/PriceTrendChart.vue'
import {
  TrendingDown,
  Wallet,
  Database,
  ListTodo,
  RefreshCcw,
  Tag,
  ArrowRight,
} from 'lucide-vue-next'

const router = useRouter()
const { t } = useI18n()
const { taskSummaries, decliningDipTasks, error, fetchSummary, isLoading } =
  useDashboard()

const stats = computed(() => {
  const list = taskSummaries.value
  const withPrice = list.filter((t) => t.history_avg_price !== null)
  const samples = list.reduce((sum, t) => sum + (t.history_sample_count || 0), 0)
  return {
    total: list.length,
    withPrice: withPrice.length,
    samples,
  }
})

function goTasks() {
  router.push({ name: 'Tasks', query: { create: '1' } })
}
function openTask(item: { filename: string | null }) {
  if (item.filename) {
    router.push({ name: 'Results', query: { file: item.filename } })
  }
}
function openLowestItem(link: string) {
  if (link) window.open(link, '_blank', 'noopener,noreferrer')
}
void openLowestItem
</script>

<template>
  <div class="space-y-4">
    <!-- 顶部：欢�?+ 操作 -->
    <section class="xy-card-flat relative overflow-hidden p-3 md:p-5">
      <div
        aria-hidden="true"
        class="absolute inset-x-0 top-0 h-1"
        style="background-color: hsl(56 100% 52%)"
      ></div>
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            {{ t('dashboard.welcomeTag') }}
          </p>
          <h1 class="mt-1 truncate text-lg font-black tracking-tight text-foreground md:text-xl">
            {{ t('dashboard.welcomeTitle') }}
          </h1>
          <p class="mt-1 hidden text-sm text-slate-500 md:block">
            {{ t('dashboard.welcomeSubtitle') }}
          </p>
        </div>
        <div class="flex shrink-0 gap-2">
          <button
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-full bg-muted text-slate-600 active:scale-95"
            :aria-label="t('common.refresh')"
            @click="fetchSummary"
          >
            <RefreshCcw class="h-4 w-4" :class="isLoading ? 'animate-spin' : ''" />
          </button>
          <button
            type="button"
            class="xy-btn-primary text-[13px]"
            @click="goTasks"
          >
            <ListTodo class="h-4 w-4" />
            <span>{{ t('dashboard.createTask') }}</span>
          </button>
        </div>
      </div>
    </section>

    <!-- 数据 stat chips -->
    <section class="grid grid-cols-3 gap-2 md:gap-3">
      <div class="xy-card flex flex-col gap-1 p-3">
        <div class="flex items-center justify-between">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            {{ t('dashboard.stats.totalTasks') }}
          </span>
          <ListTodo class="h-3.5 w-3.5 text-slate-400" />
        </div>
        <span class="text-xl font-black tabular text-foreground md:text-2xl">{{ stats.total }}</span>
      </div>
      <div class="xy-card flex flex-col gap-1 p-3">
        <div class="flex items-center justify-between">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            {{ t('dashboard.stats.priceTracked') }}
          </span>
          <Wallet class="h-3.5 w-3.5 text-slate-400" />
        </div>
        <span class="text-xl font-black tabular text-foreground md:text-2xl">{{ stats.withPrice }}</span>
      </div>
      <div class="xy-card flex flex-col gap-1 p-3">
        <div class="flex items-center justify-between">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            {{ t('dashboard.stats.samples') }}
          </span>
          <Database class="h-3.5 w-3.5 text-slate-400" />
        </div>
        <span class="text-xl font-black tabular text-foreground md:text-2xl">{{ stats.samples }}</span>
      </div>
    </section>

    <div v-if="error" class="xy-card-flat border-rose-200 bg-rose-50/40 p-3 text-sm text-rose-700">
      {{ error.message }}
    </div>

    <!-- 持续下跌可抄�?-->
    <section>
      <header class="mb-2 flex items-center justify-between">
        <h2 class="flex items-center gap-2 text-base font-black tracking-tight text-foreground">
          <span class="h-4 w-1.5 rounded-full bg-primary" />
          <TrendingDown class="h-4 w-4" style="color: hsl(var(--price))" />
          {{ t('dashboard.deals.title') }}
        </h2>
        <span class="xy-chip-yellow">{{ decliningDipTasks.length }}</span>
      </header>
      <p class="mb-3 text-[12px] leading-relaxed text-slate-500">
        {{ t('dashboard.deals.description') }}
      </p>

      <div v-if="decliningDipTasks.length === 0" class="xy-card p-8 text-center">
        <p class="text-sm text-slate-500">{{ t('dashboard.deals.empty') }}</p>
      </div>

      <div
        v-else
        class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
      >
        <DipProductCard
          v-for="task in decliningDipTasks"
          :key="task.keyword + (task.task_id ?? '')"
          :data="task"
        />
      </div>
    </section>

    <!-- 价格概览 -->
    <section v-if="taskSummaries.length > 0">
      <header class="mb-2 flex items-center justify-between">
        <h2 class="flex items-center gap-2 text-base font-black tracking-tight text-foreground">
          <span class="h-4 w-1.5 rounded-full bg-primary" />
          <Wallet class="h-4 w-4 text-emerald-600" />
          {{ t('dashboard.priceOverview.title') }}
        </h2>
      </header>

      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="item in [...taskSummaries].sort((x, y) => {
            const a = x.history_avg_price !== null ? 1 : 0
            const b = y.history_avg_price !== null ? 1 : 0
            if (a !== b) return b - a
            return x.task_name.localeCompare(y.task_name)
          })"
          :key="item.task_id ?? item.task_name"
          class="xy-card cursor-pointer p-3 transition-shadow hover:shadow-xy-hover"
          :class="item.filename ? '' : 'opacity-60'"
          @click="openTask(item)"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="line-clamp-1 text-[13px] font-bold text-foreground" :title="item.task_name">
                {{ item.task_name }}
              </p>
              <p class="mt-0.5 flex items-center gap-1 text-[11px] text-slate-500">
                <Tag class="h-3 w-3" />
                <span class="truncate">{{ item.keyword }}</span>
              </p>
            </div>
            <div class="text-right">
              <p class="text-base font-black tabular text-foreground">
                {{ item.history_avg_price !== null ? `¥${item.history_avg_price}` : '—' }}
              </p>
              <p v-if="item.history_sample_count" class="text-[10px] text-slate-400 tabular">
                {{ t('dashboard.priceOverview.sampleLabel', { count: item.history_sample_count }) }}
              </p>
            </div>
          </div>
          <div
            v-if="item.history_daily_trend && item.history_daily_trend.length > 1"
            class="mt-2"
            @click.stop
          >
            <PriceTrendChart :points="item.history_daily_trend" :height="280" />
          </div>
          <div class="mt-2 flex justify-end">
            <ArrowRight class="h-3.5 w-3.5 text-slate-400" />
          </div>
        </div>
      </div>
    </section>
  </div>
</template>




