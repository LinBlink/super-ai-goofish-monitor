<script setup lang="ts">
import type { Component } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    value: string
    icon?: Component
    hint?: string
    tone?: 'primary' | 'emerald' | 'amber' | 'sky' | 'rose'
  }>(),
  {
    hint: '',
    tone: 'primary',
  },
)

const toneClasses: Record<string, string> = {
  primary: 'bg-primary/10 text-primary',
  emerald: 'bg-emerald-500/10 text-emerald-600',
  amber: 'bg-amber-500/15 text-amber-600',
  sky: 'bg-sky-500/10 text-sky-600',
  rose: 'bg-rose-500/10 text-rose-600',
}
</script>

<template>
  <div class="app-card p-5">
    <div class="flex items-center justify-between">
      <p class="text-sm font-semibold text-slate-500">{{ label }}</p>
      <div
        v-if="icon"
        :class="['flex h-10 w-10 items-center justify-center rounded-xl', toneClasses[tone]]"
      >
        <component :is="icon" class="h-5 w-5" />
      </div>
    </div>
    <p class="mt-2 text-3xl font-black tracking-tight text-slate-800">{{ value }}</p>
    <p v-if="hint" class="mt-1 text-xs font-medium text-slate-400">{{ hint }}</p>
  </div>
</template>
