<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import ModelIcon from "../components/ModelIcon.vue";
import TrayIcon from "../components/TrayIcon.vue";
import { POLL_INTERVAL_MS, fetchCostSummary, fetchModels, fetchSummary, fetchTrend } from "../api";

const brandAssets = import.meta.glob("../../../assets/{icon,tokenlens}.png", {
  eager: true,
  query: "?url",
  import: "default",
});
const logoUrl = brandAssets["../../../assets/icon.png"];
const wordmarkUrl = brandAssets["../../../assets/tokenlens.png"];

const summary = ref({ requests: 0, total_tokens: 0, avg_latency_ms: 0 });
const models = ref([]);
const trendItems = ref([]);
const costSummary = ref({ total_cost_micros: 0 });
const refreshing = ref(false);
const activeRange = ref("24h");
const pinned = ref(false);
const lastUpdated = ref(null);
let timer = null;

const ranges = [
  { value: "1h", label: "1H" },
  { value: "6h", label: "6H" },
  { value: "24h", label: "今日" },
  { value: "7d", label: "7D" },
];

const totalTokens = computed(() => Number(summary.value.total_tokens) || 0);
const estimatedCost = computed(() => Number(costSummary.value.total_cost_micros || 0) / 1_000_000);
const topModels = computed(() => models.value.slice(0, 3).map((item) => {
  const inputTokens = Math.max(0, Number(item.input_tokens) || 0);
  // Cache-read tokens are already included in input_tokens.  Split input into
  // mutually exclusive cache-hit and cache-miss portions before rendering.
  const cacheHitTokens = Math.min(inputTokens, Math.max(0, Number(item.cache_read_tokens) || 0));
  const parts = [
    { key: "cache-hit", value: cacheHitTokens, color: "#8061ee" },
    { key: "input-miss", value: inputTokens - cacheHitTokens, color: "#1673ed" },
    { key: "output", value: Number(item.output_tokens || 0), color: "#0aa36e" },
  ];
  const partTotal = Math.max(1, parts.reduce((sum, part) => sum + part.value, 0));
  return {
    ...item,
    cache_hit_tokens: cacheHitTokens,
    input_miss_tokens: inputTokens - cacheHitTokens,
    parts: parts.map((part) => ({ ...part, percent: Math.round(part.value / partTotal * 100) })),
  };
}));

const chart = computed(() => {
  const items = trendItems.value;
  const left = 39;
  const right = 424;
  const top = 8;
  const bottom = 91;
  const plotHeight = bottom - top;
  const plotWidth = right - left;
  const partsFor = (item) => {
    const input = Math.max(0, Number(item.input_tokens) || 0);
    const cacheHit = Math.min(input, Math.max(0, Number(item.cache_read_tokens) || 0));
    return [
      { label: "缓存未命中输入", value: input - cacheHit, color: "#1673ed" },
      { label: "缓存命中输入", value: cacheHit, color: "#8061ee" },
      { label: "输出", value: Math.max(0, Number(item.output_tokens) || 0), color: "#0aa36e" },
    ];
  };
  const totals = items.map((item) => partsFor(item).reduce((sum, part) => sum + part.value, 0));
  const maxValue = Math.max(1, ...totals);
  const magnitude = 10 ** Math.max(0, Math.floor(Math.log10(maxValue)));
  const axisMax = Math.max(magnitude, Math.ceil(maxValue / magnitude) * magnitude);
  const barWidth = Math.min(16, Math.max(5, plotWidth / Math.max(items.length, 1) * .68));
  const bars = items.map((item, index) => {
    const center = left + (index + .5) / Math.max(items.length, 1) * plotWidth;
    let cursorY = bottom;
    const parts = partsFor(item).map((part) => {
      const height = part.value / axisMax * plotHeight;
      cursorY -= height;
      return { ...part, y: cursorY, height };
    });
    return { x: center - barWidth / 2, center, width: barWidth, item, parts };
  });
  const labelIndexes = [...new Set([0, Math.floor((items.length - 1) / 3), Math.floor((items.length - 1) * 2 / 3), items.length - 1])].filter((index) => index >= 0);
  return {
    axisMax,
    bars,
    labels: labelIndexes.map((index) => ({ x: bars[index]?.center || left, text: formatBucket(items[index]?.bucket, index === items.length - 1) })),
  };
});
const updatedText = computed(() => {
  if (!lastUpdated.value) return "等待首次更新";
  const seconds = Math.max(0, Math.floor((Date.now() - lastUpdated.value.getTime()) / 1000));
  if (seconds < 60) return "数据更新于刚刚";
  return `数据更新于 ${Math.floor(seconds / 60)} 分钟前`;
});

function fmt(value) {
  const number = Number(value) || 0;
  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(number >= 10_000_000 ? 0 : 1)}M`;
  if (number >= 1_000) return `${(number / 1_000).toFixed(number >= 100_000 ? 0 : 1)}K`;
  return number.toLocaleString("zh-CN");
}

function formatBucket(bucket, isLast = false) {
  if (!bucket) return "";
  if (isLast && activeRange.value !== "7d") return "现在";
  if (bucket.length === 10) return bucket.slice(5).replace("-", "/");
  return `${bucket.slice(11, 13)}:00`;
}

function bucketDate(bucket) {
  if (!bucket) return null;
  const value = bucket.length === 10 ? `${bucket}T00:00:00` : `${bucket}:00:00`;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function filterTrend(items, range) {
  if (range === "24h" || range === "7d") return items;
  const hours = range === "1h" ? 1 : 6;
  const cutoff = Date.now() - hours * 60 * 60 * 1000;
  const filtered = items.filter((item) => (bucketDate(item.bucket)?.getTime() || 0) >= cutoff);
  if (filtered.length) return filtered;
  return items.slice(-(hours + 1));
}

function nativeApi() { return window.pywebview?.api; }

function openDashboard(path = "/dashboard") {
  const api = nativeApi();
  if (api) api.open_dashboard(path);
  else window.location.href = path;
}

function closeWidget() {
  const api = nativeApi();
  if (api) api.close_widget();
  else window.close();
}

function togglePinned() {
  pinned.value = !pinned.value;
  nativeApi()?.set_widget_pinned(pinned.value);
}

function reportPointer(inside) {
  const api = nativeApi();
  if (inside) api?.widget_pointer_enter();
  else api?.widget_pointer_leave();
}

async function loadTrend(range) {
  const apiRange = range === "7d" ? "7d" : "24h";
  const data = await fetchTrend(apiRange);
  trendItems.value = filterTrend(data.items || [], range);
}

async function selectRange(range) {
  if (range === activeRange.value) return;
  activeRange.value = range;
  try { await loadTrend(range); } catch { /* Keep the last successful chart visible. */ }
}

async function refresh() {
  if (refreshing.value) return;
  refreshing.value = true;
  try {
    const [summaryData, modelData, costData] = await Promise.all([
      fetchSummary("24h"),
      fetchModels("24h", { limit: 3 }),
      fetchCostSummary("today"),
      loadTrend(activeRange.value),
    ]);
    summary.value = summaryData;
    models.value = modelData.items || [];
    costSummary.value = costData;
    lastUpdated.value = new Date();
  } catch { /* Keep the last successful data visible. */ }
  finally { refreshing.value = false; }
}

onMounted(() => { refresh(); timer = setInterval(refresh, POLL_INTERVAL_MS); });
onBeforeUnmount(() => clearInterval(timer));
</script>

<template>
  <div class="tray-page" @mouseenter="reportPointer(true)" @mouseleave="reportPointer(false)">
    <header class="tray-header">
      <div class="tray-brand"><button type="button" class="logo-box" aria-label="查看详情" @click="openDashboard('/dashboard')"><img :src="logoUrl" alt="TokenLens" /></button><img class="wordmark" :src="wordmarkUrl" alt="TokenLens" /></div>
      <div class="header-actions">
        <button type="button" aria-label="刷新" title="刷新" @click="refresh"><TrayIcon name="refresh" :size="20" :class="{ spinning: refreshing }" /></button>
        <button type="button" aria-label="固定" title="固定" :class="{ selected: pinned }" @click="togglePinned"><TrayIcon name="pin" :size="20" /></button>
        <button type="button" aria-label="设置" title="设置" @click="openDashboard('/settings')"><TrayIcon name="settings" :size="20" /></button>
        <button type="button" aria-label="关闭" title="关闭" @click="closeWidget"><TrayIcon name="close" :size="20" /></button>
      </div>
    </header>

    <section class="overview card">
      <div class="metrics">
        <article><span class="metric-symbol purple"><TrayIcon name="coins" :size="11" /></span><strong>{{ fmt(totalTokens) }}</strong></article>
        <article><span class="metric-symbol orange"><TrayIcon name="wallet" :size="10" /></span><strong>¥{{ estimatedCost.toFixed(2) }}</strong></article>
        <article><span class="metric-symbol green"><TrayIcon name="send" :size="10" /></span><strong>{{ fmt(summary.requests) }}</strong></article>
        <article><span class="metric-symbol blue"><TrayIcon name="clock" :size="10" /></span><strong>{{ (Number(summary.avg_latency_ms || 0) / 1000).toFixed(1) }}s</strong></article>
      </div>
    </section>

    <section class="ranking card">
      <header class="ranking-heading"><h2>模型使用量（Top 3）</h2><button type="button" @click="openDashboard('/models')">全部模型 <TrayIcon name="chevron" :size="14" /></button></header>
      <div class="legend"><span class="cache">缓存命中</span><span class="input">未命中输入</span><span class="output">输出</span><small>总 Token</small></div>
      <div class="model-list">
        <article v-for="model in topModels" :key="model.model" class="model-row">
          <ModelIcon class="model-logo" :model="model.model" :provider="model.provider" :size="31" />
          <div class="model-main">
            <div class="model-title"><strong>{{ model.model }}</strong><b>{{ fmt(model.total_tokens) }}</b></div>
            <div class="segmented-bar"><i v-for="part in model.parts" :key="part.key" :style="{ width: `${part.percent}%`, background: part.color }"><span v-if="part.percent >= 18">{{ part.percent }}%</span></i></div>
            <div class="model-meta"><span class="cache">命中 {{ fmt(model.cache_hit_tokens) }}</span><span class="input">未命中 {{ fmt(model.input_miss_tokens) }}</span><span class="output">输出 {{ fmt(model.output_tokens) }}</span></div>
          </div>
        </article>
        <div v-if="!topModels.length" class="empty-models">暂无模型使用数据</div>
      </div>
    </section>

    <section class="trend-card card">
      <header>
        <h2>Token 趋势</h2>
        <div class="range-tabs">
          <button v-for="range in ranges" :key="range.value" type="button" :class="{ active: activeRange === range.value }" @click="selectRange(range.value)">{{ range.label }}</button>
        </div>
      </header>
      <svg class="trend-chart" viewBox="0 0 435 122" role="img" aria-label="缓存命中输入、未命中输入和输出构成的 Token 趋势堆叠柱状图">
        <g class="grid-lines"><line x1="39" y1="8" x2="424" y2="8" /><line x1="39" y1="49.5" x2="424" y2="49.5" /><line x1="39" y1="91" x2="424" y2="91" /></g>
        <g class="axis-labels"><text x="33" y="11" text-anchor="end">{{ fmt(chart.axisMax) }}</text><text x="33" y="52.5" text-anchor="end">{{ fmt(chart.axisMax / 2) }}</text><text x="33" y="94" text-anchor="end">0</text></g>
        <g v-for="bar in chart.bars" :key="bar.item.bucket" class="trend-bar"><title>{{ `${formatBucket(bar.item.bucket)}：${bar.parts.map((part) => `${part.label} ${fmt(part.value)}`).join('，')}` }}</title><rect v-for="part in bar.parts" v-show="part.height > 0" :key="part.label" :x="bar.x" :y="part.y" :width="bar.width" :height="part.height" :fill="part.color" rx="1" /></g>
        <g class="x-labels"><text v-for="label in chart.labels" :key="`${label.x}-${label.text}`" :x="label.x" y="113" text-anchor="middle">{{ label.text }}</text></g>
      </svg>
    </section>

    <footer class="tray-footer"><span>{{ updatedText }}</span><button type="button" aria-label="刷新数据" @click="refresh"><TrayIcon name="refresh" :size="14" /></button></footer>
  </div>
</template>

<style scoped>
:global(html), :global(body), :global(#app) { width: 100%; height: 100%; margin: 0; overflow: hidden; }
:global(body) { min-width: 320px; background: #f3f6fa; }
* { box-sizing: border-box; }
button { display: flex; align-items: center; justify-content: center; gap: 3px; border: 0; padding: 0; color: #0d6bea; background: transparent; font: inherit; cursor: pointer; }
.tray-page { width: 480px; height: 600px; margin: 0 auto; padding: 8px 6px 5px 9px; overflow-x: hidden; overflow-y: scroll; scrollbar-width: thin; scrollbar-color: #b9c5d5 #edf1f6; color: #172033; background: linear-gradient(145deg, #fff 0%, #f7f9fc 68%, #f1f5fa 100%); font-family: Inter, "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; }
.tray-page::-webkit-scrollbar { width: 7px; }.tray-page::-webkit-scrollbar-track { border-radius: 99px; background: #edf1f6; }.tray-page::-webkit-scrollbar-thumb { border: 1px solid #edf1f6; border-radius: 99px; background: #b9c5d5; }.tray-page::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
.tray-header { position: sticky; top: -8px; z-index: 5; height: 43px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; padding: 0 5px; background: rgba(250,252,255,.96); backdrop-filter: blur(8px); }.tray-brand { display: flex; align-items: center; gap: 8px; }.wordmark { width: auto; height: 20px; object-fit: contain; }.logo-box { width: 31px; height: 31px; display: block; overflow: hidden; border-radius: 7px; box-shadow: 0 3px 8px #1769ef25; }.logo-box:hover { transform: scale(1.04); }.logo-box img { display: block; width: 100%; height: 100%; object-fit: cover; }.header-actions { display: flex; align-items: center; gap: 8px; }.header-actions button { width: 26px; height: 29px; color: #263248; border-radius: 6px; }.header-actions button:hover, .header-actions button.selected { color: #176def; background: #edf4ff; }.spinning { animation: spin .7s linear infinite; }
.card { border: 1px solid #e4eaf2; border-radius: 10px; background: rgba(255,255,255,.96); box-shadow: 0 3px 10px rgba(37,63,92,.055); }
.overview { height: 76px; margin-bottom: 7px; overflow: hidden; }.metrics { height: 100%; display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; padding: 8px 9px; }.metrics article { min-width: 0; display: flex; align-items: center; gap: 4px; padding: 8px 7px; border: 1px solid #e6ebf2; border-radius: 8px; }.metric-symbol { width: 17px; height: 17px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 5px; }.metric-symbol.purple { color: #7d3bec; background: #f3edff; }.metric-symbol.orange { color: #ff7218; background: #fff1e7; }.metric-symbol.green { color: #0ca56d; background: #e9f8f1; }.metric-symbol.blue { color: #176def; background: #edf4ff; }.metrics strong { display: block; color: #172033; font-size: 15px; line-height: 1; letter-spacing: -.2px; white-space: nowrap; }
.trend-card { height: 190px; margin-bottom: 7px; padding: 0 10px; }.trend-card > header { height: 39px; display: flex; align-items: center; justify-content: space-between; }.trend-card h2, .ranking h2 { margin: 0; color: #111827; font-size: 13px; letter-spacing: -.2px; }.trend-heading { display: grid; gap: 2px; }.trend-legend { display: flex; align-items: center; gap: 7px; color: #69758a; font-size: 7.5px; }.trend-legend span::before { content: ""; width: 5px; height: 5px; display: inline-block; margin-right: 3px; border-radius: 50%; vertical-align: 0; }.trend-legend .cache::before { background: #8061ee; }.trend-legend .input::before { background: #1673ed; }.trend-legend .output::before { background: #0aa36e; }.range-tabs { height: 25px; display: flex; align-items: center; padding: 2px; border: 1px solid #e0e6ee; border-radius: 7px; }.range-tabs button { width: 36px; height: 20px; border-radius: 5px; color: #657186; font-size: 10px; }.range-tabs button.active { color: #fff; background: #146eee; box-shadow: 0 2px 5px #146eee34; }.trend-chart { width: 100%; height: 144px; display: block; overflow: visible; }.grid-lines line { stroke: #e7ecf3; stroke-width: 1; stroke-dasharray: 3 3; }.axis-labels, .x-labels { fill: #6d788b; font-size: 8px; }.trend-bar rect { shape-rendering: geometricPrecision; }
.ranking { height: 225px; margin-bottom: 7px; padding: 0 10px; overflow: hidden; }.ranking-heading { height: 35px; display: flex; align-items: center; justify-content: space-between; }.ranking-heading button { font-size: 13px; font-weight: 650; letter-spacing: -.2px; }.legend { height: 20px; display: flex; align-items: center; gap: 16px; color: #69758a; font-size: 9px; }.legend span::before, .model-meta span::before { content: ""; width: 6px; height: 6px; display: inline-block; margin-right: 5px; border-radius: 50%; vertical-align: 0; }.legend .cache::before, .model-meta .cache::before { background: #8061ee; }.legend .input::before, .model-meta .input::before { background: #1673ed; }.legend .output::before, .model-meta .output::before { background: #0aa36e; }.legend small { margin-left: auto; color: #7a8598; font-size: 9px; }.model-list { height: calc(100% - 55px); }.model-row { min-height: 54px; display: grid; grid-template-columns: 31px minmax(0, 1fr); align-items: center; gap: 9px; padding: 6px 0; border-top: 1px solid #edf0f4; }.model-logo { border-radius: 8px; }.model-main { min-width: 0; }.model-title { height: 16px; display: flex; justify-content: space-between; gap: 10px; }.model-title strong { overflow: hidden; color: #273247; font-size: 10.5px; text-overflow: ellipsis; white-space: nowrap; }.model-title b { flex: 0 0 auto; color: #5d697d; font-size: 10px; font-weight: 500; }.segmented-bar { height: 8px; display: flex; overflow: hidden; border-radius: 99px; background: #edf1f5; }.segmented-bar i { min-width: 0; display: grid; place-items: center; height: 100%; color: #fff; font-size: 7px; font-style: normal; line-height: 1; }.model-meta { height: 13px; display: flex; align-items: end; justify-content: space-between; color: #667185; font-size: 7.5px; }.model-meta span::before { width: 4px; height: 4px; margin-right: 3px; }.empty-models { height: 100%; display: grid; place-items: center; color: #98a2b3; font-size: 10px; }
.tray-footer { height: 15px; display: flex; align-items: center; gap: 8px; padding-left: 10px; color: #98a2b3; font-size: 9px; }.tray-footer button { width: 20px; height: 15px; color: #8995a7; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 479px), (max-height: 599px) { .tray-page { width: 100vw; height: 100vh; } }
</style>
