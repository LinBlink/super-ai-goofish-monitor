<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ResultItem } from '@/types/result.d.ts'
import {
  ExternalLink,
  CheckCircle2,
  XCircle,
  AlertCircle,
  EyeOff,
  Eye,
  TrendingDown,
} from 'lucide-vue-next'
import { formatDateTime } from '@/i18n'

interface Props {
  item: ResultItem
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'toggle-block', item: ResultItem): void
}>()
const { t } = useI18n()

const info = props.item.商品信息
const ai = props.item.ai_analysis
const priceInsight = props.item.price_insight

const recommendationStatus = computed(() => {
  if (ai?.is_recommended === true)
    return {
      label: t('results.card.strongRecommend'),
      icon: CheckCircle2,
      tone: 'bg-emerald-50 text-emerald-700',
    }
  if (ai?.is_recommended === false)
    return {
      label: t('results.card.notRecommended'),
      icon: XCircle,
      tone: 'bg-rose-50 text-rose-700',
    }
  return {
    label: t('results.card.pending'),
    icon: AlertCircle,
    tone: 'bg-amber-50 text-amber-700',
  }
})

const imageUrl = info.商品图片列表?.[0] || info.商品主图链接 || ''
const crawlTime = props.item.爬取时间
  ? formatDateTime(props.item.爬取时间, { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  : ''
const matchScore = ai?.value_score ?? 0
const isHidden = computed(() => props.item._effective_hidden === true || props.item._status === 'hidden')
const canToggleBlock = computed(() => props.item._hidden_reason !== 'expired')
const hiddenLabel = computed(() => {
  if (props.item._hidden_reason === 'expired') return t('results.card.expired')
  return t('results.card.hidden')
})

const reasonText = computed(() => (ai?.reason ? ai.reason.trim() : ''))
const hasReason = computed(() => reasonText.value.length > 0)
const isLongReason = computed(() => reasonText.value.length > 60)
const isReasonExpanded = ref(false)
</script>

<template>
  <article class="xy-card overflow-hidden" :class="isHidden ? 'opacity-60' : ''">
    <!-- Image -->
    <a
      :href="info.商品链接"
      target="_blank"
      rel="noopener noreferrer"
      class="relative block aspect-square overflow-hidden"
    >
      <div v-if="!imageUrl" class="absolute inset-0 bg-[#eaeaea]"></div>
      <img
        v-else
        :src="imageUrl"
        :alt="info.商品标题"
        class="h-full w-full object-cover"
        loading="lazy"
      />
      <div v-if="isHidden" class="absolute inset-0 flex items-center justify-center bg-black/40">
        <span class="rounded-full bg-white/85 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-700">
          {{ hiddenLabel }}
        </span>
      </div>
      <div class="absolute right-1.5 top-1.5 flex gap-1">
        <button
          v-if="canToggleBlock"
          type="button"
          class="rounded-full bg-white/85 p-1.5 text-slate-700 shadow-sm hover:bg-white"
          :aria-label="isHidden ? t('results.card.unblock') : t('results.card.block')"
          @click.prevent.stop="emit('toggle-block', props.item)"
        >
          <EyeOff v-if="!isHidden" class="h-3.5 w-3.5" />
          <Eye v-else class="h-3.5 w-3.5" />
        </button>
      </div>
    </a>

    <!-- Content -->
    <div class="space-y-1.5 p-2.5">
      <a
        :href="info.商品链接"
        target="_blank"
        rel="noopener noreferrer"
        class="line-clamp-2 block text-[13px] font-medium leading-snug text-foreground hover:text-foreground"
      >
        {{ info.商品标题 }}
      </a>

      <div class="flex items-baseline gap-1.5">
        <span class="xy-price-sign">¥</span>
        <span class="xy-price text-[20px] tabular">{{ info.当前售价 }}</span>
        <span
          v-if="info['商品原价'] && info['商品原价'] !== info.当前售价"
          class="text-[11px] text-slate-400 line-through tabular"
        >¥{{ info['商品原价'] }}</span>
      </div>

      <!-- AI 推荐状�?-->
      <div
        v-if="ai"
        class="flex items-center justify-between rounded-lg px-1.5 py-1 text-[10px] font-semibold"
        :class="recommendationStatus.tone"
      >
        <span class="flex items-center gap-1 truncate">
          <component :is="recommendationStatus.icon" class="h-3 w-3 shrink-0" />
          <span class="truncate">{{ recommendationStatus.label }}</span>
        </span>
        <span class="tabular">{{ matchScore }}%</span>
      </div>

      <!-- AI 推荐理由 -->
      <div v-if="hasReason" class="space-y-0.5">
        <p
          class="text-[11px] leading-relaxed text-slate-600"
          :class="isReasonExpanded ? '' : 'line-clamp-2'"
        >
          {{ reasonText }}
        </p>
        <button
          v-if="isLongReason"
          type="button"
          class="text-[10px] font-semibold uppercase tracking-wider text-slate-500 active:text-slate-700"
          @click.stop="isReasonExpanded = !isReasonExpanded"
        >
          {{ isReasonExpanded ? t('results.card.collapse') : t('results.card.expand') }}
        </button>
      </div>

      <!-- 价格洞察 -->
      <div v-if="priceInsight?.observation_count" class="flex items-center gap-1 text-[10px] text-slate-500">
        <TrendingDown class="h-3 w-3" />
        <span class="tabular">
          {{ t('results.card.historicalLow') }} ¥{{ priceInsight.min_price }}
        </span>
      </div>

      <p class="flex items-center gap-1 text-[10px] text-slate-400">
        <ExternalLink class="h-3 w-3" />
        <a
          :href="info.商品链接"
          target="_blank"
          rel="noopener noreferrer"
          class="truncate hover:text-slate-600"
        >{{ crawlTime }}</a>
      </p>
    </div>
  </article>
</template>




