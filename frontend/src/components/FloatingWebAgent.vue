<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import { NButton, NInput, NModal, NSelect } from 'naive-ui';
import type { User } from '../api/auth';
import AgentMarkdown from './AgentMarkdown.vue';
import { agentConnections } from '../api/agentConnections';
import { streamChat, webAgentApi, type AgentEvent, type AgentHistory, type ChatMessage, type WebAgentConfig } from '../api/webAgent';

const props = defineProps<{ user: User }>();
const emit = defineEmits<{ changed: [] }>();
const open = ref(new URLSearchParams(window.location.search).get('assistant') === '1');
const expanded = ref(false);
const config = ref<WebAgentConfig | null>(null);
const connection = ref<string | null>(null);
const source = ref<'personal' | 'shared'>('shared');
const model = ref('deepseek-flash');
const key = ref('');
const draft = ref('');
const error = ref('');
const busy = ref(false);
const settings = ref(false);
const configurationFailed = ref(false);
const transcript = ref<HTMLElement | null>(null);
const followLatest = ref(true);
interface ToolProgress { id: string; name: string; done: boolean }
interface ChatEntry extends ChatMessage { incomplete?: boolean; tools?: ToolProgress[] }
const messages = ref<ChatEntry[]>([]);
const agentHistory = shallowRef<AgentHistory>([]);
const usage = ref({ input: 0, output: 0, requests: 0 });
const balance = ref('');
const balanceBusy = ref(false);
let controller: AbortController | null = null;
let disposed = false;
const options = computed(() => config.value?.connections.map(item => ({
  value: item.id, label: item.name + `（${item.level}）` + (item.active ? '' : '（已停用）'), disabled: !item.active,
})) || []);
const connectionLevel = computed(() => config.value?.connections.find(item => item.id === connection.value)?.level);
const modelReady = computed(() => Boolean(config.value?.models.includes(model.value) &&
  (source.value === 'shared' ? config.value.shared_available : key.value.trim())));
const canSend = computed(() => Boolean(draft.value.trim() && !busy.value));
const labels: Record<string, string> = {
  fgas_help: '查看业务指南', fgas_query: '查询业务资料', fgas_propose: '提交待审批申请',
  fgas_execute: '直接办理业务',
};

async function load() {
  try {
    const data = await webAgentApi.config();
    if (disposed) return;
    const initial = config.value === null;
    config.value = data;
    const active = data.connections.filter(item => item.active);
    if (!active.some(item => item.id === connection.value)) {
      const low = active.filter(item => item.level === 'low');
      connection.value = low.find(item => item.name === '网页助手')?.id || low[0]?.id || null;
    }
    if (initial) source.value = data.shared_available ? 'shared' : 'personal';
    if (open.value && (!modelReady.value || configurationFailed.value)) settings.value = true;
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
}
async function createConnection() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await agentConnections.create({ name: '网页助手', level: 'low', expires_at: null });
    await load();
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) busy.value = false; }
}
function trackScroll() {
  const area = transcript.value;
  if (area) followLatest.value = area.scrollHeight - area.scrollTop - area.clientHeight < 48;
}
async function scroll(force = false) {
  await nextTick();
  if (transcript.value && (force || followLatest.value)) {
    transcript.value.scrollTop = transcript.value.scrollHeight;
    followLatest.value = true;
  }
}
function toolSummary(message: ChatEntry, index: number) {
  const pending = message.tools?.find(tool => !tool.done);
  if (pending) return busy.value && index === messages.value.length - 1
    ? labels[pending.name] || '正在处理' : '有步骤待核对';
  return `${message.tools?.length || 0} 个步骤已返回`;
}
async function send() {
  if (!canSend.value) return;
  if (!modelReady.value || !connection.value || configurationFailed.value) { settings.value = true; return; }
  if (messages.value.length >= 40) { error.value = '这段对话已较长，请清空会话后继续'; return; }
  const previousHistory = agentHistory.value;
  const message = draft.value.trim();
  messages.value.push({ role: 'user', content: message });
  messages.value.push({ role: 'assistant', content: '', incomplete: true, tools: [] });
  const index = messages.value.length - 1;
  const reply = messages.value[index]!;
  const tools = reply.tools!;
  draft.value = '';
  error.value = '';
  void scroll(true);
  busy.value = true;
  controller = new AbortController();
  let changed = false;
  const requestConfiguration = () => {
    configurationFailed.value = true;
    settings.value = true;
    if (!tools.length && !reply.content) {
      messages.value.splice(index - 1, 2);
      agentHistory.value = previousHistory;
      draft.value = message;
    }
  };
  const onEvent = (event: AgentEvent) => {
    if (disposed) return;
    if (event.type === 'start' && event.level) {
      const selected = config.value?.connections.find(item => item.id === connection.value);
      if (selected) selected.level = event.level;
    } else if (event.type === 'text') reply.content += event.text || '';
    else if (event.type === 'tool_start') {
      tools.push({ id: event.id || '', name: event.name || '', done: false });
      if (event.name === 'fgas_propose' || event.name === 'fgas_execute') changed = true;
    } else if (event.type === 'tool_end') {
      const tool = tools.find(item => item.id === event.id);
      if (tool) tool.done = true;
    } else if (event.type === 'usage') {
      usage.value.input += event.input_tokens || 0;
      usage.value.output += event.output_tokens || 0;
      usage.value.requests += event.requests || 0;
    } else if (event.type === 'history' && event.history) agentHistory.value = event.history;
    else if (event.type === 'done') reply.incomplete = false;
    else if (event.type === 'error') {
      error.value = event.message || '本轮未能完成';
      if (event.configuration_error) requestConfiguration();
    }
    void scroll();
  };
  try {
    await streamChat({ credential_id: connection.value, message, history: agentHistory.value, model: model.value,
      source: source.value, ...(source.value === 'personal' ? { api_key: key.value } : {}) }, controller.signal, onEvent);
  } catch (e) {
    if (!disposed) {
      error.value = (e as Error).name === 'AbortError'
        ? '已停止接收回复。已经提交的业务请到记录中核对。' : (e as Error).message;
      if ((e as Error & { configurationError?: boolean }).configurationError) requestConfiguration();
    }
  } finally {
    controller = null;
    if (!disposed) { busy.value = false; if (changed) emit('changed'); }
  }
}
function clear() {
  if (busy.value) return;
  messages.value = [];
  agentHistory.value = [];
  followLatest.value = true;
  usage.value = { input: 0, output: 0, requests: 0 };
  error.value = '';
}
async function queryBalance() {
  balanceBusy.value = true;
  error.value = '';
  try {
    const result = await webAgentApi.balance();
    if (!disposed) balance.value = result.balances.map(item => item.total_balance + ' ' + item.currency).join('，') +
      '（' + new Date().toLocaleTimeString('zh-CN') + ' 查询）';
  } catch (e) { if (!disposed) error.value = (e as Error).message; }
  finally { if (!disposed) balanceBusy.value = false; }
}
function openWithDraft(message: string) {
  if (!draft.value.trim() && !busy.value) draft.value = message;
  open.value = true;
}
defineExpose({ openWithDraft });
watch([source, model, key, connection], () => { configurationFailed.value = false; });
watch(open, visible => {
  if (!visible) settings.value = false;
  else {
    if (config.value && (!modelReady.value || configurationFailed.value)) settings.value = true;
    void scroll();
  }
});
watch(settings, visible => { if (visible) void load(); });
watch(expanded, () => { void scroll(); });
onMounted(load);
onBeforeUnmount(() => { disposed = true; controller?.abort(); key.value = ''; });
</script>

<template>
  <Teleport to="body">
  <button v-show="!open || !expanded" class="agent-launcher" :class="{ 'agent-launcher-open': open }" type="button" :aria-expanded="open" aria-controls="web-agent-panel" @click="open = !open">
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-9l-5 3v-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M7 9h10M7 13h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
    <span>{{ busy ? '回复中…' : open ? '收起助手' : '网页助手' }}</span>
  </button>
  <section v-show="open" id="web-agent-panel" class="web-agent-panel" :class="{ 'agent-expanded': expanded }" aria-label="网页助手">
    <header class="agent-header"><strong>网页助手</strong><div class="agent-window-actions">
      <button class="agent-expand-button" type="button" :aria-pressed="expanded" :aria-label="expanded ? '还原聊天窗口' : '展开聊天窗口'" @click="expanded = !expanded">{{ expanded ? '还原' : '展开' }}</button>
      <button class="agent-minimize-button" type="button" aria-label="收起网页助手" @click="open = false">−</button>
    </div></header>
    <div class="agent-toolbar"><NSelect v-model:value="connection" class="agent-connection-select" size="small" :options="options" :disabled="busy" placeholder="选择连接" @update:show="visible => { if (visible) void load(); }" /><template v-if="modelReady"><span>{{ source === 'shared' ? '社团提供模型' : '个人 Key' }}</span><span>{{ model }}</span></template><span v-else>尚未配置模型</span><button :disabled="busy" @click="settings = true">模型设置</button></div>
    <div v-if="config && !connection" class="agent-connection-hint"><span>请选择本人的连接，或创建默认 low 连接。</span><NButton size="small" :loading="busy" @click="createConnection">创建网页助手连接</NButton></div>
    <div class="agent-reading">
    <div ref="transcript" class="agent-transcript" aria-live="polite" @scroll="trackScroll">
      <p v-if="!messages.length" class="agent-empty">查询账目、库存，或描述要办理的事。</p>
      <article v-for="(message, index) in messages" :key="index" class="agent-message" :class="message.role">
        <div class="agent-message-meta">
          <small>{{ message.role === 'user' ? user.display_name : '网页助手' }}</small>
          <small v-if="message.incomplete && !(busy && index === messages.length - 1)" class="agent-interrupted">本轮未完成</small>
          <details v-if="message.tools?.length" class="agent-tools">
            <summary>{{ toolSummary(message, index) }}</summary>
            <div v-for="(tool, toolIndex) in message.tools" :key="toolIndex"><span>{{ tool.done ? '已返回' : busy && index === messages.length - 1 ? '进行中' : '待核对' }}</span>{{ labels[tool.name] || tool.name }}</div>
          </details>
        </div>
        <AgentMarkdown v-if="message.role === 'assistant' && message.content" :content="message.content" />
        <p v-else>{{ message.content || (busy && index === messages.length - 1 ? '正在处理…' : '') }}</p>
      </article>
    </div>
    <button v-if="!followLatest && messages.length" class="agent-latest" type="button" @click="scroll(true)">回到最新</button>
    </div>
    <p v-if="error && !settings" class="agent-error" role="alert">{{ error }}</p>
    <footer class="agent-composer"><div class="agent-usage"><span>本页用量 {{ usage.input.toLocaleString() }} 输入 / {{ usage.output.toLocaleString() }} 输出 token</span><button :disabled="busy || !messages.length" @click="clear">清空</button></div><NInput v-model:value="draft" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" :disabled="busy" placeholder="描述要查询或办理的事…" @keydown.ctrl.enter.prevent="send" /><div class="agent-send"><small>{{ connectionLevel === 'high' ? '直接办理须先获得你的明确确认' : 'low 提交的申请等待审批' }}</small><NButton v-if="busy" @click="controller?.abort()">停止</NButton><NButton v-else type="primary" :disabled="!canSend" @click="send">发送</NButton></div></footer>
  </section>
  <NModal v-model:show="settings" preset="card" title="模型设置" class="dialog compact-dialog agent-settings-dialog" :mask-closable="!busy" :closable="!busy" :close-on-esc="!busy">
    <div class="agent-settings">
      <label>连接<NSelect v-model:value="connection" :options="options" :disabled="busy" placeholder="选择本人的 low 或 high 连接" @update:show="visible => { if (visible) void load(); }" /></label>
      <NButton v-if="!options.length" size="small" :loading="busy" @click="createConnection">创建网页助手连接</NButton>
      <label>模型来源<NSelect v-model:value="source" :disabled="busy" :options="[{ label: '社团提供的 DeepSeek', value: 'shared', disabled: !config?.shared_available }, { label: '我的 DeepSeek Key', value: 'personal' }]" /></label>
      <label>模型<NSelect v-model:value="model" :disabled="busy" :options="(config?.models || []).map(value => ({ value, label: value }))" /></label>
      <label v-if="source === 'personal'">个人 DeepSeek Key<NInput v-model:value="key" type="password" show-password-on="click" :disabled="busy" autocomplete="off" placeholder="仅用于当前页面会话" /></label>
      <p v-if="!config?.shared_available">社团公共模型尚未配置，可先填写个人 Key。</p>
      <template v-if="user.role === 'admin'"><NButton size="small" :loading="balanceBusy" :disabled="!config?.shared_available" @click="queryBalance">查询公共账户余额</NButton><p v-if="balance">{{ balance }}</p></template>
      <small>原型的 Key 和对话仅保留在当前页面，刷新后清空。</small>
      <p v-if="error" class="agent-error" role="alert">{{ error }}</p>
    </div>
    <template #footer><div class="agent-settings-actions"><NButton type="primary" :disabled="!modelReady || busy" @click="configurationFailed = false; settings = false">使用此配置</NButton></div></template>
  </NModal>
  </Teleport>
</template>

<style scoped>
.agent-launcher { position:fixed; z-index:1199; right:24px; bottom:22px; display:flex; align-items:center; gap:8px; padding:10px 15px; border:1px solid #26313c; border-radius:6px; color:white; background:#26313c; box-shadow:0 3px 12px #0002; font:inherit; font-size:13px; }
.agent-launcher svg { width:21px; height:21px; flex:none; }
.agent-launcher span { color:inherit; }
.agent-launcher:hover { background:#3b4856; }
.web-agent-panel { position:fixed; z-index:1200; right:24px; top:96px; bottom:80px; width:min(560px, calc(100vw - 48px)); display:flex; flex-direction:column; color:var(--ink); background:var(--paper); border:1px solid #bfc7cf; border-radius:7px; box-shadow:0 8px 30px #0002; text-align:left; font-size:13px; overflow:hidden; }
.web-agent-panel.agent-expanded { top:24px; bottom:24px; width:min(860px, calc(100vw - 48px)); }
.agent-header { display:flex; justify-content:space-between; align-items:center; padding:10px 15px; border-bottom:1px solid var(--line); flex:none; }
.agent-header strong { font-family:var(--serif); font-weight:normal; font-size:20px; }
.agent-window-actions { display:flex; align-items:center; gap:14px; }
.agent-header button { border:0; background:none; font:inherit; padding:3px; color:var(--muted); }
.agent-header .agent-expand-button { font-size:12px; }
.agent-header .agent-minimize-button { font-size:25px; line-height:1; padding:0 3px; }
.agent-toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:6px 15px; border-bottom:1px solid var(--line); font-size:11px; color:var(--muted); }
.agent-toolbar button { margin-left:auto; }
.agent-connection-select { width:172px; flex:none; }
.agent-toolbar button,.agent-usage button { padding:0; border:0; background:none; text-decoration:underline; text-underline-offset:3px; font:inherit; color:inherit; }
.agent-settings { max-height:min(60dvh, 520px); overflow:auto; }
.agent-settings-actions { display:flex; justify-content:flex-end; }
.agent-connection-hint { display:flex; align-items:center; flex-wrap:wrap; gap:8px; padding:8px 15px; border-bottom:1px solid var(--line); font-size:12px; }
.agent-settings label { display:block; margin-bottom:10px; }
.agent-settings p { margin:8px 0; font-size:12px; }
.agent-reading { flex:1; display:flex; min-height:90px; position:relative; overflow:hidden; }
.agent-transcript { flex:1; min-width:0; overflow:auto; overflow-anchor:none; padding:14px 16px; overscroll-behavior:contain; scrollbar-gutter:stable; }
.agent-empty { margin:8px 0; color:var(--muted); }
.agent-latest { position:absolute; right:16px; bottom:12px; border:1px solid #c8ced5; border-radius:5px; padding:5px 10px; background:white; color:var(--ink); font:inherit; font-size:12px; box-shadow:0 2px 8px #0001; }
.agent-message { margin-bottom:16px; }
.agent-message-meta { display:flex; align-items:baseline; flex-wrap:wrap; gap:4px 10px; margin-bottom:4px; color:var(--muted); }
.agent-message-meta small { font-size:11px; }
.agent-message-meta .agent-interrupted { color:#8a4c20; }
.agent-message p { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
.agent-message.user { padding:9px 11px; background:#eee; border-radius:4px; }
.agent-tools { margin-left:auto; max-width:80%; font-size:11px; color:var(--muted); }
.agent-tools summary { cursor:pointer; overflow-wrap:anywhere; }
.agent-tools div { margin:3px 0; }
.agent-tools span { display:inline-block; width:54px; }
.agent-error { padding:8px 14px; margin:0; color:#8a2020; background:#fff1ef; border-top:1px solid #e3c7c2; overflow-wrap:anywhere; }
.agent-composer { border-top:1px solid var(--line); padding:8px 12px 10px; flex:none; }
.agent-usage { display:flex; justify-content:space-between; gap:8px; margin-bottom:6px; font-size:10px; color:#727c87; }
.agent-send { display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:6px; }
.agent-send small { font-size:10px; }
@media(max-width:700px) {
  .web-agent-panel,.web-agent-panel.agent-expanded { top:0; right:0; bottom:auto; width:100%; height:100dvh; border:0; border-radius:0; }
  .agent-launcher { right:12px; bottom:18px; padding:9px 13px; }
  .agent-launcher-open,.agent-expand-button { display:none; }
  .agent-header { padding:calc(9px + env(safe-area-inset-top)) 13px 9px; }
  .agent-transcript { padding:12px; }
  .agent-composer { padding-bottom:calc(10px + env(safe-area-inset-bottom)); }
  .agent-usage { flex-wrap:wrap; }
}
</style>
