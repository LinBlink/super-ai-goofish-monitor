<script setup lang="ts">
import type { ResultItem } from '@/types/result.d.ts'
import { useI18n } from 'vue-i18n'
import ResultCard from './ResultCard.vue'

interface Props {
  results: ResultItem[]
  isLoading: boolean
}

defineProps<Props>()
const { t } = useI18n()

const emit = defineEmits<{
  (e: 'toggle-block', item: ResultItem): void
}>()

const skeletonItems = Array.from({ length: 6 }, (_, index) => index)
</script>

<template>
  <div :aria-busy="isLoading">
    <div
      v-if="isLoading"
      class="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
      aria-live="polite"
    >
      <div v-for="item in skeletonItems" :key="item" class="xy-card overflow-hidden">
        <div class="aspect-square animate-pulse bg-[#eaeaea]"></div>
        <div class="space-y-2 p-2.5">
          <div class="h-3 w-4/5 animate-pulse rounded bg-[#eaeaea]"></div>
          <div class="h-5 w-1/2 animate-pulse rounded bg-[#eaeaea]"></div>
        </div>
      </div>
    </div>

    <div v-else-if="results.length === 0" class="xy-card py-10 text-center text-sm text-slate-500">
      {{ t('results.grid.empty') }}
    </div>

    <div
      v-else
      class="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      <ResultCard
        v-for="item in results"
        :key="item.商品信息.商品ID"
        :item="item"
        @toggle-block="emit('toggle-block', $event)"
      />
    </div>
  </div>
</template>




