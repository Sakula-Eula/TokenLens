<script setup>
defineProps({ name: { type: String, required: true }, size: { type: [Number, String], default: 24 } });
</script>

<template>
  <svg class="tray-icon" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <template v-if="name === 'logo'"><rect x="3" y="12" width="3.5" height="7" rx="1" fill="currentColor" stroke="none"/><rect x="8.7" y="8" width="3.5" height="11" rx="1" fill="currentColor" stroke="none"/><rect x="14.4" y="4" width="3.5" height="15" rx="1" fill="currentColor" stroke="none"/></template>
    <template v-else-if="name === 'refresh'"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/></template>
    <template v-else-if="name === 'pin'"><path d="m14 4 6 6-3 1-4 4-1 4-7-7 4-1 4-4 1-3Z"/><path d="m9 15-5 5"/></template>
    <template v-else-if="name === 'settings'"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></template>
    <template v-else-if="name === 'clock'"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></template>
    <template v-else-if="name === 'coins'"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v5c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 11v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/></template>
    <template v-else-if="name === 'wallet'"><path d="M4 7.5h14.5A1.5 1.5 0 0 1 20 9v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h11"/><path d="M20 12h-5a2 2 0 0 0 0 4h5"/></template>
    <template v-else-if="name === 'send'"><path d="m21 3-7.5 18-4-8.5L1 9l20-6Z"/><path d="M9.5 12.5 21 3"/></template>
    <template v-else-if="name === 'chevron'"><path d="m9 18 6-6-6-6"/></template>
    <template v-else-if="name === 'close'"><path d="M5 5l14 14M19 5 5 19"/></template>
  </svg>
</template>

<style scoped>.tray-icon { display: block; flex: 0 0 auto; }</style>
