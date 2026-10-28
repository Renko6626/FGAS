<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { NButton, NInput, NSelect } from 'naive-ui';
import type { User } from '../api/auth';
import { agentConnections } from '../api/agentConnections';
import { streamChat, webAgentApi, type AgentEvent, type ChatMessage, type WebAgentConfig } from '../api/webAgent';

const props = defineProps<{ user: User }>();
const emit = defineEmits<{ changed: [] }>();
const open = ref(new URLSearchParams(window.location.search).get('assistant') === '1');
const config = ref<WebAgentConfig | null>(null);
const connection = ref<string | null>(null);
const source = ref<'personal' | 'shared'>('shared');
const model = ref('deepseek-flash');
const key = ref('');
const draft = ref('');
const error = ref('');
const busy = ref(false);
const settings = ref(false);
const transcript = ref<HTMLElement | null>(null);
const messages = ref<(ChatMessage & { incomplete?: boolean })[]>([]);
const tools = ref<{ id: string; name: string; done: boolean }[]>([]);
const usage = ref({ input: 0, output: 0, requests: 0 });
const balance = ref('');
const balanceBusy = ref(false);
let controller: AbortController | null = null;
let disposed = false;
const options = computed(() => config.value?.connections.map(item => ({
  value: item.id, label: item.name + (item.active ? '' : '（已停用）'), disabled: !item.active,
})) || []);
const canSend = computed(() => Boolean(connection.value && draft.value.trim() && !busy.value &&
  (source.value === 'shared' ? config.value?.shared_available : key.value.trim())));
const labels: Record<string, string> = {
  fgas_help: '查看业务指南', fgas_query: '查询业务资料', fgas_propose: '提交待审批申请',
};

async function load() {
  try {
    const data = await webAgentApi.config();
    if (disposed) return;
    config.value = data;
    const active = data.connections.filter(item => item.active);
    connection.value = active.find(item => item.name === '网页助手')?.id || active[0]?.id || null;
    source.value = data.shared_available ? 'shared' : 'personal';
    settings.value = !connection.value || !data.shared_available;
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
async function scroll() {
  await nextTick();
  if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight;
}
function parts(text: string) {
  return text.split(/\b((?:FT|ST)-\d{6})\b/g).filter(Boolean).map(content => ({
    content, href: /^(FT|ST)-\d{6}$/.test(content)
      ? '/#' + (content.startsWith('FT') ? 'transfers' : 'stock') + '?code=' + content : null,
  }));
}
async function send() {
  if (!canSend.value || !connection.value) return;
  if (messages.value.length >= 40) { error.value = '这段对话已较长，请清空会话后继续'; return; }
  const history = messages.value.filter(item => !item.incomplete && item.content.trim()).map(({ role, content }) => ({ role, content }));
  const message = draft.value.trim();
  messages.value.push({ role: 'user', content: message });
  messages.value.push({ role: 'assistant', content: '', incomplete: true });
  const index = messages.value.length - 1;
  draft.value = '';
  error.value = '';
  tools.value = [];
  busy.value = true;
  controller = new AbortController();
  let changed = false;
  const onEvent = (event: AgentEvent) => {
    if (disposed) return;
    if (event.type === 'text') messages.value[index]!.content += event.text || '';
    else if (event.type === 'tool_start') {
      tools.value.push({ id: event.id || '', name: event.name || '', done: false });
      if (event.name === 'fgas_propose') changed = true;
    } else if (event.type === 'tool_end') {
      const tool = tools.value.find(item => item.id === event.id);
      if (tool) tool.done = true;
    } else if (event.type === 'usage') {
      usage.value.input += event.input_tokens || 0;
      usage.value.output += event.output_tokens || 0;
      usage.value.requests += event.requests || 0;
    } else if (event.type === 'done') messages.value[index]!.incomplete = false;
    else if (event.type === 'error') error.value = event.message || '本轮未能完成';
    void scroll();
  };
  try {
    await streamChat({ credential_id: connection.value, message, history, model: model.value,
      source: source.value, ...(source.value === 'personal' ? { api_key: key.value } : {}) }, controller.signal, onEvent);
  } catch (e) {
    if (!disposed) error.value = (e as Error).name === 'AbortError'
      ? '已停止接收回复。已经提交的业务请到记录中核对。' : (e as Error).message;
  } finally {
    controller = null;
    if (!disposed) { busy.value = false; if (changed) emit('changed'); }
  }
}
function clear() {
  if (busy.value) return;
  messages.value = [];
  tools.value = [];
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
onMounted(load);
onBeforeUnmount(() => { disposed = true; controller?.abort(); key.value = ''; });
</script>

<template>
  <NButton quaternary @click="open = !open">网页助手</NButton>
  <section v-if="open" class="web-agent-panel" aria-label="网页助手">
    <header class="agent-header"><div><strong>网页助手</strong><small>以你的低权限连接查询和提交申请</small></div><button aria-label="关闭网页助手" @click="open = false">×</button></header>
    <div class="agent-toolbar"><span>{{ source === 'shared' ? '社团提供模型' : '个人 Key' }}</span><span>{{ model }}</span><button :disabled="busy" @click="settings = !settings">模型设置</button></div>
    <div v-if="settings" class="agent-settings">
      <label>连接<NSelect v-model:value="connection" :options="options" :disabled="busy" placeholder="选择本人的低权限连接" /></label>
      <NButton v-if="!options.length" size="small" :loading="busy" @click="createConnection">创建网页助手连接</NButton>
      <label>模型来源<NSelect v-model:value="source" :disabled="busy" :options="[{ label: '社团提供的 DeepSeek', value: 'shared', disabled: !config?.shared_available }, { label: '我的 DeepSeek Key', value: 'personal' }]" /></label>
      <label>模型<NSelect v-model:value="model" :disabled="busy" :options="(config?.models || []).map(value => ({ value, label: value }))" /></label>
      <label v-if="source === 'personal'">个人 DeepSeek Key<NInput v-model:value="key" type="password" show-password-on="click" :disabled="busy" autocomplete="off" placeholder="仅用于当前页面会话" /></label>
      <p v-if="!config?.shared_available">社团公共模型尚未配置，可先填写个人 Key。</p>
      <template v-if="user.role === 'admin'"><NButton size="small" :loading="balanceBusy" :disabled="!config?.shared_available" @click="queryBalance">查询公共账户余额</NButton><p v-if="balance">{{ balance }}</p></template>
      <small>原型的 Key 和对话仅保留在当前页面，刷新后清空。</small>
    </div>
    <div ref="transcript" class="agent-transcript" aria-live="polite">
      <div v-if="!messages.length" class="agent-empty"><h3>从一笔记录开始</h3><p>可以查询库存、核对资金，或帮你整理一份待审批申请。</p><div><span>查询我当前的连接身份</span><span>有哪些待完成的货物转移？</span></div></div>
      <article v-for="(message, index) in messages" :key="index" class="agent-message" :class="message.role"><small>{{ message.role === 'user' ? user.display_name : '网页助手' }}</small><p><template v-for="(part, n) in parts(message.content)" :key="n"><a v-if="part.href" :href="part.href">{{ part.content }}</a><span v-else>{{ part.content }}</span></template><span v-if="busy && index === messages.length - 1 && !message.content">正在处理…</span></p></article>
      <div v-if="tools.length" class="agent-tools"><div v-for="(tool, index) in tools" :key="index"><span>{{ tool.done ? '已返回' : busy ? '进行中' : '待核对' }}</span>{{ labels[tool.name] || tool.name }}</div></div>
    </div>
    <p v-if="error" class="agent-error" role="alert">{{ error }}</p>
    <footer class="agent-composer"><div class="agent-usage"><span>本页会话 {{ usage.input.toLocaleString() }} 输入 / {{ usage.output.toLocaleString() }} 输出 token</span><button :disabled="busy || !messages.length" @click="clear">清空</button></div><NInput v-model:value="draft" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" :disabled="busy" placeholder="描述要查询或办理的事…" @keydown.ctrl.enter.prevent="send" /><div class="agent-send"><small>低权限提交的申请等待人工审批</small><NButton v-if="busy" @click="controller?.abort()">停止</NButton><NButton v-else type="primary" :disabled="!canSend" @click="send">发送</NButton></div></footer>
  </section>
</template>

<style scoped>
.web-agent-panel { position: fixed; z-index: 1200; right: 24px; top: 128px; bottom: 20px; width: min(450px, calc(100vw - 32px)); display: flex; flex-direction: column; color: var(--ink); background: var(--paper); border: 2px solid var(--ink); box-shadow: 7px 7px 0 #0002; text-align: left; font-size: 13px; }
.agent-header { display:flex; justify-content:space-between; align-items:flex-start; padding:16px 18px; border-bottom:2px solid var(--ink); }
.agent-header strong { display:block; font-family:var(--serif); font-weight:normal; font-size:23px; }
.agent-header small { display:block; margin-top:3px; }
.agent-header button { border:0; background:none; font-size:25px; line-height:1; }
.agent-toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:10px 16px; border-bottom:1px solid var(--line); font-size:12px; }
.agent-toolbar button { margin-left:auto; }
.agent-toolbar button,.agent-usage button { padding:0; border:0; background:none; text-decoration:underline; text-underline-offset:3px; }
.agent-settings { padding:12px 16px; border-bottom:1px solid var(--line); max-height:48%; overflow:auto; flex-shrink:0; background:#f8f8f8; }
.agent-settings label { display:block; margin-bottom:10px; }
.agent-settings p { margin:8px 0; font-size:12px; }
.agent-transcript { flex:1; min-height:90px; overflow:auto; padding:18px; }
.agent-empty { padding:24px 0; }
.agent-empty h3 { font-family:var(--serif); font-size:21px; margin-bottom:10px; }
.agent-empty p { color:var(--muted); }
.agent-empty div { display:grid; gap:8px; margin-top:22px; }
.agent-empty span { border-left:2px solid #aaa; padding-left:10px; color:var(--muted); }
.agent-message { margin-bottom:20px; }
.agent-message small { display:block; margin-bottom:5px; }
.agent-message p { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
.agent-message.user { padding:12px; background:#eee; }
.agent-message a { color:inherit; text-underline-offset:3px; }
.agent-tools { border-top:1px solid var(--line); margin-top:14px; padding-top:10px; font-size:12px; color:var(--muted); }
.agent-tools div { margin:4px 0; }
.agent-tools span { display:inline-block; width:54px; }
.agent-error { padding:10px 16px; margin:0; color:#8a2020; background:#fff1ef; border-top:1px solid #e3c7c2; overflow-wrap:anywhere; }
.agent-composer { border-top:1px solid var(--line); padding:12px 14px; }
.agent-usage { display:flex; justify-content:space-between; gap:8px; margin-bottom:9px; font-size:11px; color:var(--muted); }
.agent-send { display:flex; justify-content:space-between; align-items:center; gap:10px; margin-top:9px; }
@media(max-width:700px) { .web-agent-panel { top:12px; right:12px; bottom:12px; width:calc(100vw - 24px); box-shadow:4px 4px 0 #0002; } .agent-header { padding:12px 14px; } .agent-settings { max-height:46%; } .agent-usage { flex-wrap:wrap; } }
</style>
