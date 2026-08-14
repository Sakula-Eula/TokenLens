<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import { POLL_INTERVAL_MS, fetchModels, fetchProviders, fetchSummary, fetchTrend } from "../api";

const summary = ref({ requests: 0, total_tokens: 0, input_tokens: 0, output_tokens: 0, errors: 0, error_rate: 0, avg_latency_ms: 0 });
const models = ref([]);
const providers = ref([]);
const range = ref("24h");
const chartEl = ref(null);
let chart = null;
let timer = null;

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

async function refresh() {
  try {
    summary.value = await fetchSummary();
    models.value = (await fetchModels()).items;
    providers.value = (await fetchProviders()).items;
    const trend = await fetchTrend(range.value);
    chart.setOption({
      xAxis: { type: "category", data: trend.items.map((t) => t.bucket) },
      yAxis: { type: "value" },
      series: [{ type: "line", smooth: true, areaStyle: {}, data: trend.items.map((t) => t.total_tokens) }],
      tooltip: { trigger: "axis" },
    });
  } catch { /* Keep the last successful data visible if polling fails. */ }
}

function maxTokens(list) {
  return Math.max(1, ...list.map((x) => x.total_tokens));
}

onMounted(() => {
  chart = echarts.init(chartEl.value);
  refresh();
  timer = setInterval(refresh, POLL_INTERVAL_MS);
});
onBeforeUnmount(() => {
  clearInterval(timer);
  chart.dispose();
});
watch(range, refresh);
</script>

<template>
  <div>
    <div class="cards">
      <div class="card"><div class="label">今日请求数</div><div class="value">{{ summary.requests }}</div></div>
      <div class="card"><div class="label">今日 Token</div><div class="value">{{ fmt(summary.total_tokens) }}</div></div>
      <div class="card"><div class="label">Input Token</div><div class="value">{{ fmt(summary.input_tokens) }}</div></div>
      <div class="card"><div class="label">Output Token</div><div class="value">{{ fmt(summary.output_tokens) }}</div></div>
      <div class="card"><div class="label">今日错误</div><div class="value">{{ summary.errors }}（{{ summary.error_rate }}%）</div></div>
      <div class="card"><div class="label">平均耗时</div><div class="value">{{ (summary.avg_latency_ms / 1000).toFixed(1) }}s</div></div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2>Token Trend</h2>
        <select v-model="range">
          <option value="24h">最近 24 小时</option>
          <option value="7d">最近 7 天</option>
          <option value="30d">最近 30 天</option>
        </select>
      </div>
      <div ref="chartEl" style="height: 260px"></div>
    </div>

    <div class="panel">
      <h2>Model Usage</h2>
      <div v-for="m in models" :key="m.model" class="bar-row">
        <span class="bar-name">{{ m.model }}</span>
        <div class="bar-track"><div class="bar-fill" :style="{ width: (m.total_tokens / maxTokens(models) * 100) + '%' }"></div></div>
        <span class="bar-value">{{ fmt(m.total_tokens) }}</span>
      </div>
    </div>

    <div class="panel">
      <h2>Provider Usage</h2>
      <div v-for="p in providers" :key="p.provider" class="bar-row">
        <span class="bar-name">{{ p.provider }}</span>
        <div class="bar-track"><div class="bar-fill provider" :style="{ width: (p.total_tokens / maxTokens(providers) * 100) + '%' }"></div></div>
        <span class="bar-value">{{ fmt(p.total_tokens) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 16px; }
.card { background: #fff; border-radius: 8px; padding: 12px; }
.label { color: #6b7280; font-size: 12px; }
.value { font-size: 20px; font-weight: 600; margin-top: 4px; }
.panel { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; }
h2 { font-size: 15px; margin: 0 0 12px; }
.bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.bar-name { width: 160px; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; background: #e5e7eb; border-radius: 4px; height: 12px; }
.bar-fill { background: #2563eb; border-radius: 4px; height: 12px; }
.bar-fill.provider { background: #059669; }
.bar-value { width: 80px; text-align: right; font-size: 13px; }
</style>
