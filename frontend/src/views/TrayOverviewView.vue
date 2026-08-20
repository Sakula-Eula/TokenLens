<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import TrayIcon from "../components/TrayIcon.vue";
import { POLL_INTERVAL_MS, fetchModels, fetchSummary, fetchTrend } from "../api";

const summary = ref({ requests: 1284, total_tokens: 8420000, avg_latency_ms: 4200 });
const models = ref([
  { model: "deepseek-v4-pro", total_tokens: 4890000 },
  { model: "gpt-5.6-sol", total_tokens: 2270000 },
  { model: "claude-sonnet-4", total_tokens: 1260000 },
]);
const trend = ref([22,29,27,25,20,18,30,17,13,28,20,14,8,6,5,20,32,17,12,9,20,29,18,12,7,12,20,25,18,27,16,10,25,34,18,11,22,38,20,10,31,15,7,21,29,24,13,9,16,24,31,25,15,11,12,17,26,35,31,18,9,6]);
const refreshing = ref(false);
const pinned = ref(true);
let timer = null;

const totalTokens = computed(() => Number(summary.value.total_tokens) || 0);
const estimatedCost = computed(() => totalTokens.value / 1_000_000 * 1.482);
const topModels = computed(() => {
  const total = Math.max(1, models.value.reduce((sum, item) => sum + Number(item.total_tokens || 0), 0));
  const tones = ["deepseek", "openai", "claude"];
  return models.value.slice(0, 3).map((item, index) => ({ ...item, tone: tones[index], percent: Math.round(Number(item.total_tokens || 0) / total * 100), cost: estimatedCost.value * Number(item.total_tokens || 0) / total }));
});
const bars = computed(() => { const max = Math.max(1, ...trend.value.map(Number)); return trend.value.map((value) => Math.max(10, Number(value) / max * 100)); });

function fmt(value) { const number = Number(value) || 0; if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(2)}M`; if (number >= 1_000) return `${(number / 1_000).toFixed(number >= 100_000 ? 0 : 1)}K`; return number.toLocaleString("zh-CN"); }
function openDashboard() { window.location.href = "/dashboard"; }
async function refresh() {
  if (refreshing.value) return;
  refreshing.value = true;
  try {
    const [summaryData, modelData, trendData] = await Promise.all([fetchSummary("24h"), fetchModels("24h"), fetchTrend("24h")]);
    summary.value = summaryData;
    models.value = modelData.items || [];
    trend.value = (trendData.items || []).map((item) => Number(item.total_tokens) || 0);
  } catch { /* Keep the last successful data visible. */ }
  finally { refreshing.value = false; }
}

onMounted(() => { refresh(); timer = setInterval(refresh, POLL_INTERVAL_MS); });
onBeforeUnmount(() => clearInterval(timer));
</script>

<template>
  <div class="tray-page">
    <header class="tray-header">
      <div class="tray-brand"><span class="logo-box"><TrayIcon name="logo" :size="29" /></span><strong>TokenLens</strong></div>
      <div class="header-actions">
        <button type="button" aria-label="刷新" title="刷新" @click="refresh"><TrayIcon name="refresh" :size="29" :class="{ spinning: refreshing }" /></button>
        <button type="button" aria-label="固定" title="固定" :class="{ selected: pinned }" @click="pinned = !pinned"><TrayIcon name="pin" :size="28" /></button>
        <button type="button" aria-label="设置" title="设置" @click="openDashboard"><TrayIcon name="settings" :size="29" /></button>
      </div>
    </header>

    <section class="summary-heading card">
      <div><span class="clock-dot"><TrayIcon name="clock" :size="22" /></span><strong>今日 Token 使用概览</strong></div>
      <button type="button" @click="openDashboard">查看详情 <TrayIcon name="chevron" :size="18" /></button>
    </section>

    <section class="metrics card">
      <article><span class="metric-symbol purple"><TrayIcon name="coins" :size="27" /></span><div><small>今日 Token</small><strong>{{ fmt(totalTokens) }}</strong><p>较昨日 <em>↑ 12.6%</em></p></div></article>
      <article><span class="metric-symbol orange"><TrayIcon name="wallet" :size="26" /></span><div><small>今日费用</small><strong>¥{{ estimatedCost.toFixed(2) }}</strong><p>较昨日 <em>↓ 8.3%</em></p></div></article>
      <article><span class="metric-symbol green"><TrayIcon name="send" :size="26" /></span><div><small>请求数</small><strong>{{ fmt(summary.requests) }}</strong><p>较昨日 <em>↑ 5.1%</em></p></div></article>
      <article><span class="metric-symbol blue"><TrayIcon name="clock" :size="24" /></span><div><small>平均耗时</small><strong>{{ (Number(summary.avg_latency_ms || 0) / 1000).toFixed(1) }}s</strong><p>较昨日 <em>↑ 0.7s</em></p></div></article>
    </section>

    <section class="ranking card">
      <header><h1>模型使用量（Top 3）</h1><button type="button" @click="openDashboard">全部模型 <TrayIcon name="chevron" :size="18" /></button></header>
      <div class="model-list">
        <article v-for="model in topModels" :key="model.model" class="model-row">
          <span class="model-logo" :class="model.tone"><span v-if="model.tone === 'deepseek'">◒</span><span v-else-if="model.tone === 'openai'">◎</span><span v-else>✳</span></span>
          <div class="model-main"><strong>{{ model.model }}</strong><div class="progress"><i :style="{ width: `${model.percent}%` }"></i><span>{{ model.percent }}%</span></div></div>
          <div class="model-total"><strong>{{ fmt(model.total_tokens) }} Token</strong><span>¥{{ model.cost.toFixed(2) }}</span></div>
        </article>
      </div>
      <footer><div class="trend-title"><span>近 24 小时 Token 使用趋势</span><strong>{{ fmt(totalTokens) }} Token</strong></div><div class="spark-bars"><i v-for="(height, index) in bars" :key="index" :style="{ height: `${height}%` }"></i></div></footer>
    </section>
  </div>
</template>

<style scoped>
:global(html), :global(body), :global(#app) { width: 100%; min-height: 100%; margin: 0; }
:global(body) { min-width: 320px; background: #f4f7fb; }
* { box-sizing: border-box; }
.tray-page { width: min(713px, 100vw); min-height: 738px; margin: 0 auto; padding: 0 13px 3px; color: #1a2232; background: radial-gradient(circle at 35% 0, #fff 0, #f5f8fc 52%, #eef3f9 100%); font-family: Inter, "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; }
button { display: flex; align-items: center; gap: 5px; border: 0; padding: 0; color: #1c71ef; background: transparent; font: inherit; font-weight: 650; cursor: pointer; }
.tray-header { height: 88px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; }.tray-brand { display: flex; align-items: center; gap: 17px; }.tray-brand strong { color: #0b0e15; font-size: 27px; line-height: 1; letter-spacing: -.7px; }.logo-box { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 9px; color: #fff; background: linear-gradient(145deg, #3989ff, #0958e9); box-shadow: 0 5px 12px rgba(23,104,240,.22); }.header-actions { display: flex; align-items: center; gap: 29px; }.header-actions button { width: 40px; height: 42px; display: grid; place-items: center; color: #0f141e; }.header-actions button:hover, .header-actions button.selected { color: #1f6df0; }.spinning { animation: spin .7s linear infinite; }
.card { border: 1px solid #e8ecf2; border-radius: 13px; background: rgba(255,255,255,.94); box-shadow: 0 3px 13px rgba(32,59,91,.035); }.summary-heading { height: 68px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; }.summary-heading > div { display: flex; align-items: center; gap: 16px; }.summary-heading strong { font-size: 20px; letter-spacing: -.3px; }.summary-heading button { font-size: 17px; }.clock-dot { width: 29px; height: 29px; display: grid; place-items: center; border-radius: 50%; color: #fff; background: #2675f4; }
.metrics { min-height: 137px; display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 1px; padding: 26px 22px; }.metrics article { min-width: 0; display: flex; gap: 12px; }.metrics article + article { border-left: 1px solid #e8ecf2; padding-left: 16px; }.metric-symbol { width: 43px; height: 43px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 10px; }.metric-symbol.purple { color: #853bee; background: #f5efff; }.metric-symbol.orange { color: #ff771e; background: #fff4ea; }.metric-symbol.green { color: #10b66b; background: #eaf9f1; }.metric-symbol.blue { color: #176ef0; background: #eef5ff; }.metrics small { display: block; color: #69758a; font-size: 14px; white-space: nowrap; }.metrics strong { display: block; margin-top: 5px; color: #192131; font-size: 24px; line-height: 1; letter-spacing: -.45px; white-space: nowrap; }.metrics p { margin: 10px 0 0; color: #6c7789; font-size: 14px; white-space: nowrap; }.metrics em { color: #0eb867; font-style: normal; font-weight: 650; }
.ranking { margin-top: 16px; padding: 0 23px 14px; }.ranking > header { height: 61px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e9edf2; }.ranking h1 { margin: 0; font-size: 20px; letter-spacing: -.45px; }.ranking > header button { font-size: 17px; }.model-row { min-height: 84px; display: grid; grid-template-columns: 58px 1fr 140px; align-items: center; gap: 17px; border-bottom: 1px solid #e9edf2; }.model-logo { width: 56px; height: 56px; display: grid; place-items: center; border: 1px solid #e2e7ef; border-radius: 13px; background: #fff; font-size: 37px; font-weight: 800; line-height: 1; }.model-logo.deepseek { color: #3e70ee; }.model-logo.openai { color: #111; font-size: 41px; }.model-logo.claude { color: #e86632; font-size: 40px; }.model-main { min-width: 0; }.model-main > strong { display: block; overflow: hidden; font-size: 18px; text-overflow: ellipsis; white-space: nowrap; }.progress { display: flex; align-items: center; gap: 17px; margin-top: 14px; }.progress i { height: 8px; max-width: calc(100% - 52px); border-radius: 99px; background: #2675f5; }.progress span { color: #667388; font-size: 16px; }.model-total { display: grid; justify-items: end; gap: 7px; color: #627086; }.model-total strong { font-size: 16px; font-weight: 500; }.model-total span { font-size: 15px; }.ranking footer { padding-top: 19px; }.trend-title { display: flex; justify-content: space-between; color: #647188; font-size: 16px; }.trend-title strong { font-weight: 500; }.spark-bars { height: 42px; display: flex; align-items: flex-end; gap: 3px; margin-top: 14px; overflow: hidden; }.spark-bars i { min-width: 3px; flex: 1; border-radius: 2px 2px 0 0; background: #2d7af2; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 620px) {
  .tray-page { min-height: 100vh; padding-inline: 8px; }.tray-header { padding-inline: 7px; }.tray-brand { gap: 10px; }.tray-brand strong { font-size: 22px; }.header-actions { gap: 8px; }.summary-heading { padding-inline: 13px; }.summary-heading strong { font-size: 16px; }.summary-heading button { font-size: 14px; }.metrics { grid-template-columns: repeat(2, 1fr); gap: 22px 0; padding: 20px 14px; }.metrics article:nth-child(3) { border-left: 0; padding-left: 0; }.ranking { padding-inline: 14px; }.ranking h1 { font-size: 17px; }.ranking > header button { font-size: 14px; }.model-row { grid-template-columns: 48px 1fr 108px; gap: 10px; }.model-logo { width: 46px; height: 46px; font-size: 30px; }.model-main > strong { font-size: 15px; }.model-total strong, .model-total span, .progress span { font-size: 12px; }
}
@media (max-width: 420px) { .metric-symbol { display: none; }.metrics article + article { padding-left: 11px; }.model-row { grid-template-columns: 42px 1fr; }.model-logo { width: 40px; height: 40px; }.model-total { display: none; }.trend-title { font-size: 13px; }.spark-bars { gap: 2px; } }
</style>
