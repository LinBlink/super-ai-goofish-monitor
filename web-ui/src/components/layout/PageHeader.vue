<script setup lang="ts">
import type { Component } from 'vue'

const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    icon?: Component
  }>(),
  {
    description: '',
  },
)
</script>

<template>
  <div class="mb-6 flex animate-fade-in flex-col gap-4 md:flex-row md:items-center md:justify-between">
    <div class="flex items-start gap-4">
      <div v-if="icon" class="page-icon">
        <component :is="icon" class="h-6 w-6" />
      </div>
      <div>
        <h1 class="text-2xl font-black tracking-tight text-slate-800 md:text-3xl">
          {{ title }}
        </h1>
        <p v-if="description" class="mt-1 max-w-2xl text-sm font-medium text-slate-500">
          {{ description }}
        </p>
      </div>
    </div>
    <div class="flex shrink-0 items-center gap-3">
      <slot name="actions" />
    </div>
  </div>
</template>
