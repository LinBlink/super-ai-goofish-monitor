<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import TheHeader from '@/components/layout/TheHeader.vue'
import TheSidebar from '@/components/layout/TheSidebar.vue'
import BottomTabBar from '@/components/layout/BottomTabBar.vue'
import { useMobileNav } from '@/composables/useMobileNav'
import { useIsMobile } from '@/composables/useMediaQuery'

const { isMobileNavOpen, closeMobileNav } = useMobileNav()
const isMobile = useIsMobile()
const { t } = useI18n()
</script>

<template>
  <div class="relative flex min-h-screen w-full flex-col bg-background selection:bg-primary/40">
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[120] focus:rounded-full focus:px-4 focus:py-2 focus:text-sm focus:font-semibold"
      style="background-color: hsl(56 100% 52%); color: #1f1f1f"
    >
      {{ t('common.skipToContent') }}
    </a>

    <TheHeader />

    <transition name="mobile-nav">
      <div v-if="isMobileNavOpen" class="fixed inset-0 z-50 md:hidden">
        <button
          type="button"
          class="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px]"
          :aria-label="t('common.close')"
          @click="closeMobileNav"
        />
        <aside class="relative h-full w-72 border-r border-border bg-white p-4 shadow-2xl">
          <TheSidebar class="pt-12" @navigate="closeMobileNav" />
        </aside>
      </div>
    </transition>

    <div class="flex flex-1">
      <aside
        v-if="!isMobile"
        class="hidden w-60 shrink-0 border-r border-border bg-white md:block"
      >
        <div class="sticky top-14 h-[calc(100vh-3.5rem)] p-3">
          <TheSidebar />
        </div>
      </aside>

      <main
        id="main-content"
        tabindex="-1"
        class="flex-1 overflow-x-hidden px-3 pb-20 pt-3 focus:outline-none md:px-8 md:pb-8 md:pt-6"
        :class="isMobile ? 'pb-24' : ''"
      >
        <div class="mx-auto w-full max-w-7xl animate-fade-in">
          <RouterView v-slot="{ Component }">
            <transition name="page" mode="out-in">
              <component :is="Component" />
            </transition>
          </RouterView>
        </div>
      </main>
    </div>

    <BottomTabBar v-if="isMobile" />
  </div>
</template>

<style scoped>
.page-enter-active,
.page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.mobile-nav-enter-active,
.mobile-nav-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.mobile-nav-enter-from,
.mobile-nav-leave-to {
  opacity: 0;
  transform: translateX(-16px);
}

@media (prefers-reduced-motion: reduce) {
  .page-enter-active,
  .page-leave-active,
  .mobile-nav-enter-active,
  .mobile-nav-leave-active {
    transition: none;
  }
  .page-enter-from,
  .page-leave-to,
  .mobile-nav-enter-from,
  .mobile-nav-leave-to {
    opacity: 1;
    transform: none;
  }
}
</style>




