<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { NButton, NInput, NPopconfirm } from 'naive-ui';
import { webAgentApi, type SharedModelConfig } from '../api/webAgent';

const config = ref<SharedModelConfig | null>(null);
const key = ref('');
const busy = ref(false);
const error = ref('');
const notice = ref('');
const balance = ref('');
let disposed = false;
const sourceLabel = computed(() => config.value?.source === 'database' ? '使用网页保存的 Key'
  : config.value?.source === 'environment' ? '使用服务器环境变量中的 Key' : '尚未配置公共 Key');

async function load() {
  busy.value = true;
  error.value = '';
  try {
    const result = await webAgentApi.sharedConfig();
    if (!disposed) config.value = result;
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) busy.value = false; }
}
async function save() {
  if (busy.value || !key.value.trim()) return;
  busy.value = true;
  error.value = notice.value = '';
  try {
    const result = await webAgentApi.saveSharedKey(key.value.trim());
    if (!disposed) {
      config.value = result;
      key.value = '';
      balance.value = '';
      notice.value = '公共 Key 已保存，后续请求立即使用新配置。';
    }
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) busy.value = false; }
}
async function clear() {
  if (busy.value) return;
  busy.value = true;
  error.value = notice.value = '';
  try {
    const result = await webAgentApi.clearSharedKey();
    if (!disposed) {
      config.value = result;
      key.value = balance.value = '';
      notice.value = result.configured ? '网页保存的 Key 已清除，当前使用服务器环境变量配置。'
        : '公共 Key 已清除，成员仍可使用自己的个人 Key。';
    }
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) busy.value = false; }
}
async function queryBalance() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  balance.value = '';
  try {
    const result = await webAgentApi.balance();
    if (!disposed) balance.value = result.balances.map(item => `${item.total_balance} ${item.currency}`).join('，')
      + (result.available ? '' : '（账户当前不可用）') + `（${new Date().toLocaleString('zh-CN')} 查询）`;
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) busy.value = false; }
}
onMounted(load);
onBeforeUnmount(() => { disposed = true; key.value = ''; });
</script>

<template>
  <div class="page-toolbar">
    <span class="page-count">供社团成员在网页助手中使用</span>
    <div class="page-tools"><NButton size="small" :disabled="busy" @click="load">刷新状态</NButton></div>
  </div>
  <section class="shared-model-settings" :aria-busy="busy">
    <div class="model-status"><strong>DeepSeek 公共模型</strong><span>{{ config ? sourceLabel : '正在读取配置…' }}</span></div>
    <p>成员在助手的模型设置中选择“社团提供的 DeepSeek”后，调用费用由这个 Key 所属账户承担。</p>
    <form @submit.prevent="save">
      <label for="shared-deepseek-key">{{ config?.configured ? '替换公共 Key' : '公共 DeepSeek Key' }}</label>
      <NInput id="shared-deepseek-key" v-model:value="key" type="password" show-password-on="click"
        autocomplete="off" :disabled="busy || !config" placeholder="粘贴 DeepSeek API Key，保存后不再显示" />
      <p class="model-help">只有管理员可以管理。Key 明文保存在数据库及其备份中，不会返回给成员或回填到页面。</p>
      <div class="model-actions">
        <NButton attr-type="submit" type="primary" :loading="busy" :disabled="busy || !config || !key.trim()">保存 Key</NButton>
        <NButton :disabled="busy || !config?.configured" @click="queryBalance">查询公共账户余额</NButton>
        <NPopconfirm :disabled="busy || !config?.database_configured" @positive-click="clear">
          <template #trigger><NButton :disabled="busy || !config?.database_configured">清除网页保存的 Key</NButton></template>
          清除网页保存的 Key？服务器若仍配置了环境变量，将继续使用该配置。
        </NPopconfirm>
      </div>
    </form>
    <p v-if="config?.source === 'environment'" class="model-help">网页保存的新 Key 会优先使用。环境变量只能在服务器修改或移除。</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="balance" role="status">公共账户余额：{{ balance }}</p>
  </section>
</template>

<style scoped>
.shared-model-settings { max-width:760px; padding:24px; border:1px solid var(--line); border-radius:6px; background:white; }
.model-status { display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px 20px; }
.model-status strong { font-size:18px; font-weight:600; }
.model-status span,.model-help { color:var(--muted); font-size:12px; }
.shared-model-settings p { line-height:1.7; margin:12px 0; }
.shared-model-settings form { margin-top:24px; }
.shared-model-settings label { display:block; margin-bottom:8px; font-weight:500; }
.model-actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }
@media(max-width:700px) { .shared-model-settings { padding:18px; } .model-actions { align-items:stretch; } }
</style>
