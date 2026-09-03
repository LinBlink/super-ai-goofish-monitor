<script setup lang="ts">
defineProps<{
  size?: number | string
  className?: string
}>()
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    :width="size ?? 24"
    :height="size ?? 24"
    viewBox="0 0 64 64"
    :class="className"
    role="img"
    aria-label="Lightning fish"
    fill="none"
  >
    <defs>
      <linearGradient id="lf-fish" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#22d3ee" />
        <stop offset="55%" stop-color="#3b82f6" />
        <stop offset="100%" stop-color="#7c3aed" />
      </linearGradient>
      <linearGradient id="lf-bolt" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#fde047" />
        <stop offset="100%" stop-color="#f59e0b" />
      </linearGradient>
      <linearGradient id="lf-fin" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#a5f3fc" />
        <stop offset="100%" stop-color="#3b82f6" />
      </linearGradient>
    </defs>

    <!-- 鱼身 -->
    <path
      d="M8 32 C 16 18, 36 16, 48 24 C 54 28, 58 30, 62 30 L 62 34 C 58 34, 54 36, 48 40 C 36 48, 16 46, 8 32 Z"
      fill="url(#lf-fish)"
    />
    <!-- 鱼鳃 -->
    <path
      d="M28 26 C 30 30, 30 34, 28 38"
      stroke="#0f172a"
      stroke-width="1.6"
      stroke-linecap="round"
      fill="none"
      opacity="0.6"
    />
    <!-- 鱼眼 -->
    <circle cx="18" cy="30" r="2.6" fill="#0f172a" />
    <circle cx="18.8" cy="29.2" r="0.9" fill="#f8fafc" />
    <!-- 背鳍 -->
    <path
      d="M30 18 C 34 12, 40 12, 44 16 C 40 18, 34 19, 30 18 Z"
      fill="url(#lf-fin)"
    />
    <!-- 胸鳍 -->
    <path
      d="M30 38 C 32 44, 38 46, 42 44 C 38 42, 34 40, 30 38 Z"
      fill="url(#lf-fin)"
      opacity="0.9"
    />
    <!-- 鱼鳞 -->
    <g opacity="0.45" stroke="#e0f2fe" stroke-width="0.8" fill="none">
      <path d="M22 26 q 3 -3 6 0" />
      <path d="M28 24 q 3 -3 6 0" />
      <path d="M34 23 q 3 -3 6 0" />
      <path d="M22 34 q 3 3 6 0" />
      <path d="M28 36 q 3 3 6 0" />
      <path d="M34 37 q 3 3 6 0" />
    </g>
    <!-- 闪电 -->
    <path
      d="M40 4 L 26 24 L 36 26 L 22 60 L 42 32 L 32 30 L 46 4 Z"
      fill="url(#lf-bolt)"
      stroke="#92400e"
      stroke-width="1.2"
      stroke-linejoin="round"
    />
  </svg>
</template>





