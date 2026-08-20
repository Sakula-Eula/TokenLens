<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "./components/AppIcon.vue";
import logoUrl from "./assets/logo.png";

const route = useRoute();
const router = useRouter();
const viewRef = ref(null);
const refreshing = ref(false);
const autoRefresh = ref(true);
const range = ref("24h");
const savedInterval = Number(localStorage.getItem("tokenlens.refreshInterval"));
const refreshInterval = ref([5000, 10000, 30000, 60000].includes(savedInterval) ? savedInterval : 10000);

const navigation = [
  { id: "dashboard", path: "/dashboard", label: "概览", icon: "home" },
  { id: "models", path: "/models", label: "模型", icon: "grid" },
  { id: "providers", path: "/providers", label: "供应商", icon: "providers" },
  { id: "tokens", path: "/tokens", label: "Token", icon: "wallet" },
  { id: "costs", path: "/costs", label: "费用", icon: "coins" },
  { id: "requests", path: "/requests", label: "请求", icon: "request" },
  { id: "errors", path: "/errors", label: "错误", icon: "alert" },
  { id: "settings", path: "/settings", label: "设置", icon: "settings" },
];

const viewProps = computed(() => {
  if (route.name === "settings") return { refreshInterval: refreshInterval.value };
  const props = { autoRefresh: autoRefresh.value, refreshInterval: refreshInterval.value };
  if (route.meta.range) props.range = range.value;
  return props;
});

function updateRefreshInterval(value) {
  const interval = Number(value);
  if (![5000, 10000, 30000, 60000].includes(interval)) return;
  refreshInterval.value = interval;
  localStorage.setItem("tokenlens.refreshInterval", String(interval));
}

async function manualRefresh() {
  const view = viewRef.value;
  if (!view || refreshing.value) return;
  refreshing.value = true;
  try { await view.refresh(); } finally { refreshing.value = false; }
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark"><img :src="logoUrl" alt="TokenLens" /></span><span>TokenLens</span></div>
      <nav class="side-nav" aria-label="主导航">
        <RouterLink v-for="item in navigation" :key="item.id" :to="item.path" :class="{ active: route.name === item.id }"><AppIcon :name="item.icon" :size="19" /><span>{{ item.label }}</span></RouterLink>
      </nav>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div class="mobile-brand"><span class="brand-mark"><img :src="logoUrl" alt="TokenLens" /></span><strong>TokenLens</strong></div>
        <div class="toolbar">
          <label v-if="route.meta.range" class="range-select"><select v-model="range" aria-label="统计时间范围"><option value="24h">最近24小时</option><option value="7d">最近7天</option><option value="30d">最近30天</option></select><AppIcon name="calendar" :size="16" /></label>
          <label class="auto-refresh"><span>自动刷新</span><input v-model="autoRefresh" type="checkbox" /><span class="switch" aria-hidden="true"></span></label>
          <button class="refresh-button" type="button" :disabled="refreshing" @click="manualRefresh"><AppIcon name="refresh" :size="17" :class="{ spinning: refreshing }" /><span>{{ refreshing ? "刷新中" : "刷新" }}</span></button>
        </div>
      </header>
      <main>
        <RouterView v-slot="{ Component }">
          <component :is="Component" ref="viewRef" v-bind="viewProps" @open-errors="router.push('/errors')" @update-refresh-interval="updateRefreshInterval" />
        </RouterView>
      </main>
    </section>
  </div>
</template>

<style>
:root { font-family: Inter, "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; color: #101828; background: #f7f9fc; font-synthesis: none; }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; min-width: 320px; min-height: 100vh; overflow: hidden; background: #f7f9fc; }
button, input, select { font: inherit; }button { cursor: pointer; }
.app-shell { height: 100vh; display: flex; overflow: hidden; }
.sidebar { position: fixed; inset: 0 auto 0 0; z-index: 20; width: 210px; background: #fff; border-right: 1px solid #e4e9f1; }
.brand { height: 76px; display: flex; align-items: center; gap: 12px; padding: 0 26px; font-size: 20px; font-weight: 750; letter-spacing: -.4px; }
.brand-mark { width: 31px; height: 31px; display: block; flex: 0 0 auto; overflow: hidden; border-radius: 7px; }.brand-mark img { display: block; width: 100%; height: 100%; object-fit: cover; }
.side-nav { padding: 2px 6px; }.side-nav a { position: relative; width: 100%; height: 47px; display: flex; align-items: center; gap: 15px; padding: 0 25px; border-radius: 7px; color: #42526d; background: transparent; font-size: 14px; text-align: left; text-decoration: none; }.side-nav a:hover { color: #1769ef; background: #f4f7fc; }.side-nav a.active { color: #1769ef; background: #eef4ff; font-weight: 650; }.side-nav a.active::before { content: ""; position: absolute; left: -3px; top: 0; bottom: 0; width: 3px; border-radius: 3px; background: #2476f5; }
.workspace { min-width: 0; flex: 1; height: 100vh; margin-left: 210px; overflow-y: scroll; scrollbar-gutter: stable; scrollbar-color: #b9c5d5 #edf1f6; scrollbar-width: thin; }.workspace::-webkit-scrollbar { width: 10px; }.workspace::-webkit-scrollbar-track { background: #edf1f6; }.workspace::-webkit-scrollbar-thumb { border: 2px solid #edf1f6; border-radius: 99px; background: #b9c5d5; }.workspace::-webkit-scrollbar-thumb:hover { background: #94a3b8; }.topbar { height: 76px; display: flex; align-items: center; justify-content: flex-end; padding: 0 38px; border-bottom: 1px solid #edf0f5; background: rgba(255,255,255,.76); backdrop-filter: blur(12px); }.mobile-brand { display: none; align-items: center; gap: 9px; }.toolbar { display: flex; align-items: center; gap: 24px; }
.range-select { position: relative; display: flex; align-items: center; }.range-select select { width: 145px; height: 38px; appearance: none; border: 1px solid #dfe5ed; border-radius: 7px; padding: 0 38px 0 13px; color: #344054; outline: none; background: #fff; }.range-select .app-icon { position: absolute; right: 12px; color: #667085; pointer-events: none; }
.auto-refresh { display: flex; align-items: center; gap: 10px; color: #344054; font-size: 14px; cursor: pointer; }.auto-refresh input { position: absolute; opacity: 0; pointer-events: none; }.switch { position: relative; width: 39px; height: 22px; border-radius: 99px; background: #cbd5e1; transition: .2s; }.switch::after { content: ""; position: absolute; width: 18px; height: 18px; top: 2px; left: 2px; border-radius: 50%; background: #fff; box-shadow: 0 1px 4px #0003; transition: .2s; }.auto-refresh input:checked + .switch { background: #2476f5; }.auto-refresh input:checked + .switch::after { transform: translateX(17px); }
.refresh-button { height: 38px; min-width: 110px; display: flex; align-items: center; justify-content: center; gap: 8px; border: 1px solid #dfe5ed; border-radius: 7px; color: #1769ef; background: #fff; }.refresh-button:hover { border-color: #a9c7f8; background: #f8fbff; }.refresh-button:disabled { opacity: .65; cursor: wait; }.spinning { animation: spin .75s linear infinite; }.workspace main { padding: 20px 28px 40px; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 900px) {
  .sidebar { inset: auto 0 0; width: auto; height: 62px; border-right: 0; border-top: 1px solid #e4e9f1; }.brand { display: none; }.side-nav { height: 100%; padding: 4px 8px; display: flex; justify-content: flex-start; overflow-x: auto; }.side-nav a { width: 72px; height: 52px; flex: 0 0 72px; flex-direction: column; justify-content: center; gap: 3px; padding: 0 5px; font-size: 11px; }.workspace { margin-left: 0; padding-bottom: 62px; }.topbar { padding: 0 18px; justify-content: space-between; }.mobile-brand { display: flex; }.toolbar { gap: 10px; }.auto-refresh > span:first-child { display: none; }.workspace main { padding: 16px; }
}
@media (max-width: 560px) {
  .topbar { height: auto; min-height: 70px; align-items: flex-start; padding-block: 12px; }.mobile-brand strong { display: none; }.toolbar { flex-wrap: wrap; justify-content: flex-end; }.range-select select { width: 133px; }.refresh-button { min-width: 38px; width: 38px; padding: 0; }.refresh-button span { display: none; }
}
</style>
