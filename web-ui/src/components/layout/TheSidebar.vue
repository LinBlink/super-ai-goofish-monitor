<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import {
  LayoutDashboard,
  ListTodo,
  Users,
  Inbox,
  Terminal,
  Settings2,
} from 'lucide-vue-next'
import { useWebSocket } from '@/composables/useWebSocket'
import { useI18n } from 'vue-i18n'

const emit = defineEmits<{
  (event: 'navigate'): void
}>()
const { isConnected } = useWebSocket()
const { t } = useI18n()

const navItems = computed(() => [
  { to: '/dashboard', label: t('sidebar.dashboard'), icon: LayoutDashboard },
  { to: '/tasks', label: t('sidebar.tasks'), icon: ListTodo },
  { to: '/accounts', label: t('sidebar.accounts'), icon: Users },
  { to: '/results', label: t('sidebar.results'), icon: Inbox },
  { to: '/logs', label: t('sidebar.logs'), icon: Terminal },
  { to: '/settings', label: t('sidebar.settings'), icon: Settings2 },
])

const connectionLabel = computed(() => (
  isConnected.value ? t('sidebar.backendConnected') : t('sidebar.backendConnecting')
))

</script>

<template>
  <nav class="flex h-full flex-col">
    <ul class="space-y-1">
      <li v-for="item in navItems" :key="item.to">
        <RouterLink
          :to="item.to"
          class="group flex items-center gap-2.5 rounded-2xl px-3 py-2.5 text-sm font-semibold transition-colors"
          :class="[
            $route.path === item.to || $route.path.startsWith(item.to + '/')
              ? 'bg-primary text-slate-900'
              : 'text-slate-600 hover:bg-muted hover:text-foreground',
          ]"
          @click="emit('navigate')"
        >
          <component
            :is="item.icon"
            class="h-5 w-5 shrink-0"
            :class="[
              $route.path === item.to || $route.path.startsWith(item.to + '/')
                ? 'text-slate-900'
                : 'text-slate-500 group-hover:text-slate-700',
            ]"
          />
          <span class="truncate">{{ item.label }}</span>
        </RouterLink>
      </li>
    </ul>

    <div class="mt-auto px-3 pb-2 pt-6">
      <div class="flex items-center gap-2 text-[11px] text-slate-500">
        <span
          class="h-2 w-2 shrink-0 rounded-full"
          :class="isConnected ? 'bg-emerald-500' : 'bg-amber-400'"
        ></span>
        <span class="font-medium">{{ connectionLabel }}</span>
      </div>
    </div>
  </nav>
</template>




