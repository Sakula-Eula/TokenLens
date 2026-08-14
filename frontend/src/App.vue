<script setup>
import { ref } from "vue";
import DashboardView from "./views/DashboardView.vue";
import RequestsView from "./views/RequestsView.vue";

const tab = ref("dashboard");
</script>

<template>
  <div class="app">
    <header>
      <h1>TokenLens</h1>
      <nav>
        <button :class="{ active: tab === 'dashboard' }" @click="tab = 'dashboard'">Dashboard</button>
        <button :class="{ active: tab === 'requests' }" @click="tab = 'requests'">Requests</button>
      </nav>
    </header>
    <main>
      <DashboardView v-if="tab === 'dashboard'" />
      <RequestsView v-else />
    </main>
  </div>
</template>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: #f5f6f8; color: #1f2937; }
.app { max-width: 1100px; margin: 0 auto; padding: 16px; }
header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
h1 { font-size: 20px; margin: 0; }
nav button { margin-left: 8px; padding: 6px 16px; border: 1px solid #d1d5db; border-radius: 6px; background: #fff; cursor: pointer; }
nav button.active { background: #2563eb; color: #fff; border-color: #2563eb; }
</style>
