<script setup>
import { onMounted, ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { fetchProviderSettings, saveProviderSettings } from "../api";

const providers = ref([]);
const loading = ref(true);
const saving = ref(false);
const message = ref("");
const errorMessage = ref("");

function editable(item) {
  return { ...item, api_key: "", clear_api_key: false, persisted: true };
}

async function refresh() {
  loading.value = true;
  try {
    const data = await fetchProviderSettings();
    providers.value = (data.items || []).map(editable);
    errorMessage.value = "";
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || "配置加载失败";
  } finally { loading.value = false; }
}

function addProvider() {
  providers.value.push({ name: "", type: "openai", base_url: "", api_key: "", has_api_key: false, clear_api_key: false, persisted: false });
}

function removeProvider(index) {
  const item = providers.value[index];
  if (item.persisted && !window.confirm(`确定删除 Provider“${item.name}”吗？保存后需重启生效。`)) return;
  providers.value.splice(index, 1);
}

async function save() {
  saving.value = true;
  message.value = "";
  errorMessage.value = "";
  try {
    const payload = providers.value.map((item) => ({
      name: item.name.trim(), type: item.type, base_url: item.base_url.trim(),
      api_key: item.api_key.trim() || null, clear_api_key: item.clear_api_key,
    }));
    const data = await saveProviderSettings(payload);
    providers.value = (data.items || []).map(editable);
    message.value = "配置已安全保存，请重启 TokenLens 使新配置生效。";
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || "配置保存失败，请检查输入";
  } finally { saving.value = false; }
}

onMounted(refresh);
defineExpose({ refresh });
</script>

<template>
  <div class="settings-page" :class="{ loading }">
    <div class="page-heading">
      <div><h1>设置</h1><p>管理透明代理使用的上游 Provider</p></div>
      <button class="add-button" type="button" @click="addProvider"><span>＋</span>新增 Provider</button>
    </div>

    <div class="security-note"><AppIcon name="check" :size="18" /><span><b>密钥受到保护</b>后端不会返回已有 API Key。密钥输入留空会保留原值，只有勾选清除才会删除。</span></div>
    <div v-if="message" class="message success"><AppIcon name="check" :size="17" />{{ message }}</div>
    <div v-if="errorMessage" class="message error"><AppIcon name="alert" :size="17" />{{ errorMessage }}</div>

    <section class="provider-list">
      <article v-for="(item, index) in providers" :key="item.persisted ? item.name : `new-${index}`" class="provider-card">
        <div class="card-heading"><div><h2>{{ item.name || '新 Provider' }}</h2><span v-if="item.has_api_key" class="key-badge">已配置密钥</span></div><button type="button" class="delete-button" @click="removeProvider(index)">删除</button></div>
        <div class="form-grid">
          <label><span>Provider 名称</span><input v-model.trim="item.name" :disabled="item.persisted" placeholder="例如 openai" /><small>用于代理路径 /{provider}/v1/...</small></label>
          <label><span>协议类型</span><select v-model="item.type"><option value="openai">OpenAI Compatible</option><option value="anthropic">Anthropic</option></select></label>
          <label class="base-url"><span>Base URL</span><input v-model.trim="item.base_url" placeholder="https://api.example.com" /><small>不要包含末尾的 /v1</small></label>
          <label class="api-key"><span>替换 API Key</span><input v-model="item.api_key" type="password" autocomplete="new-password" :placeholder="item.has_api_key ? '留空以保留现有密钥' : '可选：输入兜底密钥'" /></label>
        </div>
        <label v-if="item.has_api_key" class="clear-key"><input v-model="item.clear_api_key" type="checkbox" />保存时清除现有 API Key</label>
      </article>
      <div v-if="!providers.length && !loading" class="empty-state"><AppIcon name="providers" :size="32" /><b>尚未配置 Provider</b><span>点击“新增 Provider”添加第一个上游服务。</span></div>
    </section>

    <footer><span>配置保存后不会立即热加载，需要重启 TokenLens。</span><button type="button" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存设置' }}</button></footer>
  </div>
</template>

<style scoped>
.settings-page { max-width: 1120px; margin: 0 auto; color: #344054; transition: opacity .2s; }.loading { opacity: .7; }.page-heading { min-height: 70px; display: flex; justify-content: space-between; gap: 16px; }.page-heading h1 { margin: 0; color: #101828; font-size: 22px; }.page-heading p { margin: 7px 0 0; color: #7b879b; font-size: 13px; }.add-button, footer button { height: 38px; border: 0; border-radius: 7px; padding: 0 15px; color: #fff; background: #2476f5; }.add-button span { margin-right: 5px; font-size: 18px; }.security-note, .message { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; padding: 12px 14px; border: 1px solid #cfe0fb; border-radius: 9px; color: #315b96; background: #f4f8ff; font-size: 12px; }.security-note span { display: flex; gap: 7px; }.message.success { border-color: #b7ebd4; color: #087a55; background: #effbf6; }.message.error { border-color: #fecaca; color: #b42318; background: #fff1f1; }
.provider-list { display: grid; gap: 14px; }.provider-card { padding: 19px; border: 1px solid #e6ebf2; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(16,24,40,.035); }.card-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 17px; }.card-heading > div { display: flex; align-items: center; gap: 10px; }.card-heading h2 { margin: 0; color: #101828; font-size: 15px; }.key-badge { padding: 4px 8px; border-radius: 99px; color: #087a55; background: #eaf9f2; font-size: 10px; }.delete-button { border: 0; color: #d92d20; background: transparent; font-size: 12px; }.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }.form-grid label { display: grid; gap: 7px; color: #667085; font-size: 11px; }.form-grid .base-url, .form-grid .api-key { grid-column: span 1; }.form-grid input, .form-grid select { height: 40px; border: 1px solid #dfe5ed; border-radius: 7px; padding: 0 11px; color: #344054; background: #fff; outline: none; }.form-grid input:focus, .form-grid select:focus { border-color: #8db6f7; box-shadow: 0 0 0 3px #2677f412; }.form-grid input:disabled { color: #667085; background: #f5f7fa; }.form-grid small { color: #98a2b3; font-size: 10px; }.clear-key { display: flex; align-items: center; gap: 7px; margin-top: 14px; color: #b42318; font-size: 11px; }.empty-state { min-height: 230px; display: grid; place-items: center; align-content: center; gap: 9px; border: 1px dashed #cfd7e3; border-radius: 10px; color: #98a2b3; }.empty-state b { color: #475467; font-size: 14px; }.empty-state span { font-size: 11px; }footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 16px; padding: 15px 0; color: #7b879b; font-size: 11px; }footer button { min-width: 120px; }footer button:disabled { opacity: .65; cursor: wait; }
@media (max-width: 680px) { .form-grid { grid-template-columns: 1fr; }.page-heading { min-height: 82px; }.add-button { padding: 0 10px; }.security-note span { display: grid; }.form-grid .base-url, .form-grid .api-key { grid-column: auto; }footer { align-items: flex-start; flex-direction: column; }footer button { width: 100%; } }
</style>
