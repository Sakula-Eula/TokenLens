<script setup>
import { computed, ref, watch } from "vue";
import { getModelProvider } from "../utils/modelProvider";

const props = defineProps({
  model: { type: String, default: "" },
  provider: { type: String, default: "" },
  size: { type: Number, default: 24 },
});

const iconModules = {
  ...import.meta.glob("../assets/providers/*.{svg,png}", {
    eager: true,
    query: "?url",
    import: "default",
  }),
  ...import.meta.glob("../../../assets/*.{svg,png}", {
    eager: true,
    query: "?url",
    import: "default",
  }),
};
const iconUrls = Object.fromEntries(Object.entries(iconModules).map(([path, url]) => [path.split("/").pop().replace(/\.(svg|png)$/, ""), url]));
const iconFileKeys = { anthropic: "claude" };
const failed = ref(false);
const providerKey = computed(() => getModelProvider(props.model, props.provider));
const iconUrl = computed(() => failed.value ? null : iconUrls[iconFileKeys[providerKey.value] || providerKey.value]);
const fallback = computed(() => String(props.model || props.provider || "?").trim().charAt(0).toUpperCase() || "?");

watch([() => props.model, () => props.provider], () => { failed.value = false; });
</script>

<template>
  <span class="model-icon" :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${Math.max(9, size * .46)}px` }" :title="providerKey || '未知模型供应商'">
    <img v-if="iconUrl" :src="iconUrl" :alt="`${providerKey} 图标`" @error="failed = true" />
    <span v-else aria-hidden="true">{{ fallback }}</span>
  </span>
</template>

<style scoped>
.model-icon { display: inline-grid; flex: 0 0 auto; place-items: center; overflow: hidden; border: 1px solid #e2e7ef; border-radius: 25%; color: #667085; background: #fff; font-weight: 700; line-height: 1; vertical-align: middle; }
.model-icon img { display: block; width: 72%; height: 72%; object-fit: contain; }
</style>
