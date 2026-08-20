<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import ApiStateBanner from "../components/ApiStateBanner.vue";
import RequestDetailDrawer from "../components/RequestDetailDrawer.vue";
import { fetchRequests } from "../api";

const props = defineProps({ autoRefresh: { type: Boolean, default: true }, refreshInterval: { type: Number, default: 10000 } });
const route = useRoute(); const router = useRouter();
const filters = ref({ provider: String(route.query.provider || ""), model: String(route.query.model || ""), status: String(route.query.status || ""), date_from: String(route.query.date_from || ""), date_to: String(route.query.date_to || "") });
const page = ref(Math.max(1, Number(route.query.page) || 1));
const data = ref({ items: [], total: 0 });
const loading = ref(true);
const error = ref(""); const updatedAt = ref(""); const detailId = ref(null);
let timer = null;

async function refresh() {
  const params = { limit: 50, offset: (page.value - 1) * 50 };
  if (filters.value.provider) params.provider_contains = filters.value.provider;
  if (filters.value.model) params.model_contains = filters.value.model;
  if (filters.value.date_from) params.date_from = filters.value.date_from;
  if (filters.value.date_to) params.date_to = dayAfter(filters.value.date_to);
  if (filters.value.status === "success") params.success = true;
  else if (filters.value.status === "failed") params.success = false;
  else if (/^[245]xx$/.test(filters.value.status)) params.status_group = filters.value.status;
  else if (filters.value.status) params.status = Number(filters.value.status);
  try { data.value = await fetchRequests(params); error.value = ""; updatedAt.value = new Date().toLocaleTimeString("zh-CN", { hour12: false }); syncQuery(); }
  catch (exc) { error.value = exc?.response?.data?.detail || "请求记录更新失败"; }
  finally { loading.value = false; }
}

function resetFilters() {
  filters.value = { provider: "", model: "", status: "", date_from: "", date_to: "" };
}
function syncQuery() {
  const query = { ...filters.value };
  for (const key of Object.keys(query)) if (!query[key]) delete query[key];
  if (page.value > 1) query.page = String(page.value);
  router.replace({ query });
}

function configureTimer() {
  clearInterval(timer);
  timer = props.autoRefresh ? setInterval(refresh, props.refreshInterval) : null;
}

function fmt(value) { return (Number(value) || 0).toLocaleString("zh-CN"); }
function formatTime(value) { return value ? String(value).replace("T", " ").slice(0, 19) : "—"; }
function dayAfter(value) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + 1);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

onMounted(() => { refresh(); configureTimer(); });
onBeforeUnmount(() => clearInterval(timer));
watch(filters, () => { page.value = 1; refresh(); }, { deep: true });
watch(page, refresh);
watch(() => [props.autoRefresh, props.refreshInterval], configureTimer);
defineExpose({ refresh });
</script>

<template>
  <div class="requests-page" :class="{ loading }">
    <div class="page-heading">
      <div><h1>请求记录</h1><p>查看和筛选所有 API 调用记录</p></div>
      <div class="request-count"><AppIcon name="request" :size="18" /><span>共 <b>{{ fmt(data.total) }}</b> 条</span></div>
    </div>
    <ApiStateBanner :error="error" :updated-at="updatedAt" />

    <section class="request-panel">
      <div class="filters">
        <label><span>供应商</span><input v-model.trim="filters.provider" placeholder="输入 Provider" /></label>
        <label><span>模型</span><input v-model.trim="filters.model" placeholder="输入模型名称" /></label>
        <label><span>状态</span><select v-model="filters.status"><option value="">全部状态</option><option value="success">全部成功</option><option value="failed">全部失败</option><option value="2xx">全部 2xx</option><option value="4xx">全部 4xx</option><option value="5xx">全部 5xx</option><option v-for="code in [200, 400, 401, 403, 404, 408, 429, 500, 502, 503, 504]" :key="code" :value="String(code)">{{ code }}</option></select></label>
        <label><span>开始日期</span><input v-model="filters.date_from" type="date" :max="filters.date_to || undefined" /></label>
        <label><span>结束日期</span><input v-model="filters.date_to" type="date" :min="filters.date_from || undefined" /></label>
        <button class="reset-button" type="button" @click="resetFilters"><AppIcon name="refresh" :size="15" />重置</button>
      </div>

      <div class="table-wrap">
        <table>
          <thead><tr><th>时间</th><th>Provider</th><th>模型</th><th>输入 Token</th><th>输出 Token</th><th>Cache Token</th><th>总 Token</th><th>耗时</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="item in data.items" :key="item.id" class="clickable" @click="detailId = item.id">
              <td class="time-cell">{{ formatTime(item.created_at) }}</td><td><span class="provider-badge">{{ item.provider }}</span></td><td class="model-cell">{{ item.model || "unknown" }}</td><td>{{ fmt(item.input_tokens) }}</td><td>{{ fmt(item.output_tokens) }}</td><td>{{ fmt((item.cache_read_tokens || 0) + (item.cache_write_tokens || 0)) }}</td><td class="total-cell">{{ fmt(item.total_tokens) }}</td><td>{{ (item.latency_ms / 1000).toFixed(1) }}s</td>
              <td><span class="status" :class="item.success ? 'success' : 'error'"><i></i>{{ item.success ? "成功" : item.status_code }}</span></td>
            </tr>
            <tr v-if="!data.items.length"><td colspan="9" class="empty-cell">{{ loading ? "正在加载请求记录…" : "没有符合条件的请求记录" }}</td></tr>
          </tbody>
        </table>
      </div>

      <footer class="pagination">
        <span>第 {{ page }} 页 · 每页 50 条</span>
        <div><button type="button" :disabled="page <= 1" @click="page--">上一页</button><button type="button" :disabled="page * 50 >= data.total" @click="page++">下一页</button></div>
      </footer>
    </section>
    <RequestDetailDrawer :record-id="detailId" @close="detailId = null" />
  </div>
</template>

<style scoped>
.requests-page { max-width: 1540px; margin: 0 auto; transition: opacity .2s; }.requests-page.loading { opacity: .75; }
.page-heading { min-height: 70px; display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }.page-heading h1 { margin: 0; font-size: 22px; letter-spacing: -.3px; }.page-heading p { margin: 7px 0 0; color: #7b879b; font-size: 13px; }
.request-count { display: flex; align-items: center; gap: 8px; padding: 9px 13px; border: 1px solid #e2e7ee; border-radius: 8px; color: #667085; background: #fff; font-size: 12px; }.request-count .app-icon { color: #2476f5; }.request-count b { color: #101828; }
.request-panel { overflow: hidden; border: 1px solid #e6ebf2; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(16,24,40,.035); }
.filters { display: flex; align-items: flex-end; gap: 14px; padding: 18px; border-bottom: 1px solid #edf1f6; }.filters label { min-width: 160px; display: grid; gap: 7px; color: #667085; font-size: 11px; }.filters input, .filters select { height: 38px; border: 1px solid #dfe5ed; border-radius: 7px; padding: 0 11px; color: #344054; outline: none; background: #fff; }.filters input:focus, .filters select:focus { border-color: #8db6f7; box-shadow: 0 0 0 3px #2677f412; }.reset-button { height: 38px; display: flex; align-items: center; gap: 6px; border: 1px solid #dfe5ed; border-radius: 7px; padding: 0 14px; color: #667085; background: #fff; }.reset-button:hover { color: #1769ef; border-color: #a9c7f8; }
.table-wrap { width: 100%; overflow-x: auto; }table { width: 100%; border-collapse: collapse; color: #475467; font-size: 12px; white-space: nowrap; }th { height: 42px; color: #7b879b; background: #fafbfd; font-weight: 550; text-align: left; }td { height: 52px; border-top: 1px solid #edf1f6; }th, td { padding: 0 15px; }.time-cell { color: #667085; }.model-cell, .total-cell { color: #26344d; font-weight: 650; }.provider-badge { display: inline-flex; padding: 4px 8px; border-radius: 5px; color: #1769ef; background: #edf4ff; }.status { display: inline-flex; align-items: center; gap: 6px; }.status i { width: 6px; height: 6px; border-radius: 50%; }.status.success { color: #138a62; }.status.success i { background: #20b77a; }.status.error { color: #df3030; }.status.error i { background: #ef4444; }.empty-cell { height: 260px; color: #98a2b3; text-align: center; }
.clickable { cursor: pointer; }.clickable:hover { background: #f8fbff; }
.pagination { min-height: 58px; display: flex; align-items: center; justify-content: space-between; gap: 15px; padding: 10px 18px; border-top: 1px solid #edf1f6; color: #7b879b; font-size: 11px; }.pagination div { display: flex; gap: 8px; }.pagination button { height: 32px; border: 1px solid #dfe5ed; border-radius: 6px; padding: 0 13px; color: #344054; background: #fff; }.pagination button:hover:not(:disabled) { color: #1769ef; border-color: #a9c7f8; }.pagination button:disabled { opacity: .45; cursor: not-allowed; }
@media (max-width: 760px) { .filters { flex-wrap: wrap; }.filters label { min-width: calc(50% - 8px); flex: 1; }.reset-button { margin-left: auto; }.page-heading { min-height: 86px; }.request-count { padding: 8px; } }
@media (max-width: 480px) { .filters label { min-width: 100%; }.page-heading p { font-size: 11px; }.request-count span { display: none; }.pagination { align-items: flex-start; flex-direction: column; } }
</style>
