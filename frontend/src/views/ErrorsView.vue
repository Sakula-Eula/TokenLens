<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import ApiStateBanner from "../components/ApiStateBanner.vue";
import RequestDetailDrawer from "../components/RequestDetailDrawer.vue";
import { fetchErrors, fetchRequests } from "../api";

const props = defineProps({
  range: { type: String, default: "24h" },
  autoRefresh: { type: Boolean, default: true },
  refreshInterval: { type: Number, default: 10000 },
});
const route = useRoute(); const router = useRouter();

const stats = ref({ errors: 0, total_requests: 0, error_rate: 0, by_status: [], by_type: [] });
const data = ref({ items: [], total: 0 });
const filters = ref({ provider: String(route.query.provider || ""), model: String(route.query.model || ""), status: String(route.query.status || ""), date_from: String(route.query.date_from || ""), date_to: String(route.query.date_to || "") });
const page = ref(Math.max(1, Number(route.query.page) || 1));
const loading = ref(true);
const loadError = ref("");
const updatedAt = ref(""); const detailId = ref(null);
let timer = null;

const topStatus = computed(() => stats.value.by_status?.[0]?.status_code ?? "—");
const topType = computed(() => stats.value.by_type?.[0]?.error_type || "—");

function fmt(value) { return (Number(value) || 0).toLocaleString("zh-CN"); }
function formatTime(value) { return value ? String(value).replace("T", " ").slice(0, 19) : "—"; }
function dayAfter(value) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + 1);
  return localDate(date);
}
function localDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function rangeStart() {
  const date = new Date();
  props.range === "24h" ? date.setHours(date.getHours() - 24) : date.setDate(date.getDate() - (props.range === "7d" ? 7 : 30));
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 19);
}

async function refresh() {
  const params = { success: false, limit: 50, offset: (page.value - 1) * 50 };
  const statsParams = {};
  if (filters.value.provider) { params.provider_contains = filters.value.provider; statsParams.provider = filters.value.provider; }
  if (filters.value.model) { params.model_contains = filters.value.model; statsParams.model = filters.value.model; }
  if (filters.value.status === "2xx" || filters.value.status === "4xx" || filters.value.status === "5xx") { params.status_group = filters.value.status; statsParams.status_group = filters.value.status; }
  else if (filters.value.status) { params.status = Number(filters.value.status); statsParams.status = Number(filters.value.status); }
  params.date_from = filters.value.date_from || rangeStart();
  if (filters.value.date_from) statsParams.date_from = filters.value.date_from;
  if (filters.value.date_to) { params.date_to = dayAfter(filters.value.date_to); statsParams.date_to = params.date_to; }
  try {
    const [statsData, requestsData] = await Promise.all([fetchErrors(props.range, statsParams), fetchRequests(params)]);
    stats.value = statsData;
    data.value = requestsData;
    loadError.value = "";
    updatedAt.value = new Date().toLocaleTimeString("zh-CN", { hour12: false }); syncQuery();
  } catch (error) {
    loadError.value = error?.response?.data?.detail || "错误数据加载失败，请稍后重试";
  } finally { loading.value = false; }
}

function resetFilters() {
  filters.value = { provider: "", model: "", status: "", date_from: "", date_to: "" };
}
function syncQuery() { const query = { ...filters.value }; for (const key of Object.keys(query)) if (!query[key]) delete query[key]; if (page.value > 1) query.page = String(page.value); router.replace({ query }); }
function configureTimer() {
  clearInterval(timer);
  timer = props.autoRefresh ? setInterval(refresh, props.refreshInterval) : null;
}

onMounted(() => { refresh(); configureTimer(); });
onBeforeUnmount(() => clearInterval(timer));
watch(filters, () => { page.value = 1; refresh(); }, { deep: true });
watch(page, refresh);
watch(() => props.range, () => { page.value = 1; refresh(); });
watch(() => [props.autoRefresh, props.refreshInterval], configureTimer);
defineExpose({ refresh });
</script>

<template>
  <div class="errors-page" :class="{ loading }">
    <div class="page-heading">
      <div><h1>错误监控</h1><p>定位失败请求、状态码和上游错误类型</p></div>
      <span class="period-label">当前周期：{{ range === '24h' ? '最近24小时' : range === '7d' ? '最近7天' : '最近30天' }}</span>
    </div>

    <ApiStateBanner :error="loadError" :updated-at="updatedAt" />
    <section class="metric-grid">
      <article><span>错误请求</span><b>{{ fmt(stats.errors) }}</b></article>
      <article><span>错误率</span><b>{{ Number(stats.error_rate || 0).toFixed(2) }}%</b></article>
      <article><span>主要状态码</span><b>{{ topStatus }}</b></article>
      <article><span>主要错误类型</span><b class="type-value">{{ topType }}</b></article>
    </section>

    <section class="breakdown-grid">
      <article class="panel"><h2>状态码分布</h2><div class="chips"><span v-for="item in stats.by_status" :key="item.status_code"><b>{{ item.status_code }}</b>{{ fmt(item.count) }} 次</span><em v-if="!stats.by_status?.length">暂无错误</em></div></article>
      <article class="panel"><h2>错误类型分布</h2><div class="chips"><span v-for="item in stats.by_type" :key="item.error_type"><b>{{ item.error_type || 'unknown' }}</b>{{ fmt(item.count) }} 次</span><em v-if="!stats.by_type?.length">暂无错误</em></div></article>
    </section>

    <section class="panel request-panel">
      <div class="filters">
        <label><span>供应商</span><input v-model.trim="filters.provider" placeholder="输入 Provider" /></label>
        <label><span>模型</span><input v-model.trim="filters.model" placeholder="输入模型名称" /></label>
        <label><span>状态码</span><select v-model="filters.status"><option value="">全部错误</option><option value="4xx">全部 4xx</option><option value="5xx">全部 5xx</option><option v-for="code in [400,401,403,404,408,429,500,502,503,504]" :key="code" :value="String(code)">{{ code }}</option></select></label>
        <label><span>开始日期</span><input v-model="filters.date_from" type="date" :max="filters.date_to || undefined" /></label>
        <label><span>结束日期</span><input v-model="filters.date_to" type="date" :min="filters.date_from || undefined" /></label>
        <button type="button" @click="resetFilters">重置</button>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>时间</th><th>Provider</th><th>模型</th><th>请求 ID</th><th>接口</th><th>模式</th><th>状态</th><th>错误类型</th><th>耗时</th></tr></thead>
        <tbody>
          <tr v-for="item in data.items" :key="item.id" class="clickable" @click="detailId = item.id"><td>{{ formatTime(item.created_at) }}</td><td>{{ item.provider }}</td><td>{{ item.model || 'unknown' }}</td><td class="mono">{{ item.request_id }}</td><td class="mono">{{ item.endpoint }}</td><td>{{ item.stream ? '流式' : '非流式' }}</td><td><span class="status">{{ item.status_code }}</span></td><td>{{ item.error_type || 'unknown' }}</td><td>{{ (item.latency_ms / 1000).toFixed(1) }}s</td></tr>
          <tr v-if="!data.items.length"><td colspan="9" class="empty">{{ loading ? '正在加载错误记录…' : '当前条件下没有错误记录' }}</td></tr>
        </tbody>
      </table></div>
      <footer><span>共 {{ fmt(data.total) }} 条 · 第 {{ page }} 页</span><div><button :disabled="page <= 1" @click="page--">上一页</button><button :disabled="page * 50 >= data.total" @click="page++">下一页</button></div></footer>
    </section>
    <RequestDetailDrawer :record-id="detailId" @close="detailId = null" />
  </div>
</template>

<style scoped>
.errors-page { max-width: 1540px; margin: 0 auto; color: #344054; transition: opacity .2s; }.loading { opacity: .75; }.page-heading { min-height: 70px; display: flex; justify-content: space-between; gap: 16px; }.page-heading h1 { margin: 0; color: #101828; font-size: 22px; }.page-heading p { margin: 7px 0 0; color: #7b879b; font-size: 13px; }.period-label { height: fit-content; padding: 9px 12px; border: 1px solid #dfe5ed; border-radius: 8px; background: #fff; color: #667085; font-size: 12px; }.error-banner { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; padding: 11px 14px; border: 1px solid #fecaca; border-radius: 8px; color: #b42318; background: #fff1f1; font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }.metric-grid article, .panel { border: 1px solid #e6ebf2; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(16,24,40,.035); }.metric-grid article { min-height: 105px; display: grid; align-content: center; gap: 8px; padding: 18px; }.metric-grid span { color: #667085; font-size: 12px; }.metric-grid b { color: #d92d20; font-size: 25px; }.metric-grid .type-value { overflow: hidden; color: #344054; font-size: 18px; text-overflow: ellipsis; white-space: nowrap; }
.breakdown-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }.panel { overflow: hidden; }.breakdown-grid .panel { min-height: 125px; padding: 17px; }.panel h2 { margin: 0 0 14px; color: #101828; font-size: 15px; }.chips { display: flex; flex-wrap: wrap; gap: 8px; }.chips span { display: flex; gap: 8px; padding: 7px 10px; border-radius: 7px; color: #667085; background: #f8fafc; font-size: 11px; }.chips b { color: #d92d20; }.chips em { color: #98a2b3; font-size: 12px; font-style: normal; }
.filters { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 12px; padding: 18px; border-bottom: 1px solid #edf1f6; }.filters label { min-width: 145px; display: grid; flex: 1; gap: 7px; color: #667085; font-size: 11px; }.filters input, .filters select, .filters button, footer button { height: 38px; border: 1px solid #dfe5ed; border-radius: 7px; padding: 0 11px; color: #344054; background: #fff; }.filters button { flex: 0 0 auto; color: #1769ef; }.table-wrap { overflow-x: auto; }table { width: 100%; border-collapse: collapse; white-space: nowrap; font-size: 11px; }th, td { height: 48px; padding: 0 13px; border-bottom: 1px solid #edf1f6; text-align: left; }th { height: 42px; color: #7b879b; background: #fafbfd; font-weight: 550; }.mono { max-width: 190px; overflow: hidden; font-family: ui-monospace, Consolas, monospace; text-overflow: ellipsis; }.status { padding: 4px 8px; border-radius: 6px; color: #b42318; background: #fff0f0; }.clickable { cursor: pointer; }.clickable:hover { background: #fffafa; }.empty { height: 220px; color: #98a2b3; text-align: center; }footer { min-height: 58px; display: flex; align-items: center; justify-content: space-between; padding: 10px 18px; color: #7b879b; font-size: 11px; }footer div { display: flex; gap: 8px; }footer button { height: 32px; }footer button:disabled { opacity: .45; cursor: not-allowed; }
@media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, 1fr); }.breakdown-grid { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .metric-grid { grid-template-columns: 1fr 1fr; }.page-heading { min-height: 95px; }.period-label { display: none; }.filters label { min-width: 100%; } }
</style>
