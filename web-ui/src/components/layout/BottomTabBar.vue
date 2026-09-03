<script setup lang="ts">
import { useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  LayoutDashboard,
  ListTodo,
  Inbox,
  UserCircle2,
  Settings as SettingsIcon,
} from 'lucide-vue-next'

interface TabItem {
  to: string
  i18nKey: string
  icon: typeof LayoutDashboard
}

const route = useRoute()
const { t } = useI18n()

const tabs: TabItem[] = [
  { to: '/dashboard', i18nKey: 'nav.dashboard', icon: LayoutDashboard },
  { to: '/tasks', i18nKey: 'nav.tasks', icon: ListTodo },
  { to: '/results', i18nKey: 'nav.results', icon: Inbox },
  { to: '/accounts', i18nKey: 'nav.accounts', icon: UserCircle2 },
  { to: '/settings', i18nKey: 'nav.settings', icon: SettingsIcon },
]

function isActive(tab: TabItem): boolean {
  return route.path === tab.to || route.path.startsWith(tab.to + '/')
}
</script>

<template>
  <nav
    class="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-white pb-safe shadow-[0_-4px_16px_rgba(0,0,0,0.04)]"
  >
    <ul class="mx-auto grid max-w-screen-sm grid-cols-5">
      <li v-for="tab in tabs" :key="tab.to" class="contents">
        <RouterLink
          :to="tab.to"
          class="flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors"
          :class="isActive(tab) ? 'text-brand-op' : 'text-slate-500 hover:text-slate-700'"
          :aria-label="t(tab.i18nKey)"
        >
          <component
            :is="tab.icon"
            class="h-5 w-5"
            :class="isActive(tab) ? 'text-brand-op' : 'text-slate-500'"
          />
          <span :class="isActive(tab) ? 'font-bold' : ''">{{ t(tab.i18nKey) }}</span>
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>




