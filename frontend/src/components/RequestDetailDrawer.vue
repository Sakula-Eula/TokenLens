<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import ModelIcon from "./ModelIcon.vue";
import { fetchRequestDetail } from "../api";

const props = defineProps({ recordId: { type: Number, default: null } });
const emit = defineEmits(["close"]);
const item = ref(null);
const loading = ref(false);
const error = ref("");

function close() { emit("close"); }
function onKey(event) { if (event.key === "Escape" && props.recordId != null) close(); }

watch(() => props.recordId, async (id) => {
  if (id == null) { item.value = null; return; }
  loading.value = true; error.value = "";
  try { item.value = await fetchRequestDetail(id); }
  catch (exc) { error.value = exc?.response?.data?.detail || "请求详情加载失败"; }
  finally { loading.value = false; }
}, { immediate: true });

window.addEventListener("keydown", onKey);
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));

function fmt(value) { return (Number(value) || 0).toLocaleString("zh-CN"); }
function money(value) { return `¥${(Number(value || 0) / 1_000_000).toFixed(6)}`; }
</script>

<template>
  <Teleport to="body"><div v-if="recordId != null" class="drawer-shell" role="presentation" @mousedown.self="close">
    <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="request-detail-title">
      <header><div><h2 id="request-detail-title">请求详情</h2><p>仅展示调用元数据，不包含 Prompt 或回答内容</p></div><button type="button" aria-label="关闭" @click="close">×</button></header>
      <div v-if="loading" class="state">正在加载…</div><div v-else-if="error" class="state error">{{ error }}</div>
      <dl v-else-if="item">
        <div><dt>Request ID</dt><dd class="mono">{{ item.request_id || '—' }}</dd></div><div><dt>数据库 ID</dt><dd>{{ item.id }}</dd></div>
        <div><dt>Provider</dt><dd>{{ item.provider }}</dd></div><div><dt>模型</dt><dd class="model-name"><ModelIcon :model="item.model" :provider="item.provider" :size="25" />{{ item.model || 'unknown' }}</dd></div>
        <div class="wide"><dt>Endpoint</dt><dd class="mono">{{ item.endpoint || '—' }}</dd></div>
        <div><dt>调用模式</dt><dd>{{ item.stream ? '流式' : '非流式' }}</dd></div><div><dt>创建时间</dt><dd>{{ String(item.created_at).replace('T', ' ') }}</dd></div>
        <div><dt>Input Token</dt><dd>{{ fmt(item.input_tokens) }}</dd></div><div><dt>Output Token</dt><dd>{{ fmt(item.output_tokens) }}</dd></div>
        <div><dt>Cache Read</dt><dd>{{ fmt(item.cache_read_tokens) }}</dd></div>
        <div><dt>Total Token</dt><dd>{{ fmt(item.total_tokens) }}</dd></div><div><dt>耗时</dt><dd>{{ (Number(item.latency_ms || 0) / 1000).toFixed(2) }}s</dd></div>
        <div><dt>状态码</dt><dd :class="item.success ? 'success' : 'failure'">{{ item.status_code }}</dd></div><div><dt>结果</dt><dd :class="item.success ? 'success' : 'failure'">{{ item.success ? '成功' : '失败' }}</dd></div>
        <div class="wide"><dt>Error Type</dt><dd class="failure">{{ item.error_type || '—' }}</dd></div>
        <template v-if="item.cost"><div class="wide cost-title"><dt>费用快照</dt><dd :class="item.cost.priced ? 'success' : 'failure'">{{ item.cost.priced ? item.cost.rule_name : '未定价，费用按 ¥0 统计' }}</dd></div><div><dt>Input 单价 / 费用</dt><dd>{{ money(item.cost.input_price_micros) }} / MTok · {{ money(item.cost.input_cost_micros) }}</dd></div><div><dt>Output 单价 / 费用</dt><dd>{{ money(item.cost.output_price_micros) }} / MTok · {{ money(item.cost.output_cost_micros) }}</dd></div><div><dt>Cache Read 单价 / 费用</dt><dd>{{ money(item.cost.cache_read_price_micros) }} / MTok · {{ money(item.cost.cache_read_cost_micros) }}</dd></div><div class="wide"><dt>总费用</dt><dd><strong>{{ money(item.cost.total_cost_micros) }}</strong></dd></div></template>
      </dl>
    </aside>
  </div></Teleport>
</template>

<style scoped>
.drawer-shell { position: fixed; inset: 0; z-index: 100; display: flex; justify-content: flex-end; background: rgba(15,23,42,.28); backdrop-filter: blur(2px); }.drawer { width: min(560px, 94vw); height: 100%; overflow-y: auto; padding: 22px; background: #fff; box-shadow: -12px 0 36px #10182824; }.drawer header { display: flex; justify-content: space-between; gap: 20px; padding-bottom: 18px; border-bottom: 1px solid #e8edf4; }.drawer h2 { margin: 0; color: #101828; font-size: 19px; }.drawer p { margin: 5px 0 0; color: #98a2b3; font-size: 11px; }.drawer header button { width: 34px; height: 34px; border: 0; border-radius: 7px; color: #667085; background: #f4f6f8; font-size: 22px; }.state { min-height: 300px; display: grid; place-items: center; color: #667085; }.state.error { color: #b42318; }dl { display: grid; grid-template-columns: 1fr 1fr; gap: 0; margin: 18px 0; border: 1px solid #e8edf4; border-radius: 9px; }dl div { min-width: 0; padding: 13px; border-bottom: 1px solid #edf1f6; }.wide { grid-column: 1 / -1; }dt { margin-bottom: 5px; color: #98a2b3; font-size: 10px; }dd { margin: 0; overflow-wrap: anywhere; color: #344054; font-size: 12px; }.model-name { display: flex; align-items: center; gap: 8px; }.mono { font-family: ui-monospace, Consolas, monospace; }.success { color: #087a55; }.failure { color: #b42318; }@media(max-width:520px){dl{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
