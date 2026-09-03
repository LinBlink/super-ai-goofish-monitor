<script setup lang="ts">
import type { ToastViewportProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { ToastViewport } from "reka-ui"
import { cn } from "@/lib/utils"

const props = defineProps<ToastViewportProps & { class?: HTMLAttributes["class"] }>()

const delegatedProps = reactiveOmit(props, "class")
</script>

<template>
  <ToastViewport
    v-bind="delegatedProps"
    :class="cn('fixed top-4 left-1/2 z-[100] flex max-h-screen w-full -translate-x-1/2 flex-col-reverse p-4 sm:flex-col md:max-w-[420px]', props.class)"
  />
</template>





