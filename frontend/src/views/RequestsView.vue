<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { POLL_INTERVAL_MS, fetchRequests } from "../api";

const filters = ref({ provider: "", model: "", status: "" });
const page = ref(1);
const data = ref({ items: [], total: 0 });
let timer = null;

async function refresh() {
  const params = { limit: 50, offset: (page.value - 1) * 50 };
  for (const k of ["provider", "model"]) if (filters.value[k]) params[k] = filters.value[k];
  if (filters.value.status !== "") params.status = Number(filters.value.status);
  try {
    data.value = await fetchRequests(params);
  } catch { /* 下一轮重试 */ }
}

onMounted(() => {
  refresh();
  timer = setInterval(refresh, POLL_INTERVAL_MS * 2);
});
onBeforeUnmount(() => clearInterval(timer));
watch(filters, () => { page.value = 1; refresh(); }, { deep: true });
watch(page, refresh);
</script>

<template>
  <div class="panel">
    <div class="filters">
      <input v-model="filters.provider" placeholder="Provider" />
      <input v-model="filters.model" placeholder="Model" />
      <select v-model="filters.status">
        <option value="">全部状态</option>
        <option value="200">200</option>
        <option value="429">429</option>
        <option value="500">500</option>
      </select>
      <span class="total">共 {{ data.total }} 条</span>
      <button :disabled="page <= 1" @click="page--">上一页</button>
      <button :disabled="page * 50 >= data.total" @click="page++">下一页</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>时间</th><th>Provider</th><th>Model</th><th>Input</th><th>Output</th>
          <th>Total</th><th>Latency</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in data.items" :key="r.id">
          <td>{{ r.created_at }}</td>
          <td>{{ r.provider }}</td>
          <td>{{ r.model }}</td>
          <td>{{ r.input_tokens }}</td>
          <td>{{ r.output_tokens }}</td>
          <td>{{ r.total_tokens }}</td>
          <td>{{ (r.latency_ms / 1000).toFixed(1) }}s</td>
          <td :class="r.success ? 'ok' : 'bad'">{{ r.status_code }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.panel { background: #fff; border-radius: 8px; padding: 16px; }
.filters { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
input, select, button { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; }
.total { margin-left: auto; color: #6b7280; font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid #e5e7eb; }
.ok { color: #059669; }
.bad { color: #dc2626; }
</style>
