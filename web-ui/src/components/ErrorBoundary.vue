<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

const error = ref<unknown>(null)

onErrorCaptured((err) => {
  error.value = err
  console.error('Unhandled error captured by ErrorBoundary:', err)
  // Stop propagation so a render error in one view doesn't blank the whole app.
  return false
})

function reload() {
  window.location.reload()
}

const errorMessage = () => {
  if (error.value instanceof Error) return error.value.message
  return String(error.value)
}
</script>

<template>
  <div v-if="error" class="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
    <h1 class="text-xl font-semibold">页面出现异常</h1>
    <p class="max-w-md text-sm text-muted-foreground">{{ errorMessage() }}</p>
    <button
      class="rounded-md border px-4 py-2 text-sm hover:bg-accent"
      type="button"
      @click="reload"
    >
      刷新页面
    </button>
  </div>
  <slot v-else />
</template>





