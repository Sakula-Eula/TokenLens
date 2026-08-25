<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import ApiStateBanner from "../components/ApiStateBanner.vue";
import ModelIcon from "../components/ModelIcon.vue";
import { fetchModels, fetchProviders, fetchSummary, fetchTrend } from "../api";

const props = defineProps({ range: { type: String, default: "24h" }, autoRefresh: { type: Boolean, default: true }, refreshInterval: { type: Number, default: 10000 } });
const summary = ref({}); const trend = ref([]); const models = ref([]); const providers = ref([]);
const error = ref(""); const updatedAt = ref(""); const loading = ref(true); const chartEl = ref(null);
let chart = null; let timer = null;
const cards = computed(() => [
  ["Total Token", summary.value.total_tokens], ["Input Token", summary.value.input_tokens],
  ["Output Token", summary.value.output_tokens], ["Cache Read", summary.value.cache_read_tokens],
]);
function fmt(value) { return (Number(value) || 0).toLocaleString("zh-CN"); }
function updateChart() { chart?.setOption({ color: ["#2476f5", "#20b77a", "#8b5cf6", "#f79009"], tooltip: { trigger: "axis" }, legend: { bottom: 0, data: ["Total", "Input", "Output", "Cache Read"] }, grid: { left: 20, right: 20, top: 25, bottom: 45, containLabel: true }, xAxis: { type: "category", boundaryGap: false, data: trend.value.map(item => item.bucket.slice(5).replace("T", " ")), axisLabel: { hideOverlap: true, color: "#7b879b" } }, yAxis: { type: "value", axisLabel: { color: "#7b879b" }, splitLine: { lineStyle: { color: "#edf1f6", type: "dashed" } } }, series: [["Total", "total_tokens"], ["Input", "input_tokens"], ["Output", "output_tokens"], ["Cache Read", "cache_read_tokens"]].map(([name, key]) => ({ name, type: "line", smooth: true, showSymbol: false, data: trend.value.map(item => item[key]) })) }, true); }
async function refresh() { loading.value = true; try { const [s, t, m, p] = await Promise.all([fetchSummary(props.range), fetchTrend(props.range), fetchModels(props.range, { limit: 8 }), fetchProviders(props.range, { limit: 8 })]); summary.value = s; trend.value = t.items || []; models.value = m.items || []; providers.value = p.items || []; error.value = ""; updatedAt.value = new Date().toLocaleTimeString("zh-CN", { hour12: false }); await nextTick(); updateChart(); } catch (exc) { error.value = exc?.response?.data?.detail || "Token 数据加载失败"; } finally { loading.value = false; } }
function configureTimer() { clearInterval(timer); timer = props.autoRefresh ? setInterval(refresh, props.refreshInterval) : null; }
function resize() { chart?.resize(); }
onMounted(() => { chart = echarts.init(chartEl.value); window.addEventListener("resize", resize); refresh(); configureTimer(); });
onBeforeUnmount(() => { clearInterval(timer); chart?.dispose(); window.removeEventListener("resize", resize); });
watch(() => props.range, refresh); watch(() => [props.autoRefresh, props.refreshInterval], configureTimer);
defineExpose({ refresh });
</script>

<template><div class="tokens-page" :class="{ loading }"><div class="page-heading"><div><h1>Token 分析</h1><p>分析 Input、Output 与缓存用量构成</p></div></div><ApiStateBanner :error="error" :updated-at="updatedAt" /><section class="cards"><article v-for="card in cards" :key="card[0]"><span>{{ card[0] }}</span><b>{{ fmt(card[1]) }}</b></article></section><section class="panel chart-panel"><h2>Token 类型趋势</h2><div ref="chartEl" class="chart"></div></section><section class="rank-grid"><article class="panel"><div class="heading"><h2>模型构成</h2><RouterLink to="/models">查看全部</RouterLink></div><div v-for="item in models" :key="item.model" class="row"><b class="model-name"><ModelIcon :model="item.model" :size="26" />{{ item.model }}</b><span>{{ fmt(item.total_tokens) }}</span><small>Cache {{ fmt(item.cache_tokens) }}</small></div><div v-if="!models.length" class="empty">暂无模型数据</div></article><article class="panel"><div class="heading"><h2>Provider 构成</h2><RouterLink to="/providers">查看全部</RouterLink></div><div v-for="item in providers" :key="item.provider" class="row"><b>{{ item.provider }}</b><span>{{ fmt(item.total_tokens) }}</span><small>Cache {{ fmt(item.cache_tokens) }}</small></div><div v-if="!providers.length" class="empty">暂无 Provider 数据</div></article></section></div></template>

<style scoped>
.tokens-page{max-width:1540px;margin:0 auto;color:#475467;transition:opacity .2s}.loading{opacity:.75}.page-heading{min-height:70px}.page-heading h1{margin:0;color:#101828;font-size:22px}.page-heading p{margin:7px 0;color:#7b879b;font-size:13px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}.cards article,.panel{border:1px solid #e6ebf2;border-radius:10px;background:#fff;box-shadow:0 2px 8px #1018280a}.cards article{min-height:98px;display:grid;align-content:center;gap:7px;padding:15px}.cards span{color:#667085;font-size:11px}.cards b{color:#101828;font-size:21px}.panel{padding:17px}.panel h2{margin:0;color:#101828;font-size:15px}.chart-panel{margin-bottom:14px}.chart{height:340px}.rank-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.heading{display:flex;justify-content:space-between;margin-bottom:12px}.heading a{color:#1769ef;font-size:11px;text-decoration:none}.row{display:grid;grid-template-columns:1fr auto auto;gap:14px;align-items:center;min-height:43px;border-bottom:1px solid #edf1f6;font-size:11px}.row b{overflow:hidden;color:#344054;text-overflow:ellipsis}.row .model-name{display:flex;align-items:center;gap:8px}.row small{color:#98a2b3}.empty{height:120px;display:grid;place-items:center;color:#98a2b3;font-size:11px}@media(max-width:1100px){.cards{grid-template-columns:repeat(3,1fr)}}@media(max-width:720px){.cards{grid-template-columns:repeat(2,1fr)}.rank-grid{grid-template-columns:1fr}.row small{display:none}}
</style>
