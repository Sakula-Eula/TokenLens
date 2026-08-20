<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import * as echarts from "echarts";
import ApiStateBanner from "./ApiStateBanner.vue";
import RequestDetailDrawer from "./RequestDetailDrawer.vue";
import { fetchModels, fetchProviders, fetchRequests, fetchTrend } from "../api";

const props = defineProps({
  kind: { type: String, required: true }, range: { type: String, default: "24h" },
  autoRefresh: { type: Boolean, default: true }, refreshInterval: { type: Number, default: 10000 },
});
const route = useRoute(); const router = useRouter();
const search = ref(String(route.query.search || ""));
const page = ref(Math.max(1, Number(route.query.page) || 1));
const sortBy = ref(String(route.query.sort || "total_tokens"));
const order = ref(route.query.order === "asc" ? "asc" : "desc");
const selected = ref(String(route.query.selected || ""));
const data = ref({ items: [], total: 0 }); const trend = ref([]); const requests = ref([]);
const loading = ref(true); const error = ref(""); const updatedAt = ref(""); const detailId = ref(null); const chartEl = ref(null);
let chart = null; let timer = null; let searchTimer = null;
const entityKey = computed(() => props.kind === "models" ? "model" : "provider");
const title = computed(() => props.kind === "models" ? "模型分析" : "供应商分析");
const pageCount = computed(() => Math.max(1, Math.ceil(data.value.total / 20)));
const selectedItem = computed(() => data.value.items.find(item => item[entityKey.value] === selected.value));

function fmt(value) { return (Number(value) || 0).toLocaleString("zh-CN"); }
function syncQuery() {
  const query = {};
  if (search.value) query.search = search.value;
  if (page.value > 1) query.page = String(page.value);
  if (sortBy.value !== "total_tokens") query.sort = sortBy.value;
  if (order.value !== "desc") query.order = order.value;
  if (selected.value) query.selected = selected.value;
  router.replace({ query });
}
function updateChart() {
  chart?.setOption({
    color: ["#2476f5", "#20b77a", "#8b5cf6"], tooltip: { trigger: "axis" },
    legend: { data: ["Input", "Output", "Cache"], bottom: 0, textStyle: { color: "#667085", fontSize: 11 } },
    grid: { left: 20, right: 18, top: 24, bottom: 38, containLabel: true },
    xAxis: { type: "category", boundaryGap: false, data: trend.value.map(item => item.bucket.slice(5).replace("T", " ")), axisLabel: { color: "#7b879b", hideOverlap: true } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "#edf1f6", type: "dashed" } }, axisLabel: { color: "#7b879b" } },
    series: [
      { name: "Input", type: "line", smooth: true, data: trend.value.map(item => item.input_tokens) },
      { name: "Output", type: "line", smooth: true, data: trend.value.map(item => item.output_tokens) },
      { name: "Cache", type: "line", smooth: true, data: trend.value.map(item => item.cache_tokens) },
    ],
  }, true);
}
async function refresh() {
  loading.value = true;
  try {
    const fetchGroups = props.kind === "models" ? fetchModels : fetchProviders;
    const groupData = await fetchGroups(props.range, { search: search.value || undefined, limit: 20, offset: (page.value - 1) * 20, sort_by: sortBy.value, order: order.value });
    data.value = groupData;
    if (!selected.value || !groupData.items.some(item => item[entityKey.value] === selected.value)) selected.value = groupData.items[0]?.[entityKey.value] || "";
    if (selected.value) {
      const entityParams = { [entityKey.value]: selected.value };
      const [trendData, requestData] = await Promise.all([fetchTrend(props.range, entityParams), fetchRequests({ ...entityParams, limit: 8, offset: 0 })]);
      trend.value = trendData.items || []; requests.value = requestData.items || [];
    } else { trend.value = []; requests.value = []; }
    error.value = ""; updatedAt.value = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    syncQuery(); await nextTick(); updateChart();
  } catch (exc) { error.value = exc?.response?.data?.detail || "分析数据加载失败"; }
  finally { loading.value = false; }
}
function configureTimer() { clearInterval(timer); timer = props.autoRefresh ? setInterval(refresh, props.refreshInterval) : null; }
function handleResize() { chart?.resize(); }
onMounted(() => { chart = echarts.init(chartEl.value); window.addEventListener("resize", handleResize); refresh(); configureTimer(); });
onBeforeUnmount(() => { clearInterval(timer); clearTimeout(searchTimer); chart?.dispose(); window.removeEventListener("resize", handleResize); });
watch(search, () => { clearTimeout(searchTimer); page.value = 1; searchTimer = setTimeout(refresh, 250); });
watch([page, sortBy, order], refresh);
watch(() => props.range, () => { page.value = 1; refresh(); });
watch(() => [props.autoRefresh, props.refreshInterval], configureTimer);
watch(selected, () => { syncQuery(); refresh(); });
defineExpose({ refresh });
</script>

<template>
  <div class="analysis-page" :class="{ loading }">
    <div class="page-heading"><div><h1>{{ title }}</h1><p>查看用量、性能、错误率和关联请求</p></div><span>共 {{ fmt(data.total) }} 项</span></div>
    <ApiStateBanner :error="error" :updated-at="updatedAt" />
    <section class="panel controls"><input v-model.trim="search" :placeholder="`搜索${kind === 'models' ? '模型' : 'Provider'}`" /><select v-model="sortBy"><option value="total_tokens">按 Token</option><option value="requests">按请求数</option><option value="avg_latency_ms">按耗时</option><option value="error_rate">按错误率</option></select><button type="button" @click="order = order === 'desc' ? 'asc' : 'desc'">{{ order === 'desc' ? '降序 ↓' : '升序 ↑' }}</button></section>
    <section class="layout">
      <article class="panel ranking"><table><thead><tr><th>{{ kind === 'models' ? '模型' : 'Provider' }}</th><th>请求</th><th>Token</th><th>平均耗时</th><th>错误率</th></tr></thead><tbody><tr v-for="item in data.items" :key="item[entityKey]" :class="{ selected: selected === item[entityKey] }" @click="selected = item[entityKey]"><td><b>{{ item[entityKey] }}</b><small>Input {{ fmt(item.input_tokens) }} · Output {{ fmt(item.output_tokens) }} · Cache {{ fmt(item.cache_tokens) }}</small></td><td>{{ fmt(item.requests) }}</td><td>{{ fmt(item.total_tokens) }}</td><td>{{ (item.avg_latency_ms / 1000).toFixed(1) }}s</td><td :class="{ bad: item.error_rate > 0 }">{{ Number(item.error_rate).toFixed(1) }}%</td></tr><tr v-if="!data.items.length"><td colspan="5" class="empty">暂无数据</td></tr></tbody></table><footer><span>第 {{ page }}/{{ pageCount }} 页</span><div><button :disabled="page <= 1" @click="page--">上一页</button><button :disabled="page >= pageCount" @click="page++">下一页</button></div></footer></article>
      <article class="panel detail"><div class="panel-title"><div><h2>{{ selected || '请选择项目' }}</h2><p v-if="selectedItem">{{ fmt(selectedItem.total_tokens) }} Token · {{ fmt(selectedItem.requests) }} 次请求</p></div><RouterLink v-if="kind === 'providers' && selected" :to="{ path: '/settings', query: { provider: selected } }">管理配置</RouterLink></div><div ref="chartEl" class="chart"></div></article>
    </section>
    <section class="panel recent"><div class="panel-title"><div><h2>最近请求</h2><p>{{ selected || '尚未选择' }}</p></div></div><div class="table-wrap"><table><thead><tr><th>时间</th><th>Provider</th><th>模型</th><th>Total</th><th>耗时</th><th>状态</th></tr></thead><tbody><tr v-for="item in requests" :key="item.id" class="clickable" @click="detailId = item.id"><td>{{ String(item.created_at).replace('T', ' ').slice(0,19) }}</td><td>{{ item.provider }}</td><td>{{ item.model }}</td><td>{{ fmt(item.total_tokens) }}</td><td>{{ (item.latency_ms / 1000).toFixed(1) }}s</td><td :class="item.success ? 'ok' : 'bad'">{{ item.status_code }}</td></tr><tr v-if="!requests.length"><td colspan="6" class="empty">暂无关联请求</td></tr></tbody></table></div></section>
    <RequestDetailDrawer :record-id="detailId" @close="detailId = null" />
  </div>
</template>

<style scoped>
.analysis-page { max-width: 1540px; margin: 0 auto; color: #475467; transition: opacity .2s; }.loading { opacity: .75; }.page-heading { min-height: 70px; display: flex; justify-content: space-between; }.page-heading h1 { margin: 0; color: #101828; font-size: 22px; }.page-heading p { margin: 7px 0; color: #7b879b; font-size: 13px; }.page-heading > span { height: fit-content; padding: 8px 11px; border: 1px solid #e1e7ef; border-radius: 7px; background: #fff; font-size: 11px; }.panel { border: 1px solid #e6ebf2; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px #1018280a; }.controls { display: flex; gap: 10px; margin-bottom: 14px; padding: 14px; }.controls input { min-width: 260px; flex: 1; }.controls input, .controls select, .controls button, footer button { height: 38px; border: 1px solid #dfe5ed; border-radius: 7px; padding: 0 11px; color: #344054; background: #fff; }.layout { display: grid; grid-template-columns: 1.15fr 1fr; gap: 14px; margin-bottom: 14px; }.ranking { overflow: hidden; }.table-wrap { overflow-x: auto; }table { width: 100%; border-collapse: collapse; white-space: nowrap; font-size: 11px; }th, td { height: 50px; padding: 0 13px; border-bottom: 1px solid #edf1f6; text-align: left; }th { height: 40px; color: #7b879b; background: #fafbfd; font-weight: 550; }.ranking tbody tr { cursor: pointer; }.ranking tbody tr:hover, .ranking tbody tr.selected { background: #f3f7ff; }td b, td small { display: block; }td b { color: #26344d; }td small { margin-top: 4px; color: #98a2b3; font-size: 9px; }.ok { color: #087a55; }.bad { color: #d92d20; }.empty { height: 170px; color: #98a2b3; text-align: center; }.ranking footer { min-height: 54px; display: flex; align-items: center; justify-content: space-between; padding: 8px 13px; color: #7b879b; font-size: 11px; }.ranking footer div { display: flex; gap: 7px; }footer button { height: 31px; }footer button:disabled { opacity: .4; }.detail, .recent { padding: 16px; }.panel-title { display: flex; justify-content: space-between; gap: 12px; }.panel-title h2 { margin: 0; color: #101828; font-size: 15px; }.panel-title p { margin: 5px 0 0; color: #98a2b3; font-size: 10px; }.panel-title a { color: #1769ef; font-size: 11px; text-decoration: none; }.chart { height: 310px; }.recent .table-wrap { margin: 12px -16px -16px; }.clickable { cursor: pointer; }.clickable:hover { background: #f8fbff; }@media(max-width:1000px){.layout{grid-template-columns:1fr}}@media(max-width:600px){.controls{flex-wrap:wrap}.controls input{min-width:100%}.page-heading>span{display:none}}
</style>
