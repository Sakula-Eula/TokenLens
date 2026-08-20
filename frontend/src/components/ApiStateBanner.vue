<script setup>
defineProps({ error: { type: String, default: "" }, updatedAt: { type: String, default: "" } });
</script>

<template>
  <div v-if="error" class="api-banner error" role="alert"><strong>数据更新失败</strong><span>{{ error }}<template v-if="updatedAt">，当前显示 {{ updatedAt }} 的数据</template></span></div>
  <div v-else-if="updatedAt" class="api-banner updated"><span>最后更新：{{ updatedAt }}</span></div>
</template>

<style scoped>
.api-banner { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 9px 12px; border-radius: 8px; font-size: 11px; }.api-banner.error { border: 1px solid #fecaca; color: #b42318; background: #fff1f1; }.api-banner.updated { justify-content: flex-end; padding: 0; color: #98a2b3; background: transparent; }.api-banner strong { font-size: 12px; }
</style>
