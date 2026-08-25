<script setup>
import { computed } from "vue";
const props = defineProps({ summary: { type: Object, default: () => ({}) } });
const parts = computed(() => [
  ["Input", props.summary.input_cost_micros, "#2476f5"],
  ["Output", props.summary.output_cost_micros, "#20b77a"],
  ["Cache Read", props.summary.cache_read_cost_micros, "#8b5cf6"],
]);
const total = computed(() => Math.max(1, Number(props.summary.total_cost_micros || 0)));
function money(value) { return `¥${(Number(value || 0) / 1_000_000).toFixed(6).replace(/0+$/, "").replace(/\.$/, ".00")}`; }
</script>
<template><div class="cost-breakdown"><div v-for="part in parts" :key="part[0]" class="part"><div><i :style="{ background: part[2] }"></i><span>{{ part[0] }}</span><b>{{ money(part[1]) }}</b></div><div class="bar"><span :style="{ width: `${Number(part[1] || 0) / total * 100}%`, background: part[2] }"></span></div></div></div></template>
<style scoped>.cost-breakdown{display:grid;gap:13px}.part>div:first-child{display:grid;grid-template-columns:8px 1fr auto;align-items:center;gap:8px;font-size:11px}.part i{width:7px;height:7px;border-radius:50%}.part span{color:#667085}.part b{color:#344054}.bar{height:6px;margin-top:7px;overflow:hidden;border-radius:9px;background:#edf1f6}.bar span{display:block;height:100%;border-radius:9px}</style>
