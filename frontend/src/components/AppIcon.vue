<script setup>
defineProps({ name: { type: String, required: true }, size: { type: [Number, String], default: 20 } });
</script>

<template>
  <svg class="app-icon" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <template v-if="name === 'logo'"><rect x="3" y="12" width="3.5" height="7" rx="1" fill="currentColor" stroke="none" /><rect x="8.7" y="8" width="3.5" height="11" rx="1" fill="currentColor" stroke="none" /><rect x="14.4" y="4" width="3.5" height="15" rx="1" fill="currentColor" stroke="none" /></template>
    <template v-else-if="name === 'home'"><path d="m3 11 9-7 9 7" /><path d="M5.5 10v9h13v-9" /><path d="M9.5 19v-5h5v5" /></template>
    <template v-else-if="name === 'grid'"><rect x="4" y="4" width="6" height="6" rx="1.5" /><rect x="14" y="4" width="6" height="6" rx="1.5" /><rect x="4" y="14" width="6" height="6" rx="1.5" /><rect x="14" y="14" width="6" height="6" rx="1.5" /></template>
    <template v-else-if="name === 'providers'"><circle cx="12" cy="5" r="2.3" /><circle cx="5" cy="17" r="2.3" /><circle cx="19" cy="17" r="2.3" /><path d="M10.5 6.8 6.5 14.8M13.5 6.8l4 8M7.3 17h9.4" /></template>
    <template v-else-if="name === 'wallet'"><path d="M4 7.5h14.5A1.5 1.5 0 0 1 20 9v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h11" /><path d="M20 12h-5a2 2 0 0 0 0 4h5" /></template>
    <template v-else-if="name === 'request'"><path d="M7 3h8l4 4v13H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /><path d="M15 3v5h4M9 13h6M9 17h4" /></template>
    <template v-else-if="name === 'alert'"><path d="M10.3 4.2 2.7 18a2 2 0 0 0 1.8 3h15a2 2 0 0 0 1.8-3L13.7 4.2a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></template>
    <template v-else-if="name === 'settings'"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></template>
    <template v-else-if="name === 'coins'"><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v5c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 11v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5" /></template>
    <template v-else-if="name === 'send'"><path d="m21 3-7.5 18-4-8.5L1 9l20-6Z" /><path d="M9.5 12.5 21 3" /></template>
    <template v-else-if="name === 'check'"><circle cx="12" cy="12" r="9" /><path d="m8 12 2.7 2.7L16.5 9" /></template>
    <template v-else-if="name === 'clock'"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></template>
    <template v-else-if="name === 'refresh'"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" /></template>
    <template v-else-if="name === 'calendar'"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></template>
    <template v-else-if="name === 'trend'"><path d="m3 17 6-6 4 4 8-9" /><path d="M15 6h6v6" /></template>
    <template v-else-if="name === 'chevron'"><path d="m9 18 6-6-6-6" /></template>
  </svg>
</template>

<style scoped>.app-icon { display: block; flex: 0 0 auto; }</style>
