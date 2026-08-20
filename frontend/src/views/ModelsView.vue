<script setup>
import { ref } from "vue";
import UsageAnalysisView from "../components/UsageAnalysisView.vue";
defineProps({ range: String, autoRefresh: Boolean, refreshInterval: Number });
const view = ref(null);
defineExpose({ refresh: () => view.value?.refresh() });
</script>
<template><UsageAnalysisView ref="view" kind="models" :range="range" :auto-refresh="autoRefresh" :refresh-interval="refreshInterval" /></template>
