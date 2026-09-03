<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DashboardTaskSearch from '@/components/layout/DashboardTaskSearch.vue'
import LocaleToggle from '@/components/layout/LocaleToggle.vue'
import LightningFishIcon from '@/components/icons/LightningFishIcon.vue'
import { Bell, Search, UserCircle, Menu } from 'lucide-vue-next'
import { useMobileNav } from '@/composables/useMobileNav'
import { useIsMobile } from '@/composables/useMediaQuery'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const route = useRoute()
const { toggleMobileNav } = useMobileNav()
const isMobile = useIsMobile()
const inactiveSearchValue = ref('')
const { t } = useI18n()

const isDashboard = computed(() => route.name === 'Dashboard')

function goAccounts() {
  router.push('/accounts')
}
function goNotifications() {
  router.push({ name: 'Settings', query: { tab: 'notifications' } })
}
</script>

<template>
  <header
    class="sticky top-0 z-40 flex h-12 items-center gap-2 border-b border-border bg-white/95 px-3 backdrop-blur md:h-14 md:px-5"
  >
    <!-- 移动端：菜单 + 品牌 + 占位（搜索移到主区） -->
    <button
      v-if="isMobile"
      type="button"
      class="-ml-1 flex h-9 w-9 items-center justify-center rounded-full text-slate-700 active:bg-muted"
      :aria-label="t('header.openNavigation')"
      @click="toggleMobileNav"
    >
      <Menu class="h-5 w-5" />
    </button>

    <RouterLink
      to="/dashboard"
      class="flex items-center gap-1.5 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      :aria-label="t('header.goHome')"
    >
      <span
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg md:h-9 md:w-9 md:rounded-xl"
        style="background-color: hsl(56 100% 52%)"
      >
        <LightningFishIcon :size="18" class="md:hidden" />
        <LightningFishIcon :size="22" class="hidden md:block" />
      </span>
      <h1
        class="text-[15px] font-black tracking-tight text-foreground md:text-base"
      >
        {{ t('header.brandName') }}
      </h1>
    </RouterLink>

    <!-- 桌面：搜�?-->
    <div class="ml-2 hidden flex-1 md:flex md:max-w-md">
      <DashboardTaskSearch v-if="isDashboard" />
      <div v-else class="relative w-full">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          v-model="inactiveSearchValue"
          type="text"
          readonly
          aria-disabled="true"
          :placeholder="t('header.searchUnavailable')"
          class="h-9 w-full rounded-full border border-border bg-muted pl-9 pr-4 text-sm transition-all focus:outline-none focus:ring-2 focus:ring-primary/40 focus:bg-white"
        />
      </div>
    </div>

    <div class="ml-auto flex items-center gap-1.5 md:gap-2">
      <LocaleToggle />
      <button
        type="button"
        class="hidden h-9 w-9 items-center justify-center rounded-full text-slate-600 hover:bg-muted sm:flex"
        :aria-label="t('header.openNotifications')"
        @click="goNotifications"
      >
        <Bell class="h-4 w-4" />
      </button>
      <button
        type="button"
        class="flex h-9 items-center gap-1.5 rounded-full px-1.5 text-slate-600 hover:bg-muted"
        :aria-label="t('header.openAccounts')"
        @click="goAccounts"
      >
        <span class="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-muted">
          <UserCircle class="h-6 w-6 text-slate-500" />
        </span>
        <span class="hidden text-left lg:block">
          <span class="block text-[11px] font-bold leading-none text-slate-700">Xianyu Admin</span>
          <span class="mt-0.5 block text-[10px] font-medium leading-none text-slate-400">
            {{ t('header.accountManagement') }}
          </span>
        </span>
      </button>
    </div>
  </header>
</template>




